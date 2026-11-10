"""The auth service's paths the API can't reach in order (design-doc §4, "Sessions")."""

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import UnauthorizedError
from app.core.security import generate_token, hash_token
from app.core.settings import Settings
from app.models.audit_event import AuditEvent
from app.models.auth import UserSession
from app.services.auth import AuthService
from tests.factories.auth import UserSessionFactory
from tests.factories.user import FACTORY_PASSWORD, UserFactory

pytestmark = [pytest.mark.anyio, pytest.mark.security]


async def test_sign_out_others_is_401_once_this_session_is_gone(
    session: AsyncSession, settings: Settings
) -> None:
    """A session signed out by another request after this one authenticated: a 401, nothing
    deleted, and no event, not a 500 on the missing row (DL-298)."""
    user = await UserFactory.create_async()
    token = generate_token()
    await UserSessionFactory.create_async(user=user, token_hash=hash_token(token))
    other = await UserSessionFactory.create_async(user=user)
    await session.execute(delete(UserSession).where(UserSession.token_hash == hash_token(token)))

    with pytest.raises(UnauthorizedError):
        await AuthService(session, settings).sign_out_others(user, token)

    assert list(await session.scalars(select(UserSession.id))) == [other.id]
    assert (await session.scalars(select(AuditEvent))).all() == []


async def test_change_password_is_401_once_this_session_is_gone(
    session: AsyncSession, settings: Settings
) -> None:
    """The same race on a password change (design-doc §4): a 401, not a 500, and the other
    session left alone."""
    user = await UserFactory.create_async()
    token = generate_token()
    await UserSessionFactory.create_async(user=user, token_hash=hash_token(token))
    other = await UserSessionFactory.create_async(user=user)
    await session.execute(delete(UserSession).where(UserSession.token_hash == hash_token(token)))

    with pytest.raises(UnauthorizedError):
        await AuthService(session, settings).change_password(
            user, token, FACTORY_PASSWORD, "a brand new passphrase"
        )

    assert list(await session.scalars(select(UserSession.id))) == [other.id]
