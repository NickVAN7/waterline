import logging

from sqlalchemy.exc import SQLAlchemyError

from app.core.db import SessionMaker
from app.repositories.health import HealthRepository
from app.schemas.health import HealthRead

logger = logging.getLogger(__name__)


class HealthService:
    def __init__(self, sessionmaker: SessionMaker) -> None:
        self.repository = HealthRepository(sessionmaker)

    async def check(self) -> HealthRead:
        try:
            await self.repository.ping()
        # SQLAlchemyError covers driver errors and pool timeouts; OSError, raw socket failures.
        except SQLAlchemyError, OSError:
            logger.warning("health check: database unavailable", exc_info=True)
            return HealthRead(status="unavailable", database="unavailable")
        return HealthRead(status="ok", database="ok")
