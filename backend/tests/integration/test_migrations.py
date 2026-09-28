"""Migrations against real databases: every migration applies from empty, round-trips (down one
step and up again), and leaves no drift between the models and the database; plus the
procrastinate schema migration and the autogenerate filter."""

from pathlib import Path
from typing import Any

import anyio
import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
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


def alembic_config(url: URL | None = None) -> Config:
    config = Config(BACKEND / "alembic.ini")
    config.attributes["url"] = url
    config.attributes["configure_logger"] = False
    return config


# Every revision, oldest first.
REVISIONS = [
    script.revision
    for script in reversed(list(ScriptDirectory.from_config(alembic_config()).walk_revisions()))
]


async def migrate(url: URL, target: str, *, down: bool = False) -> None:
    step = command.downgrade if down else command.upgrade
    # Alembic's async env runs its own event loop, so it runs in a worker thread.
    await anyio.to_thread.run_sync(step, alembic_config(url), target)


async def current_revision(url: URL) -> str | None:
    engine = create_engine(url)
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(
                lambda sync: MigrationContext.configure(sync).get_current_revision()
            )
    finally:
        await engine.dispose()


@pytest.mark.parametrize("revision", REVISIONS)
async def test_migration_round_trips(scratch_database: URL, revision: str) -> None:
    """Up to this revision, down one step, and up again: the downgrade works and doesn't leave
    anything behind that would stop the upgrade from running twice."""
    await migrate(scratch_database, revision)
    await migrate(scratch_database, "-1", down=True)

    await migrate(scratch_database, revision)

    assert await current_revision(scratch_database) == revision


async def test_models_and_migrations_have_not_drifted(scratch_database: URL) -> None:
    """`alembic check` through migrations/env.py (so it covers env.py's settings, including the
    procrastinate filter) finds nothing for autogenerate to add."""
    await migrate(scratch_database, "head")

    await anyio.to_thread.run_sync(command.check, alembic_config(scratch_database))


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
