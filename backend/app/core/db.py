"""Async engine, session factory, and the one-transaction-per-request dependency."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import URL
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

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
        except BaseException:
            await session.rollback()
            raise
        await session.commit()


SessionDep = Annotated[AsyncSession, Depends(get_session, scope="function")]


def get_sessionmaker(request: Request) -> SessionMaker:
    return request.app.state.sessionmaker


# Only for work that must stay outside the request's transaction (the health check). Everything
# else uses SessionDep.
SessionMakerDep = Annotated[SessionMaker, Depends(get_sessionmaker)]
