"""The one-transaction-per-request dependency (`get_session`), through a real app."""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import URL, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionDep, SessionMaker, create_engine
from tests.support.models import Widget

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("support_tables")]


class BoomError(Exception):
    pass


def build_app(sessionmaker: SessionMaker) -> FastAPI:
    app = FastAPI()
    app.state.sessionmaker = sessionmaker

    @app.post("/widgets/{name}")
    async def create(name: str, session: SessionDep) -> dict[str, str]:
        session.add(Widget(name=name))
        return {"name": name}

    @app.post("/widgets/{name}/then-fail")
    async def create_then_fail(name: str, session: SessionDep) -> None:
        session.add(Widget(name=name))
        await session.flush()
        raise BoomError

    @app.post("/duplicate-at-commit")
    async def duplicate(session: SessionDep) -> dict[str, str]:
        # Nothing is flushed here, so the unique violation only surfaces at commit.
        session.add_all([Widget(name="dup"), Widget(name="dup")])
        return {"status": "looks fine"}

    return app


@pytest.fixture
async def client(sessionmaker: SessionMaker) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=build_app(sessionmaker), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


async def widget_names(session: AsyncSession) -> list[str]:
    return list(await session.scalars(select(Widget.name).order_by(Widget.name)))


async def test_successful_request_commits(client: AsyncClient, session: AsyncSession) -> None:
    response = await client.post("/widgets/kept")

    assert response.status_code == 200
    assert await widget_names(session) == ["kept"]


async def test_exception_rolls_back_everything_the_request_did(
    client: AsyncClient, session: AsyncSession
) -> None:
    response = await client.post("/widgets/lost/then-fail")

    assert response.status_code == 500
    assert await widget_names(session) == []


async def test_failed_commit_is_an_error_not_a_success(
    client: AsyncClient, session: AsyncSession
) -> None:
    response = await client.post("/duplicate-at-commit")

    assert response.status_code == 500
    assert await session.scalar(select(func.count()).select_from(Widget)) == 0


async def test_each_request_gets_its_own_transaction(
    client: AsyncClient, session: AsyncSession
) -> None:
    await client.post("/widgets/first")
    await client.post("/widgets/second/then-fail")
    await client.post("/widgets/third")

    assert await widget_names(session) == ["first", "third"]


async def test_a_connection_works_in_utc_whatever_the_servers_zone(test_database_url: URL) -> None:
    """Bug: the session takes the server's zone, so timestamps come back in it (the outside
    review's Package 4 item 1). The database's default stands in for the server's: a client
    setting overrides both. This worker's own database, and its tests run one at a time."""
    engine = create_engine(test_database_url)
    alter = f'ALTER DATABASE "{test_database_url.database}"'
    try:
        async with engine.connect() as admin:
            await admin.execution_options(isolation_level="AUTOCOMMIT")
            await admin.execute(text(f"{alter} SET timezone = 'America/New_York'"))
        await engine.dispose()  # the next connection is new, so it reads the default
        async with engine.connect() as connection:
            zone = await connection.scalar(text("SHOW timezone"))
    finally:
        async with engine.connect() as admin:
            await admin.execution_options(isolation_level="AUTOCOMMIT")
            await admin.execute(text(f"{alter} RESET timezone"))
        await engine.dispose()

    assert zone == "UTC"
