"""Test harness (docs/testing-strategy.md, "Database isolation").

The test database is migrated once per session with Alembic. Each test that asks for a database
gets one connection inside an outer transaction; the app's sessions join it with
`join_transaction_mode="create_savepoint"`, so their commits only release savepoints and
everything is rolled back when the test ends.
"""

import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import cast

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import URL, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, async_sessionmaker

from app.core.db import SessionMaker, create_engine, create_sessionmaker
from app.core.settings import TEST_DATABASE_NAME, Settings
from tests.factories import SEED, BaseFactory
from tests.support.concurrency import (
    check_tables_are_empty,
    concurrency_tables,
    create_concurrency_engine,
    truncate,
)
from tests.support.models import SupportBase

BACKEND = Path(__file__).resolve().parents[1]

# `pytester` runs a test in a separate pytest process (the concurrency fixture's wiring test).
pytest_plugins = ["pytester"]


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    # Session scope: one event loop for the whole run, so the session-scoped engine works.
    return "asyncio"


@pytest.fixture(autouse=True)
def _seed_factories() -> None:
    """Fixed seed, reset per test, so generated data never depends on test order."""
    BaseFactory.seed_random(SEED)


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings(api_docs_enabled=True)  # pyright: ignore[reportCallIssue]


@pytest.fixture(scope="session")
def test_database_url(settings: Settings) -> URL:
    url = settings.test_database_url()
    assert url.database == TEST_DATABASE_NAME, "tests only ever run against the test database"
    return url


@pytest.fixture(scope="session")
def migrated_database(test_database_url: URL) -> URL:
    """Bring the test database to the latest migration (the real schema, never create_all)."""
    config = Config(BACKEND / "alembic.ini")
    config.attributes["url"] = test_database_url
    config.attributes["configure_logger"] = False
    try:
        command.upgrade(config, "head")
    except OperationalError as exc:
        pytest.exit(
            f"Can't reach the test database {test_database_url.render_as_string()}: {exc.orig}\n"
            "Start Postgres with `uv run wl up`. If the test database is missing, the volume "
            "predates it: recreate it with `uv run wl down -v && uv run wl up`.",
            returncode=1,
        )
    return test_database_url


@pytest.fixture(scope="session")
async def engine(migrated_database: URL) -> AsyncIterator[AsyncEngine]:
    engine = create_engine(migrated_database)
    yield engine
    await engine.dispose()


@pytest.fixture
async def connection(engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    """One connection per test, inside an outer transaction that is always rolled back."""
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            yield connection
        finally:
            await transaction.rollback()


@pytest.fixture
def sessionmaker(connection: AsyncConnection) -> SessionMaker:
    """Sessions that join the test's transaction; their commits release savepoints."""
    return async_sessionmaker(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )


@pytest.fixture
async def session(sessionmaker: SessionMaker) -> AsyncIterator[AsyncSession]:
    """A session for arranging and asserting; factories persist through it."""
    async with sessionmaker() as session:
        BaseFactory.__async_session__ = session
        try:
            yield session
        finally:
            BaseFactory.__async_session__ = None


@pytest.fixture(scope="session")
async def concurrency_engine(migrated_database: URL) -> AsyncIterator[AsyncEngine]:
    """The engine behind `concurrency`: a pool sized for `run_in_parallel` and a Postgres
    `lock_timeout` on every connection (tests/support/concurrency.py)."""
    engine = create_concurrency_engine(migrated_database)
    yield engine
    await engine.dispose()


@pytest.fixture
async def concurrency(
    request: pytest.FixtureRequest, concurrency_engine: AsyncEngine
) -> AsyncIterator[SessionMaker]:
    """Sessions with real commits, for tests that need separate connections or another process
    (a worker) to see their data. Afterwards, pass or fail, the tables named in
    `@pytest.mark.concurrency(...)` are truncated and every table must be empty: a test that
    left rows elsewhere fails (and those rows are removed). Never combine with the rolled-back
    `connection`/`session` fixtures: the truncate would wait on that open transaction's
    locks."""
    item = cast(pytest.Item, request.node)  # pyright: ignore[reportUnknownMemberType] -- untyped in pytest
    marker = item.get_closest_marker("concurrency")
    tables = concurrency_tables(marker.args if marker else (), request.fixturenames)
    try:
        yield create_sessionmaker(concurrency_engine)
    finally:
        await truncate(concurrency_engine, tables)
        await check_tables_are_empty(concurrency_engine)


@pytest.fixture
async def scratch_database(migrated_database: URL) -> AsyncIterator[URL]:
    """A new, empty database for the test (e.g. to run migrations up and down), dropped after."""
    name = f"{migrated_database.database}_scratch_{uuid.uuid4().hex[:8]}"
    admin = create_engine(migrated_database).execution_options(isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as connection:
            await connection.execute(text(f'CREATE DATABASE "{name}"'))
        yield migrated_database.set(database=name)
    finally:
        async with admin.connect() as connection:
            await connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        await admin.dispose()


@pytest.fixture
async def support_tables(connection: AsyncConnection) -> None:
    """Create the test-only tables (tests/support/models.py) inside the test's transaction."""
    await connection.run_sync(SupportBase.metadata.create_all)


@pytest.fixture
async def committed_support_tables(engine: AsyncEngine) -> AsyncIterator[None]:
    """The test-only tables, committed, for `concurrency` tests; dropped afterwards. Request it
    before `concurrency`, so the tables are truncated before they're dropped."""
    async with engine.begin() as connection:
        await connection.run_sync(SupportBase.metadata.create_all)
    try:
        yield
    finally:
        async with engine.begin() as connection:
            await connection.run_sync(SupportBase.metadata.drop_all)
