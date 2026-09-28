from fastapi import APIRouter

from app.schemas.health import HealthRead

router = APIRouter(tags=["health"])


@router.get("/health")
async def get_health() -> HealthRead:
    """Liveness check. Database connectivity is added with the database core (S0-C2)."""
    return HealthRead(status="ok")
