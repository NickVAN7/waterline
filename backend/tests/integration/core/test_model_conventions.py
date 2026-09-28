"""Enum columns, soft delete, and explicit loading against real Postgres."""

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, InvalidRequestError, StatementError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.base_model import INCLUDE_DELETED
from app.core.db import SessionMaker
from tests.support.models import Document, DocumentStatus, Note

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("support_tables")]


# --- Enums -------------------------------------------------------------------------------


async def test_enum_is_stored_as_its_value_and_read_back_as_a_member(
    session: AsyncSession, sessionmaker: SessionMaker
) -> None:
    session.add(Document(title="a", status=DocumentStatus.IN_REVIEW))
    await session.commit()

    stored = await session.scalar(text("SELECT status FROM support_document"))
    async with sessionmaker() as fresh:
        loaded = await fresh.scalar(select(Document.status))
    assert stored == "in_review"
    assert loaded is DocumentStatus.IN_REVIEW


async def test_database_check_rejects_a_value_outside_the_enum(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError, match="ck_support_document_status"):
        await session.execute(
            text(
                "INSERT INTO support_document (id, title, status, rank, next_note_number, version)"
                " VALUES (gen_random_uuid(), 'a', 'bogus', 'm', 1, 1)"
            )
        )


async def test_orm_rejects_a_string_outside_the_enum_before_the_database(
    session: AsyncSession,
) -> None:
    session.add(Document(title="a", status="bogus"))  # pyright: ignore[reportArgumentType]

    with pytest.raises(StatementError, match="bogus"):
        await session.flush()


async def test_filtering_by_enum_member_matches_stored_rows(session: AsyncSession) -> None:
    session.add_all(
        [
            Document(title="a", status=DocumentStatus.DRAFT),
            Document(title="b", status=DocumentStatus.IN_REVIEW),
        ]
    )
    await session.flush()

    titles = await session.scalars(
        select(Document.title).where(Document.status == DocumentStatus.IN_REVIEW)
    )

    assert list(titles) == ["b"]


# --- Soft delete -----------------------------------------------------------------------------


async def deleted_and_live(session: AsyncSession) -> tuple[Document, Document]:
    live = Document(title="live")
    deleted = Document(title="deleted")
    session.add_all([live, deleted])
    await session.flush()
    await session.execute(
        text("UPDATE support_document SET deleted_at = now() WHERE id = :id"), {"id": deleted.id}
    )
    session.expunge_all()
    return live, deleted


async def test_soft_deleted_rows_are_hidden_from_queries(session: AsyncSession) -> None:
    await deleted_and_live(session)

    titles = await session.scalars(select(Document.title))
    count = await session.scalar(select(func.count()).select_from(Document))

    assert list(titles) == ["live"]
    assert count == 1


async def test_soft_deleted_rows_are_returned_when_the_query_opts_in(
    session: AsyncSession,
) -> None:
    await deleted_and_live(session)

    titles = await session.scalars(
        select(Document.title).order_by(Document.title).execution_options(**{INCLUDE_DELETED: True})
    )

    assert list(titles) == ["deleted", "live"]


async def test_get_by_id_does_not_return_a_soft_deleted_row(session: AsyncSession) -> None:
    _, deleted = await deleted_and_live(session)

    assert await session.get(Document, deleted.id) is None


async def test_soft_deleted_children_are_hidden_from_relationship_loads(
    session: AsyncSession,
) -> None:
    document = Document(title="parent")
    session.add(document)
    await session.flush()
    session.add_all(
        [Note(document_id=document.id, body="kept"), Note(document_id=document.id, body="gone")]
    )
    await session.flush()
    await session.execute(text("UPDATE support_note SET deleted_at = now() WHERE body = 'gone'"))
    session.expunge_all()

    loaded = await session.scalar(select(Document).options(selectinload(Document.notes)))

    assert loaded is not None
    assert [note.body for note in loaded.notes] == ["kept"]


async def test_child_of_a_soft_deleted_parent_loads_without_it_unless_the_query_opts_in(
    session: AsyncSession,
) -> None:
    document = Document(title="parent")
    session.add(document)
    await session.flush()
    session.add(Note(document_id=document.id, body="orphaned"))
    await session.flush()
    await session.execute(text("UPDATE support_document SET deleted_at = now()"))
    session.expunge_all()

    hidden = await session.scalar(select(Note).options(selectinload(Note.document)))
    session.expunge_all()
    shown = await session.scalar(
        select(Note)
        .options(selectinload(Note.document))
        .execution_options(**{INCLUDE_DELETED: True})
    )

    assert hidden is not None
    assert hidden.document is None
    assert shown is not None
    assert shown.document.title == "parent"


# --- Explicit loading --------------------------------------------------------------------


async def test_touching_an_unloaded_relationship_raises(session: AsyncSession) -> None:
    session.add(Document(title="parent"))
    await session.flush()
    session.expunge_all()

    loaded = await session.scalar(select(Document))

    assert loaded is not None
    with pytest.raises(InvalidRequestError, match="lazy='raise'"):
        _ = loaded.notes
