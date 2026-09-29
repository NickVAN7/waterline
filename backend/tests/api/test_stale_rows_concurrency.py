"""A stale save on a versioned row: 409 if someone else changed it, 404 if it's gone (deleted, or
soft-deleted since this request loaded it). Owner decisions in S0-C6's review. Needs real
commits from a second connection, so it uses the `concurrency` fixture."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

import pytest
from fastapi import FastAPI, Query
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.core.base_model import INCLUDE_DELETED
from app.core.db import SessionDep, SessionMaker
from app.core.errors import register_error_handlers
from tests.support.models import Document

pytestmark = [pytest.mark.anyio, pytest.mark.concurrency("support_note", "support_document")]

EDIT = "UPDATE support_document SET version = version + 1 WHERE id = :id"
SOFT_DELETE = "UPDATE support_document SET deleted_at = now(), version = version + 1 WHERE id = :id"
DELETE = "DELETE FROM support_document WHERE id = :id"


def build_app(sessionmaker: SessionMaker) -> FastAPI:
    app = FastAPI()
    app.state.sessionmaker = sessionmaker
    register_error_handlers(app)

    async def meanwhile(sql: str, document_id: uuid.UUID) -> None:
        """Someone else, on their own connection, writes the row and commits."""
        async with sessionmaker() as other:
            await other.execute(text(sql), {"id": document_id})
            await other.commit()

    @app.put("/documents/rename")
    async def rename(
        ids: Annotated[list[uuid.UUID], Query()], change_first: str, session: SessionDep
    ) -> None:
        """Load the documents, let someone else change the first one, then rename them all in
        one flush."""
        documents = [await session.get_one(Document, document_id) for document_id in ids]
        await meanwhile(change_first, ids[0])
        for document in documents:
            document.title = "renamed"
        await session.flush()

    @app.put("/documents/{document_id}/restore")
    async def restore(document_id: uuid.UUID, session: SessionDep) -> None:
        """Restore a soft-deleted document while someone else bumps its version."""
        document = (
            await session.scalars(
                select(Document)
                .where(Document.id == document_id)
                .execution_options(**{INCLUDE_DELETED: True})
            )
        ).one()
        await meanwhile(EDIT, document_id)
        document.deleted_at = None
        await session.flush()

    return app


async def saved_document(sessionmaker: SessionMaker, *, deleted: bool = False) -> uuid.UUID:
    async with sessionmaker() as session:
        document = Document(title="original", deleted_at=datetime.now(UTC) if deleted else None)
        session.add(document)
        await session.commit()
    return document.id


async def stored_titles(sessionmaker: SessionMaker) -> set[str]:
    """Every stored title, soft-deleted rows included."""
    async with sessionmaker() as session:
        query = select(Document.title).execution_options(**{INCLUDE_DELETED: True})
        return set(await session.scalars(query))


async def put(app: FastAPI, url: str, **params: str | list[str]) -> tuple[int, str]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        response = await c.put(url, params=params)
    return response.status_code, response.json()["code"]


@pytest.mark.parametrize(
    ("change", "status", "code", "titles"),
    [
        (EDIT, 409, "stale_version", {"original"}),  # changed: reload and retry
        (SOFT_DELETE, 404, "not_found", {"original"}),  # deleted meanwhile: gone for the user
        (DELETE, 404, "not_found", set[str]()),  # hard-deleted: gone
    ],
    ids=["edited", "soft-deleted", "deleted"],
)
async def test_stale_save_is_409_if_the_row_changed_and_404_if_it_is_gone(
    committed_support_tables: None,
    concurrency: SessionMaker,
    change: str,
    status: int,
    code: str,
    titles: set[str],
) -> None:
    document_id = await saved_document(concurrency)

    result = await put(
        build_app(concurrency), "/documents/rename", ids=[str(document_id)], change_first=change
    )

    assert result == (status, code)
    assert await stored_titles(concurrency) == titles  # the rename never landed


async def test_one_gone_row_among_several_in_the_flush_is_404(
    committed_support_tables: None, concurrency: SessionMaker
) -> None:
    gone = await saved_document(concurrency)
    kept = await saved_document(concurrency)

    result = await put(
        build_app(concurrency), "/documents/rename", ids=[str(gone), str(kept)], change_first=DELETE
    )

    assert result == (404, "not_found")


async def test_version_race_while_restoring_a_soft_deleted_row_is_409_not_404(
    committed_support_tables: None, concurrency: SessionMaker
) -> None:
    """The row was already soft-deleted when loaded, so still being soft-deleted after the
    rollback doesn't make it "gone": this is a real conflict."""
    document_id = await saved_document(concurrency, deleted=True)

    result = await put(build_app(concurrency), f"/documents/{document_id}/restore")

    assert result == (409, "stale_version")
