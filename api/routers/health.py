from datetime import datetime

from fastapi import APIRouter

from config import get_settings
from schemas.common import HealthResponse, HealthStatus
from services.health_checks import gather_health

router = APIRouter(prefix="/api/v1", tags=["health"])
settings = get_settings()


@router.get("/health", response_model=HealthResponse)
async def health():
    services = await gather_health()
    overall = "healthy" if all(item.get("status") == "up" for item in services.values()) else "degraded"
    normalized = {
        name: HealthStatus(**value)
        for name, value in services.items()
    }
    return HealthResponse(
        status=overall,
        timestamp=datetime.utcnow(),
        services=normalized,
        version=settings.stack_version,
    )
