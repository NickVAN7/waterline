import logging

from sqlalchemy.exc import SQLAlchemyError

from app.core.db import SessionMaker
from app.core.errors import ServiceUnavailableError
from app.repositories.health import HealthRepository
from app.schemas.health import HealthRead

logger = logging.getLogger(__name__)


class HealthService:
    def __init__(self, sessionmaker: SessionMaker) -> None:
        self.repository = HealthRepository(sessionmaker)

    async def check(self) -> HealthRead:
        """Raises `ServiceUnavailableError` (503) when the database can't be reached."""
        try:
            await self.repository.ping()
        # SQLAlchemyError covers driver errors and pool timeouts; OSError, raw socket failures.
        except SQLAlchemyError, OSError:
            logger.warning("health check: database unavailable", exc_info=True)
            raise ServiceUnavailableError(
                "The database is unavailable.", details={"database": "unavailable"}
            ) from None
        return HealthRead(status="ok", database="ok")
