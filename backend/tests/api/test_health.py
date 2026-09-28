import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import URL, text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.core.db import SessionMaker, create_engine, create_sessionmaker
from app.core.settings import Settings
from app.main import create_app

pytestmark = pytest.mark.anyio


async def test_health_reports_database_ok(client: AsyncClient) -> None:
    response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


async def test_health_is_503_when_the_database_is_unreachable(settings: Settings) -> None:
    # Port 1 on localhost: nothing listens there, so the connection is refused at once.
    unreachable = URL.create("postgresql+psycopg", host="127.0.0.1", port=1, database="none")
    engine = create_engine(unreachable)
    app = create_app(settings, sessionmaker=create_sessionmaker(engine))
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.get("/api/health")
    finally:
        await engine.dispose()

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unavailable"}


async def test_health_is_503_not_500_when_a_pooled_connection_has_died(
    settings: Settings, connection: AsyncConnection
) -> None:
    """The ping fails mid-request on a dead connection. Pinging on the request's own session
    would leave that transaction invalid, and the request's commit would turn this into a 500."""
    # No pre-ping, so the next request gets the dead pooled connection and fails mid-request.
    engine = create_async_engine(
        settings.test_database_url(), connect_args={"application_name": "health-drop-test"}
    )
    app = create_app(settings, sessionmaker=create_sessionmaker(engine))
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            before = await client.get("/api/health")
            await connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity"
                    " WHERE application_name = 'health-drop-test'"
                )
            )
            after = await client.get("/api/health")
    finally:
        await engine.dispose()

    assert before.status_code == 200
    assert after.status_code == 503
    assert after.json() == {"status": "unavailable", "database": "unavailable"}


async def test_health_is_only_served_under_api_prefix(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 404


async def test_api_docs_are_served_when_enabled(client: AsyncClient) -> None:
    schema = await client.get("/api/openapi.json")
    docs = await client.get("/api/docs")

    assert schema.status_code == docs.status_code == 200
    assert "/api/health" in schema.json()["paths"]


async def test_api_docs_are_not_served_when_disabled(
    settings: Settings, sessionmaker: SessionMaker
) -> None:
    app = create_app(
        settings.model_copy(update={"api_docs_enabled": False}), sessionmaker=sessionmaker
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        schema = await c.get("/api/openapi.json")
        docs = await c.get("/api/docs")

    assert schema.status_code == docs.status_code == 404
