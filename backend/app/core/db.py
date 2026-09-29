"""Async engine, session factory, and the one-transaction-per-request dependency."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, Request
from sqlalchemy import URL, event, null, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import InstrumentedAttribute, Session, class_mapper
from sqlalchemy.orm.attributes import instance_state
from sqlalchemy.orm.exc import StaleDataError

from app.core.base_model import INCLUDE_DELETED, StaleVersionError, VersionMixin
from app.core.errors import NotFoundError, stale_table, versioned_class_for

type SessionMaker = async_sessionmaker[AsyncSession]


def create_engine(url: URL) -> AsyncEngine:
    return create_async_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 5})


def create_sessionmaker(engine: AsyncEngine) -> SessionMaker:
    # expire_on_commit=False: objects stay readable after the request's commit while the
    # response is serialized (build-plan.md, "Async rules").
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """One transaction per request: commit on success, roll back on any exception.

    Services may flush(); nothing else commits. Registered with scope="function" so the commit
    happens before the response is sent: a failed commit is an error, never a false success.
    """
    async with get_sessionmaker(request)() as session:
        try:
            yield session
            await session.commit()
        except BaseException as exc:
            written = _versioned_rows_written(session, exc)
            await session.rollback()
            if written and await _any_gone(session, written):
                # The "stale version" was a row deleted, or soft-deleted, since this request
                # loaded it: it's gone, not changed.
                raise NotFoundError from exc
            raise


_VERSIONED_WRITES = "versioned_writes"


@dataclass(frozen=True)
class _Write:
    model: type[VersionMixin]
    row_id: Any
    was_soft_deleted: bool  # when this session loaded it (before any change in the flush)


@event.listens_for(Session, "before_flush")
def _remember_versioned_writes(session: Session, _context: object, _instances: object) -> None:
    """Record the versioned rows each flush updates or deletes. A failed flush clears the
    session's dirty and deleted lists, so this record is how `get_session` learns afterwards
    which row went stale, and whether it was soft-deleted when this session loaded it."""
    writes: list[_Write] = []
    for obj in (*session.dirty, *session.deleted):
        state = instance_state(obj)
        if isinstance(obj, VersionMixin) and state.identity:
            loaded = state.committed_state.get("deleted_at", getattr(obj, "deleted_at", None))
            writes.append(_Write(type(obj), state.identity[0], loaded is not None))
    session.info[_VERSIONED_WRITES] = writes


def _versioned_rows_written(session: AsyncSession, exc: BaseException) -> list[_Write]:
    """For a stale-row error on a versioned table, the rows of that table the failed flush was
    updating or deleting (one of them is the stale row)."""
    if not isinstance(exc, StaleDataError) or isinstance(exc, StaleVersionError):
        return []  # check_version compares a loaded copy, so that row existed
    table = stale_table(exc)
    model = versioned_class_for(table) if table else None
    if model is None:
        return []
    writes: list[_Write] = session.info.get(_VERSIONED_WRITES, [])
    return [write for write in writes if issubclass(write.model, model)]


async def _any_gone(session: AsyncSession, written: list[_Write]) -> bool:
    """Whether a written row is gone for the user: deleted, or soft-deleted since this session
    loaded it (a row that was already soft-deleted, e.g. one being restored, isn't "gone")."""
    model = written[0].model
    mapper = class_mapper(model)
    primary_key: InstrumentedAttribute[Any] = mapper.get_property_by_column(
        mapper.primary_key[0]
    ).class_attribute
    # A versioned model without soft delete selects NULL in its place.
    deleted_at: Any = getattr(model, "deleted_at", null())
    ids = [write.row_id for write in written]
    rows = await session.execute(
        select(primary_key, deleted_at)
        .where(primary_key.in_(ids))
        .execution_options(**{INCLUDE_DELETED: True})
    )
    now_soft_deleted: dict[Any, bool] = {row_id: gone is not None for row_id, gone in rows}
    return any(
        write.row_id not in now_soft_deleted
        or (now_soft_deleted[write.row_id] and not write.was_soft_deleted)
        for write in written
    )


SessionDep = Annotated[AsyncSession, Depends(get_session, scope="function")]


def get_sessionmaker(request: Request) -> SessionMaker:
    return request.app.state.sessionmaker


# Only for work that must stay outside the request's transaction (the health check). Everything
# else uses SessionDep.
SessionMakerDep = Annotated[SessionMaker, Depends(get_sessionmaker)]
