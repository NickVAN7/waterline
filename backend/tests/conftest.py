"""Test harness (docs/testing-strategy.md, "Database isolation").

The test database is migrated once per session with Alembic. Each test that asks for a database
gets one connection inside an outer transaction; the app's sessions join it with
`join_transaction_mode="create_savepoint"`, so their commits only release savepoints and
everything is rolled back when the test ends.
"""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import URL
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, async_sessionmaker

from app.core.db import SessionMaker, create_engine
from app.core.settings import TEST_DATABASE_NAME, Settings
from tests.factories import SEED, BaseFactory

BACKEND = Path(__file__).resolve().parents[1]


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
