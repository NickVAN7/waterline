"""Helpers behind the `concurrency` fixture (tests/conftest.py)."""

from collections.abc import Collection, Sequence

import anyio
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

# Fixtures that hold the rolled-back per-test transaction; truncating a table while it's open
# would wait on its locks.
TRANSACTIONAL_FIXTURES = frozenset({"connection", "sessionmaker", "session", "client"})


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


async def truncate(engine: AsyncEngine, tables: Sequence[str]) -> None:
    """Empty `tables` (and anything referencing them) in a committed transaction."""
    async with engine.begin() as connection:
        quote = connection.dialect.identifier_preparer.quote
        names = ", ".join(quote(table) for table in tables)
        await connection.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))


async def wait_until_blocked_on_a_lock(engine: AsyncEngine, backend_pid: int) -> None:
    """Return once Postgres reports the backend `backend_pid` waiting on a lock (it has reached
    the contended row). The caller bounds the wait with anyio.fail_after."""
    query = text("SELECT wait_event_type FROM pg_stat_activity WHERE pid = :pid")
    async with engine.connect() as connection:
        # Polling is the only option: the state lives in Postgres, not in this process.
        while await connection.scalar(query, {"pid": backend_pid}) != "Lock":  # noqa: ASYNC110
            await anyio.sleep(0.02)
