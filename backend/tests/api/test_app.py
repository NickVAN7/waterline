"""The app factory's own database wiring (tests otherwise inject a sessionmaker)."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.pool import QueuePool

from app.core.db import SessionMaker
from app.core.settings import TEST_DATABASE_NAME, Settings
from app.main import create_app

pytestmark = pytest.mark.anyio


def pool_size(engine: AsyncEngine) -> int:
    """Connections sitting idle in the engine's pool."""
    pool = engine.pool
    assert isinstance(pool, QueuePool)
    return pool.checkedin()


async def test_app_owns_an_engine_for_the_configured_database_and_disposes_it(
    settings: Settings,
) -> None:
    # Point the app's own engine at the test database: tests never touch dev data.
    app = create_app(settings.model_copy(update={"postgres_db": TEST_DATABASE_NAME}))
    engine: AsyncEngine = app.state.sessionmaker.kw["bind"]

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.get("/api/health")
        pooled_while_running = pool_size(engine)

    assert response.json()["database"] == "ok"
    assert engine.url.database == TEST_DATABASE_NAME
    assert pooled_while_running == 1
    assert pool_size(engine) == 0


async def test_app_leaves_an_injected_sessionmaker_open(
    settings: Settings, sessionmaker: SessionMaker, session: AsyncSession
) -> None:
    app = create_app(settings, sessionmaker=sessionmaker)

    async with app.router.lifespan_context(app):
        pass

    assert await session.scalar(text("SELECT 1")) == 1
