"""The app factory's own database wiring (tests otherwise inject a sessionmaker)."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.pool import QueuePool

from app.core.base_model import StaleVersionError
from app.core.db import SessionMaker
from app.core.errors import NotFoundError
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


async def test_app_returns_409_for_a_stale_version(
    settings: Settings, sessionmaker: SessionMaker
) -> None:
    app = create_app(settings, sessionmaker=sessionmaker)

    @app.get("/stale")
    async def stale() -> None:
        raise StaleVersionError("Document is at version 2, not 1")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        response = await c.get("/stale")

    assert response.status_code == 409
    assert response.json()["code"] == "stale_version"


async def test_app_returns_the_standard_error_body_for_every_kind_of_error(
    settings: Settings, sessionmaker: SessionMaker
) -> None:
    """create_app registers every handler: app errors, request validation, Starlette's own."""
    app = create_app(settings, sessionmaker=sessionmaker)

    @app.get("/gone")
    async def gone() -> None:
        raise NotFoundError

    @app.get("/count")
    async def count(n: int) -> int:
        return n

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        app_error = await c.get("/gone")
        invalid = await c.get("/count", params={"n": "x"})
        unknown = await c.get("/api/no-such-route")

    assert (app_error.status_code, app_error.json()["code"]) == (404, "not_found")
    assert (invalid.status_code, invalid.json()["code"]) == (422, "validation_error")
    assert (unknown.status_code, unknown.json()["code"]) == (404, "not_found")
