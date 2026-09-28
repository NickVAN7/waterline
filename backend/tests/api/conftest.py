from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import SessionMaker
from app.core.settings import Settings
from app.main import create_app


@pytest.fixture
async def client(settings: Settings, sessionmaker: SessionMaker) -> AsyncIterator[AsyncClient]:
    """The real app, with its per-request sessions joined to the test's transaction."""
    app = create_app(settings, sessionmaker=sessionmaker)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        yield c
