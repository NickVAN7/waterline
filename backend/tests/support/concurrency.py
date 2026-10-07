"""Helpers behind the `concurrency` fixture (tests/conftest.py) and race tests
(testing-strategy.md, "Concurrency"; TD-4)."""

from collections.abc import AsyncGenerator, Awaitable, Callable, Collection, Sequence
from contextlib import asynccontextmanager

import anyio
import pytest
from sqlalchemy import URL, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.core.db import SessionMaker
from tests.factories import BaseFactory

# Fixtures that hold the rolled-back per-test transaction; truncating a table while it's open
# would wait on its locks.
TRANSACTIONAL_FIXTURES = frozenset({"connection", "sessionmaker", "session", "client"})

# The most transactions `run_in_parallel` holds open at once. The concurrency engine's pool has
# room for them plus the connections a test uses for setup and checks.
MAX_PARALLEL = 20
POOL_SIZE = MAX_PARALLEL + 5

# A statement waiting this long for a lock fails instead of hanging the run (a deadlocked race
# test, or a lock the test forgot to release).
LOCK_TIMEOUT = "5s"

# Every parallel section must finish within this many seconds.
PARALLEL_TIME_LIMIT = 10

# Tables that are never empty, by design.
NEVER_EMPTY = frozenset({"alembic_version"})


def concurrency_tables(
    marker_args: Sequence[object], fixturenames: Collection[str]
) -> tuple[str, ...]:
    """The tables to truncate after a concurrency test, or a test failure explaining misuse."""
    tables = tuple(str(arg) for arg in marker_args)
    if not tables:
        pytest.fail("the concurrency fixture needs @pytest.mark.concurrency('<table>', ...)")
    mixed = TRANSACTIONAL_FIXTURES.intersection(fixturenames)
    if mixed:
        pytest.fail(f"the concurrency fixture can't be combined with {', '.join(sorted(mixed))}")
    return tables


def create_concurrency_engine(url: URL) -> AsyncEngine:
    """An engine for tests with real commits: a pool large enough for `MAX_PARALLEL`
    transactions (and no overflow, so a leak shows up as a timeout, not a surprise connection),
    and a Postgres `lock_timeout` on every connection."""
    return create_async_engine(
        url,
        pool_size=POOL_SIZE,
        max_overflow=0,
        pool_timeout=PARALLEL_TIME_LIMIT,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5, "options": f"-c lock_timeout={LOCK_TIMEOUT}"},
    )


async def truncate(engine: AsyncEngine, tables: Sequence[str]) -> None:
    """Empty `tables` (and anything referencing them) in a committed transaction."""
    async with engine.begin() as connection:
        quote = connection.dialect.identifier_preparer.quote
        names = ", ".join(quote(table) for table in tables)
        await connection.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))


async def nonempty_tables(engine: AsyncEngine) -> list[str]:
    """Every table in the public schema that has rows (apart from `NEVER_EMPTY`): the app's,
    procrastinate's, and any test-only tables that exist."""
    async with engine.connect() as connection:
        quote = connection.dialect.identifier_preparer.quote
        names = await connection.scalars(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename")
        )
        found: list[str] = []
        for name in names.all():
            if name in NEVER_EMPTY:
                continue
            has_rows = await connection.scalar(
                text(f"SELECT EXISTS (SELECT FROM {quote(name)})")  # noqa: S608 -- catalog names
            )
            if has_rows:
                found.append(name)
        return found


async def check_tables_are_empty(engine: AsyncEngine) -> None:
    """Fail the test if it left committed rows behind (a table missing from its
    `@pytest.mark.concurrency(...)` list), after emptying them so later tests start clean."""
    leftover = await nonempty_tables(engine)
    if leftover:
        await truncate(engine, leftover)
        pytest.fail(
            "the test left committed rows in "
            f"{', '.join(leftover)}: name every table it writes in @pytest.mark.concurrency(...)"
        )


@asynccontextmanager
async def committing_factories(sessionmaker: SessionMaker) -> AsyncGenerator[AsyncSession]:
    """Factories write through a session that commits on exit, so their rows are visible to
    every other connection (a race test's committed parents: an org, a project)."""
    async with sessionmaker() as session:
        BaseFactory.__async_session__ = session
        try:
            yield session
            await session.commit()
        finally:
            BaseFactory.__async_session__ = None


class _StartBarrier:
    """Releases every waiter once `parties` of them have arrived."""

    def __init__(self, parties: int) -> None:
        self._waiting = parties
        self._all_arrived = anyio.Event()

    async def wait(self) -> None:
        self._waiting -= 1
        if self._waiting == 0:
            self._all_arrived.set()
        await self._all_arrived.wait()


async def run_in_parallel[T](
    sessionmaker: SessionMaker,
    n: int,
    work: Callable[[AsyncSession, int], Awaitable[T]],
    *,
    time_limit: float = PARALLEL_TIME_LIMIT,
) -> list[T]:
    """Run `work(session, index)` in `n` transactions that are all open at once, commit each,
    and return the results in index order.

    Every transaction has started (its first statement has run) before any `work` begins: a
    start barrier holds them, so they really overlap instead of running one after another, and
    a racy implementation can't pass by luck. The whole section fails with `TimeoutError` after
    `time_limit` seconds (a deadlock), and each statement after the `lock_timeout`.
    """
    if not 1 <= n <= MAX_PARALLEL:
        raise ValueError(f"run_in_parallel takes 1 to {MAX_PARALLEL} transactions, not {n}")
    barrier = _StartBarrier(n)
    results: dict[int, T] = {}

    async def one(index: int) -> None:
        async with sessionmaker() as session:
            await session.execute(select(1))  # start this transaction before the barrier
            await barrier.wait()
            results[index] = await work(session, index)
            await session.commit()

    with anyio.fail_after(time_limit):
        async with anyio.create_task_group() as group:
            for index in range(n):
                group.start_soon(one, index)
    return [results[index] for index in range(n)]


async def wait_until_blocked_on_a_lock(engine: AsyncEngine, backend_pid: int) -> None:
    """Return once Postgres reports the backend `backend_pid` waiting on a lock (it has reached
    the contended row). The caller bounds the wait with anyio.fail_after."""
    query = text("SELECT wait_event_type FROM pg_stat_activity WHERE pid = :pid")
    async with engine.connect() as connection:
        # Polling is the only option: the state lives in Postgres, not in this process.
        while await connection.scalar(query, {"pid": backend_pid}) != "Lock":  # noqa: ASYNC110
            await anyio.sleep(0.02)
