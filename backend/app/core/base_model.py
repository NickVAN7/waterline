"""Declarative base, constraint naming convention, and the columns every table shares.

design-doc §3 and schema-doc "Conventions applied to every table": UUIDv7 primary keys generated
in Python (known before flush), and `created_at`/`updated_at` as timestamptz with `updated_at`
maintained by the ORM.
"""

import uuid
from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import DateTime, MetaData, event, func
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    ORMExecuteState,
    Session,
    declared_attr,
    mapped_column,
    with_loader_criteria,
)
from sqlalchemy.orm.exc import StaleDataError

# Stable, predictable constraint names, so Alembic autogenerate and hand-written migrations
# agree. Postgres truncates identifiers at 63 characters.
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

TYPE_ANNOTATION_MAP: dict[Any, Any] = {datetime: DateTime(timezone=True)}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = TYPE_ANNOTATION_MAP


class IdMixin:
    """UUIDv7 primary key, assigned when the object is constructed (see `_assign_id`)."""

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)


class TimestampMixin:
    """Database-clock timestamps. `eager_defaults` returns them with the INSERT/UPDATE, so
    they're readable after flush without a lazy load (which async sessions can't do)."""

    __mapper_args__: ClassVar[dict[str, Any]] = {"eager_defaults": True}

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


@event.listens_for(IdMixin, "init", propagate=True)
def _assign_id(target: IdMixin, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
    kwargs.setdefault("id", uuid.uuid7())


class SoftDeleteMixin:
    """`deleted_at` soft delete (design-doc §9). Rows with it set are hidden from every ORM
    query unless the query opts in with `.execution_options(include_deleted=True)`."""

    deleted_at: Mapped[datetime | None] = mapped_column(default=None)


INCLUDE_DELETED = "include_deleted"


@event.listens_for(Session, "do_orm_execute")
def _hide_soft_deleted(state: ORMExecuteState) -> None:
    """Add `deleted_at IS NULL` for every soft-deletable entity in a SELECT, including the
    related rows it loads, unless the statement opted in."""
    if (
        state.is_select
        and not state.is_column_load
        and not state.is_relationship_load
        and not state.execution_options.get(INCLUDE_DELETED, False)
    ):
        state.statement = state.statement.options(
            with_loader_criteria(
                SoftDeleteMixin,
                lambda cls: cls.deleted_at.is_(None),  # pyright: ignore[reportUnknownLambdaType, reportUnknownMemberType]
                include_aliases=True,
            )
        )


class VersionMixin:
    """Optimistic locking (design-doc §3): every ORM update checks and increments `version`,
    and an update based on a stale version raises `StaleDataError` (409 over HTTP).

    List it **before** `BaseModel` in the class bases: its `__mapper_args__` keeps
    `TimestampMixin`'s `eager_defaults` and adds the version column.
    """

    version: Mapped[int] = mapped_column(nullable=False)

    @declared_attr.directive
    @classmethod
    def __mapper_args__(cls) -> dict[str, Any]:
        return {**TimestampMixin.__mapper_args__, "version_id_col": cls.__table__.c.version}  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]


class StaleVersionError(StaleDataError):
    """The client's copy is older than the stored row."""


def check_version(entity: VersionMixin, expected: int) -> None:
    """Refuse an edit based on an older copy: the version the client loaded (sent back with
    the update) must still be the stored one. The ORM's own check covers the rest: a write
    between this request's load and its flush."""
    if entity.version != expected:
        raise StaleVersionError(
            f"{type(entity).__name__} is at version {entity.version}, not {expected}"
        )


class BaseModel(IdMixin, TimestampMixin, Base):
    """Base for app tables. Tables without an `id` (e.g. a composite key) use `Base` with
    `TimestampMixin` instead."""

    __abstract__ = True
