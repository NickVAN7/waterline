"""`session` constraints (schema-doc, `session`)."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories.auth import UserSessionFactory

pytestmark = pytest.mark.anyio


async def test_token_hash_is_unique(session: AsyncSession) -> None:
    await UserSessionFactory.create_async(token_hash="a" * 64)

    with pytest.raises(IntegrityError, match="uq_session_token_hash"):
        await UserSessionFactory.create_async(token_hash="a" * 64)
