"""Every error response has the standard `{code, message, details}` body (build-plan, "API
foundations"): app errors, request validation, Starlette's own errors, and stale rows (409 for
a version conflict, 404 for a non-versioned row that's gone)."""

import uuid
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.base_model import check_version
from app.core.db import SessionDep, SessionMaker
from app.core.errors import ForbiddenError, NotFoundError, register_error_handlers
from tests.support.models import Document, Widget

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

    @app.put("/widgets/{widget_id}/racing-delete")
    async def rename_while_someone_else_deletes(widget_id: uuid.UUID, session: SessionDep) -> None:
        widget = await session.get_one(Widget, widget_id)
        # Another request hard-deletes the (non-versioned) row between load and flush.
        await session.execute(text("DELETE FROM support_widget WHERE id = :id"), {"id": widget_id})
        widget.name = "renamed"
        await session.flush()

    @app.get("/missing")
    async def missing() -> None:
        raise NotFoundError

    @app.get("/locked")
    async def locked() -> None:
        raise ForbiddenError(
            "Change your password first.",
            code="password_change_required",
            details={"next": "change-password"},
        )

    @app.get("/teapot")
    async def teapot() -> None:
        raise StarletteHTTPException(status_code=418, detail="I'm a teapot.")

    @app.post("/widgets")
    async def create_widget(name: str, quantity: int) -> dict[str, str]:
        return {"name": name, "quantity": str(quantity)}

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


async def test_not_found_error_is_404_in_the_standard_format(client: AsyncClient) -> None:
    response = await client.get("/missing")

    assert response.status_code == 404
    assert response.json() == {"code": "not_found", "message": "Not found.", "details": {}}


async def test_forbidden_error_keeps_its_specific_code_message_and_details(
    client: AsyncClient,
) -> None:
    response = await client.get("/locked")

    assert response.status_code == 403
    assert response.json() == {
        "code": "password_change_required",
        "message": "Change your password first.",
        "details": {"next": "change-password"},
    }


async def test_invalid_request_is_422_with_one_entry_per_field(client: AsyncClient) -> None:
    response = await client.post("/widgets", params={"quantity": "many"})

    assert response.status_code == 422
    body = response.json()
    assert (body["code"], body["message"]) == ("validation_error", "The request is invalid.")
    assert body["details"]["fields"] == [
        {"loc": ["query", "name"], "message": "Field required", "type": "missing"},
        {
            "loc": ["query", "quantity"],
            "message": "Input should be a valid integer, unable to parse string as an integer",
            "type": "int_parsing",
        },
    ]


async def test_unknown_route_is_404_in_the_standard_format(client: AsyncClient) -> None:
    response = await client.get("/no-such-route")

    assert response.status_code == 404
    assert response.json() == {"code": "not_found", "message": "Not found.", "details": {}}


async def test_wrong_method_is_405_and_keeps_the_allow_header(client: AsyncClient) -> None:
    response = await client.delete("/missing")

    assert response.status_code == 405
    assert response.json() == {
        "code": "method_not_allowed",
        "message": "Method not allowed.",
        "details": {},
    }
    assert response.headers["allow"] == "GET"


@pytest.fixture
async def widget_id(sessionmaker: SessionMaker) -> uuid.UUID:
    async with sessionmaker() as session:
        widget = Widget(name="original")
        session.add(widget)
        await session.commit()
    return widget.id


async def test_update_of_a_non_versioned_row_deleted_meanwhile_is_404_not_409(
    client: AsyncClient, widget_id: uuid.UUID, sessionmaker: SessionMaker
) -> None:
    response = await client.put(f"/widgets/{widget_id}/racing-delete")

    assert response.status_code == 404
    assert response.json() == {"code": "not_found", "message": "Not found.", "details": {}}
    async with sessionmaker() as session:
        # The request rolled back as a whole: the rename was never applied.
        assert await session.scalar(select(Widget.name)) == "original"


async def test_other_http_errors_keep_their_status_and_detail(client: AsyncClient) -> None:
    """Any other Starlette/FastAPI HTTP error (e.g. a security dependency's 401 from Slice 1)
    keeps its status, with `http_error` and its detail as the message."""
    response = await client.get("/teapot")

    assert response.status_code == 418
    assert response.json() == {"code": "http_error", "message": "I'm a teapot.", "details": {}}
