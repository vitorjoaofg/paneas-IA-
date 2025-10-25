from datetime import datetime
from typing import Any, Dict

from pydantic import BaseModel


class HealthStatus(BaseModel):
    status: str
    latency_ms: int | None = None
    details: Dict[str, Any] | None = None


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    services: Dict[str, HealthStatus]
    version: str
