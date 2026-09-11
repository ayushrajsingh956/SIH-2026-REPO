import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ScanCreateResponse(BaseModel):
    scan_id: str
    status: str = "queued"
    message: str = "Scan initiated successfully"
    images_count: int = 1


class ScanUrlRequest(BaseModel):
    url: str
    font_check_mode: Literal["surface_area", "reference_object", "relative"] = "relative"
    surface_area_cm2: float | None = Field(default=None, ge=0.0)


class ScanDetailResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID | None = None
    scanned_by: uuid.UUID
    mode: str
    status: str
    verdict: str | None = None
    compliance_score: float | None = None
    font_check_mode: str
    surface_area_cm2: float | None = None
    image_urls: list[str]
    presigned_image_urls: list[str] = Field(default_factory=list)
    pipeline_meta: dict[str, Any] | None = None
    scanned_at: datetime
    extraction: dict[str, Any] | None = None
    violations: list[dict[str, Any]] = Field(default_factory=list)


class ScanListResponse(BaseModel):
    items: list[ScanDetailResponse]
    total: int
