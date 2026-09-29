"""Optimistic locking and the direct-update helper (design-doc §3)."""

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.core.base_model import StaleVersionError, check_version
from app.core.db import SessionMaker
from app.repositories.base import direct_update
from tests.support.models import Document

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("support_tables")]


async def stored_version(session: AsyncSession) -> int | None:
    return await session.scalar(text("SELECT version FROM support_document"))


async def saved_document(sessionmaker: SessionMaker) -> Document:
    async with sessionmaker() as session:
        document = Document(title="original")
        session.add(document)
        await session.commit()
    return document


async def test_version_starts_at_1_and_increments_on_each_update(session: AsyncSession) -> None:
    document = Document(title="a")
    session.add(document)
    await session.flush()
    first = await stored_version(session)

    document.title = "b"
    await session.flush()

    assert first == 1
    assert await stored_version(session) == 2


async def test_saving_over_a_newer_version_raises(sessionmaker: SessionMaker) -> None:
    document = await saved_document(sessionmaker)
    async with sessionmaker() as alice, sessionmaker() as bob:
        mine = await alice.get_one(Document, document.id)
        theirs = await bob.get_one(Document, document.id)
        theirs.title = "bob's edit"
        await bob.commit()

        mine.title = "alice's edit"
        with pytest.raises(StaleDataError):
            await alice.flush()


async def test_check_version_accepts_the_current_version(session: AsyncSession) -> None:
    document = Document(title="a")
    session.add(document)
    await session.flush()

    check_version(document, 1)  # no exception


async def test_check_version_rejects_an_older_copy(session: AsyncSession) -> None:
    document = Document(title="a")
    session.add(document)
    await session.flush()
    document.title = "b"
    await session.flush()

    with pytest.raises(StaleVersionError, match="at version 2, not 1"):
        check_version(document, 1)


async def test_direct_update_does_not_bump_the_version(session: AsyncSession) -> None:
    document = Document(title="a")
    session.add(document)
    await session.flush()

    await direct_update(session, Document, document.id, {"rank": "b"}, touch_updated_at=False)

    row = (await session.execute(text("SELECT rank, version FROM support_document"))).one()
    assert tuple(row) == ("b", 1)


async def test_direct_update_does_not_make_a_concurrent_content_edit_stale(
    sessionmaker: SessionMaker,
) -> None:
    document = await saved_document(sessionmaker)
    async with sessionmaker() as editor, sessionmaker() as mover:
        editing = await editor.get_one(Document, document.id)
        await direct_update(mover, Document, document.id, {"rank": "z"}, touch_updated_at=False)
        await mover.commit()

        editing.title = "edited"
        await editor.flush()  # no StaleDataError: the move didn't bump the version

        row = (
            await editor.execute(text("SELECT title, rank, version FROM support_document"))
        ).one()
    assert tuple(row) == ("edited", "z", 2)


async def test_direct_update_returns_values_computed_by_the_database(session: AsyncSession) -> None:
    document = Document(title="a")
    session.add(document)
    await session.flush()

    counter = {"next_note_number": Document.next_note_number + 1}
    first = await direct_update(session, Document, document.id, counter, touch_updated_at=True)
    second = await direct_update(session, Document, document.id, counter, touch_updated_at=True)

    assert (first, second) == ({"next_note_number": 2}, {"next_note_number": 3})


async def _backdated_document(session: AsyncSession) -> Document:
    """A saved document whose `updated_at` is a day old, reloaded so the object holds that value.
    now() is fixed within a transaction, so without this a change to it couldn't be seen."""
    document = Document(title="a")
    session.add(document)
    await session.flush()
    await session.execute(text("UPDATE support_document SET updated_at = now() - interval '1 day'"))
    session.expunge_all()
    return await session.get_one(Document, document.id)


async def test_counter_write_moves_updated_at_and_leaves_the_object_readable(
    session: AsyncSession,
) -> None:
    document = await _backdated_document(session)
    backdated = document.updated_at

    await direct_update(
        session,
        Document,
        document.id,
        {"next_note_number": Document.next_note_number + 1},
        touch_updated_at=True,
    )

    stored = await session.scalar(text("SELECT updated_at FROM support_document"))
    assert inspect(document).expired_attributes == set()  # no lazy load needed for any read
    assert (document.next_note_number, document.version) == (2, 1)
    assert document.updated_at == stored
    assert document.updated_at > backdated


async def test_rank_write_leaves_updated_at_alone_and_the_object_readable(
    session: AsyncSession,
) -> None:
    """Owner decision (TD-7): a display-order change isn't an edit, so `updated_at` stays."""
    document = await _backdated_document(session)
    backdated = document.updated_at

    await direct_update(session, Document, document.id, {"rank": "b"}, touch_updated_at=False)

    stored = await session.scalar(text("SELECT updated_at FROM support_document"))
    assert inspect(document).expired_attributes == set()
    assert (document.rank, document.version) == ("b", 1)
    assert stored == backdated
    assert document.updated_at == backdated


async def test_direct_update_of_a_missing_row_returns_none(session: AsyncSession) -> None:
    document = Document(title="never saved")

    assert (
        await direct_update(session, Document, document.id, {"rank": "b"}, touch_updated_at=False)
        is None
    )
    assert await session.scalar(select(Document.id)) is None
