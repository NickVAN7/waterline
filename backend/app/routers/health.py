from fastapi import APIRouter, status

from app.core.db import SessionMakerDep
from app.core.errors import ErrorBody
from app.schemas.health import HealthRead
from app.services.health import HealthService

router = APIRouter(tags=["health"])


@router.get("/health", responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorBody}})
async def get_health(sessionmaker: SessionMakerDep) -> HealthRead:
    """Liveness and database connectivity. 503 (`service_unavailable`) when the database can't
    be reached."""
    return await HealthService(sessionmaker).check()
