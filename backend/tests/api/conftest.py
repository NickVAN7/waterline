from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionMaker
from app.core.settings import Settings
from app.main import create_app
from app.services import roster
from app.services.roster import MemberRemoval
from tests.support.api import api_client


@pytest.fixture
async def client(settings: Settings, sessionmaker: SessionMaker) -> AsyncIterator[AsyncClient]:
    """The real app, with its per-request sessions joined to the test's transaction."""
    app = create_app(settings, sessionmaker=sessionmaker)
    async with api_client(app) as c:
        yield c


@pytest.fixture
def removals(monkeypatch: pytest.MonkeyPatch) -> list[MemberRemoval]:
    """What the `on_member_removed` handler receives: the project area registers the real one in
    S1-C12; this stands in for it."""
    calls: list[MemberRemoval] = []

    async def handler(_session: AsyncSession, removal: MemberRemoval) -> None:
        calls.append(removal)

    monkeypatch.setattr(roster, "_ON_MEMBER_REMOVED", [handler])
    return calls
