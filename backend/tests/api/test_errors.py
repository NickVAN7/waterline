"""A stale version returns 409 in the standard error format."""

import uuid
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.core.base_model import check_version
from app.core.db import SessionDep, SessionMaker
from app.core.errors import register_error_handlers
from tests.support.models import Document

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("support_tables")]

STALE: dict[str, object] = {
    "code": "stale_version",
    "message": "This item was changed by someone else after you loaded it. "
    "Reload it and try again.",
    "details": {},
}


def build_app(sessionmaker: SessionMaker) -> FastAPI:
    app = FastAPI()
    app.state.sessionmaker = sessionmaker
    register_error_handlers(app)

    @app.put("/documents/{document_id}")
    async def rename(
        document_id: uuid.UUID, title: str, version: int, session: SessionDep
    ) -> dict[str, int]:
        document = await session.get_one(Document, document_id)
        check_version(document, version)
        document.title = title
        await session.flush()
        return {"version": document.version}

    @app.put("/documents/{document_id}/racing")
    async def rename_while_someone_else_saves(document_id: uuid.UUID, session: SessionDep) -> None:
        document = await session.get_one(Document, document_id)
        # Another writer bumps the version between this request's load and its commit.
        await session.execute(
            text("UPDATE support_document SET version = version + 1 WHERE id = :id"),
            {"id": document_id},
        )
        document.title = "lost update"

    return app


@pytest.fixture
async def client(sessionmaker: SessionMaker) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=build_app(sessionmaker)), base_url="http://testserver"
    ) as client:
        yield client


@pytest.fixture
async def document_id(sessionmaker: SessionMaker) -> uuid.UUID:
    async with sessionmaker() as session:
        document = Document(title="original")
        session.add(document)
        await session.commit()
    return document.id


async def stored_title(sessionmaker: SessionMaker) -> str | None:
    async with sessionmaker() as session:
        return await session.scalar(select(Document.title))


async def test_update_with_the_current_version_succeeds(
    client: AsyncClient, document_id: uuid.UUID, sessionmaker: SessionMaker
) -> None:
    response = await client.put(f"/documents/{document_id}", params={"title": "new", "version": 1})

    assert response.status_code == 200
    assert response.json() == {"version": 2}
    assert await stored_title(sessionmaker) == "new"


async def test_update_with_an_older_version_is_409_and_changes_nothing(
    client: AsyncClient, document_id: uuid.UUID, sessionmaker: SessionMaker
) -> None:
    await client.put(f"/documents/{document_id}", params={"title": "first", "version": 1})

    response = await client.put(
        f"/documents/{document_id}", params={"title": "second", "version": 1}
    )

    assert response.status_code == 409
    assert response.json() == STALE
    assert await stored_title(sessionmaker) == "first"


async def test_a_write_between_load_and_commit_is_409_and_changes_nothing(
    client: AsyncClient, document_id: uuid.UUID, sessionmaker: SessionMaker
) -> None:
    response = await client.put(f"/documents/{document_id}/racing")

    assert response.status_code == 409
    assert response.json() == STALE
    assert await stored_title(sessionmaker) == "original"
