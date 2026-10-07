"""`user` constraints and defaults (schema-doc, `user`)."""

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from tests.factories.user import UserFactory

pytestmark = pytest.mark.anyio


async def test_email_is_unique(session: AsyncSession) -> None:
    await UserFactory.create_async(email="ann@example.com")

    with pytest.raises(IntegrityError, match="uq_user_email"):
        await UserFactory.create_async(email="ann@example.com")


async def test_username_is_unique(session: AsyncSession) -> None:
    await UserFactory.create_async(username="ann-lee")

    with pytest.raises(IntegrityError, match="uq_user_username"):
        await UserFactory.create_async(username="ann-lee")


async def test_email_must_be_stored_lowercase(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError, match="ck_user_email_lowercase"):
        await UserFactory.create_async(email="Ann@example.com")


async def test_lowercase_email_is_accepted(session: AsyncSession) -> None:
    await UserFactory.create_async(email="ann@example.com")

    stored = await session.scalar(text('SELECT email FROM "user"'))
    assert stored == "ann@example.com"


async def test_new_user_is_active_and_has_no_flags_by_default(session: AsyncSession) -> None:
    await session.execute(
        text(
            'INSERT INTO "user" (id, email, username, name, hashed_password)'
            " VALUES (gen_random_uuid(), 'ann@example.com', 'ann', 'Ann', 'x')"
        )
    )

    flags = (
        await session.execute(
            select(User.is_active, User.is_system_admin, User.must_change_password)
        )
    ).one()
    assert tuple(flags) == (True, False, False)
