"""Helpers behind the `concurrency` fixture (tests/conftest.py)."""

from collections.abc import Collection, Sequence

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
