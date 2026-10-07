"""`get_by_id` (app/repositories/base.py): get-by-ID is always a query, so the soft-delete
filter applies even to an object already in the session (TD-8)."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import get_by_id
from tests.support.models import Document

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("support_tables")]


async def test_returns_the_row_with_that_id(session: AsyncSession) -> None:
    wanted = Document(title="wanted")
    session.add_all([Document(title="other"), wanted])
    await session.flush()
    session.expunge_all()

    found = await get_by_id(session, Document, wanted.id)

    assert found is not None
    assert found.title == "wanted"


async def test_returns_none_for_an_unknown_id(session: AsyncSession) -> None:
    session.add(Document(title="other"))
    await session.flush()

    assert await get_by_id(session, Document, uuid.uuid7()) is None


async def test_hides_a_row_soft_deleted_earlier_in_the_same_session(
    session: AsyncSession,
) -> None:
    document = Document(title="gone")
    session.add(document)
    await session.flush()
    document.deleted_at = datetime.now(UTC)
    await session.flush()

    # The object is still in the identity map; session.get() would return it.
    assert await get_by_id(session, Document, document.id) is None


async def test_include_deleted_returns_a_soft_deleted_row(session: AsyncSession) -> None:
    document = Document(title="gone")
    session.add(document)
    await session.flush()
    document.deleted_at = datetime.now(UTC)
    await session.flush()

    found = await get_by_id(session, Document, document.id, include_deleted=True)

    assert found is document
