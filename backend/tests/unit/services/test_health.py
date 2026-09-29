import pytest
from sqlalchemy import URL, exc

from app.core.db import create_engine, create_sessionmaker
from app.core.errors import ServiceUnavailableError
from app.repositories.health import HealthRepository
from app.services.health import HealthService

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(exc.OperationalError("SELECT 1", {}, Exception("gone")), id="driver-error"),
        pytest.param(exc.TimeoutError("QueuePool limit reached"), id="pool-timeout"),
        pytest.param(ConnectionResetError("reset"), id="socket-error"),
    ],
)
async def test_database_failures_raise_service_unavailable(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    async def fail(self: HealthRepository) -> None:
        raise error

    monkeypatch.setattr(HealthRepository, "ping", fail)
    # Creating an engine doesn't connect; ping is replaced, so no database is needed.
    engine = create_engine(URL.create("postgresql+psycopg", host="localhost", database="x"))

    with pytest.raises(ServiceUnavailableError, match=r"^The database is unavailable\.$") as raised:
        await HealthService(create_sessionmaker(engine)).check()

    assert raised.value.details == {"database": "unavailable"}
