"""Migrations against real databases: the procrastinate schema migration, and autogenerate
ignoring procrastinate's objects. (Round-trip and drift checks for every migration: S0-C5.)"""

from pathlib import Path
from typing import Any

import anyio
import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import URL, Connection, text
from sqlalchemy.ext.asyncio import AsyncConnection

import app.models  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers every model
from app.core.base_model import Base
from app.core.db import create_engine
from app.core.migration_filters import include_object

pytestmark = pytest.mark.anyio

BACKEND = Path(__file__).resolve().parents[2]
PROCRASTINATE_OBJECTS = text(
    "SELECT"
    " (SELECT count(*) FROM pg_tables WHERE tablename LIKE 'procrastinate\\_%'),"
    " (SELECT count(*) FROM pg_proc WHERE proname LIKE 'procrastinate\\_%'),"
    " (SELECT count(*) FROM pg_type WHERE typname LIKE 'procrastinate\\_%' AND typtype = 'e')"
)


async def migrate(url: URL, target: str, *, down: bool = False) -> None:
    config = Config(BACKEND / "alembic.ini")
    config.attributes["url"] = url
    config.attributes["configure_logger"] = False
    step = command.downgrade if down else command.upgrade
    # Alembic's async env runs its own event loop, so it runs in a worker thread.
    await anyio.to_thread.run_sync(step, config, target)


async def procrastinate_objects(url: URL) -> tuple[int, int, int]:
    engine = create_engine(url)
    try:
        async with engine.connect() as connection:
            row = (await connection.execute(PROCRASTINATE_OBJECTS)).one()
    finally:
        await engine.dispose()
    return (row[0], row[1], row[2])


async def test_upgrade_installs_procrastinate(scratch_database: URL) -> None:
    await migrate(scratch_database, "head")

    # tables, functions, enum types in procrastinate 3.10.0's schema
    assert await procrastinate_objects(scratch_database) == (4, 18, 2)


async def test_downgrade_removes_every_procrastinate_object(scratch_database: URL) -> None:
    await migrate(scratch_database, "head")

    await migrate(scratch_database, "base", down=True)

    assert await procrastinate_objects(scratch_database) == (0, 0, 0)


async def test_upgrade_after_downgrade_succeeds(scratch_database: URL) -> None:
    await migrate(scratch_database, "head")
    await migrate(scratch_database, "base", down=True)

    await migrate(scratch_database, "head")

    assert await procrastinate_objects(scratch_database) == (4, 18, 2)


def diff(connection: Connection, **opts: Any) -> list[Any]:
    return compare_metadata(MigrationContext.configure(connection, opts=opts), Base.metadata)


async def test_autogenerate_ignores_procrastinate_objects(connection: AsyncConnection) -> None:
    assert await connection.run_sync(diff, include_object=include_object) == []


async def test_without_the_filter_autogenerate_would_drop_procrastinate(
    connection: AsyncConnection,
) -> None:
    dropped = {
        change[1].name for change in await connection.run_sync(diff) if change[0] == "remove_table"
    }

    assert "procrastinate_jobs" in dropped
