from fastapi import APIRouter, Response, status

from app.core.db import SessionMakerDep
from app.schemas.health import HealthRead
from app.services.health import HealthService

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthRead}},
)
async def get_health(sessionmaker: SessionMakerDep, response: Response) -> HealthRead:
    """Liveness and database connectivity. 503 when the database can't be reached."""
    health = await HealthService(sessionmaker).check()
    if health.status != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return health
