import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio


async def test_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_health_is_only_served_under_api_prefix(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 404


async def test_openapi_schema_is_served_under_api_prefix(client: AsyncClient) -> None:
    response = await client.get("/api/openapi.json")

    assert response.status_code == 200
    assert "/api/health" in response.json()["paths"]
