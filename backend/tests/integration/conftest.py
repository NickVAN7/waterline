import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from tests.support.models import SupportBase


@pytest.fixture
async def support_tables(connection: AsyncConnection) -> None:
    """Create the test-only tables inside the test's transaction (rolled back with it)."""
    await connection.run_sync(SupportBase.metadata.create_all)
