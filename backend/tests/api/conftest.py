from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient

from app.core.db import SessionMaker
from app.core.settings import Settings
from app.main import create_app
from tests.support.api import api_client


@pytest.fixture
async def client(settings: Settings, sessionmaker: SessionMaker) -> AsyncIterator[AsyncClient]:
    """The real app, with its per-request sessions joined to the test's transaction."""
    app = create_app(settings, sessionmaker=sessionmaker)
    async with api_client(app) as c:
        yield c
