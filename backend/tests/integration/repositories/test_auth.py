"""`AuthRepository`: session rows timed by the database clock, and no expired attributes left
behind on a loaded row (backend/CLAUDE.md, "Async rules")."""

from datetime import timedelta

import pytest
from sqlalchemy import func, inspect, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import UserSession
from app.repositories.auth import AuthRepository
from tests.factories.auth import UserSessionFactory
from tests.factories.user import UserFactory

pytestmark = pytest.mark.anyio


async def test_a_new_session_is_seen_now_and_ends_its_lifetime_from_now(
    session: AsyncSession,
) -> None:
    user = await UserFactory.create_async()

    row = await AuthRepository(session).add_session(user.id, "hash", timedelta(days=30))

    now = (await session.execute(select(func.now()))).scalar_one()
    assert inspect(row).expired_attributes == set()
    assert (row.last_seen_at, row.expires_at) == (now, now + timedelta(days=30))


async def test_touch_leaves_the_loaded_row_current(session: AsyncSession) -> None:
    row = await UserSessionFactory.create_async()
    await session.execute(
        update(UserSession)
        .where(UserSession.id == row.id)
        .values(last_seen_at=func.now() - timedelta(hours=1))
    )
    loaded = await session.scalar(
        select(UserSession)
        .where(UserSession.id == row.id)
        .execution_options(populate_existing=True)
    )
    assert loaded is not None

    await AuthRepository(session).touch(loaded, timedelta(minutes=5))

    now = await session.scalar(select(func.now()))
    assert inspect(loaded).expired_attributes == set()
    assert (loaded.last_seen_at, loaded.updated_at) == (now, now)
