from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class ServiceStatus(BaseModel):
    status: str
    latency_ms: float | None = None
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str = Field(..., description="Overall health: 'ok' or 'unhealthy'")
    version: str = "0.1.0"
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    dependencies: dict[str, Any]
