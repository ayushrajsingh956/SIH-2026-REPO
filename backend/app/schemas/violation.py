import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ViolationListItem(BaseModel):
    id: uuid.UUID
    scan_id: uuid.UUID
    rule_code: str
    rule_title: str
    citation: str
    severity: str
    field_name: str
    observed_value: str | None = None
    expected_value: str | None = None
    bbox: dict[str, Any] | None = None
    overridden: bool = False
    override_reason: str | None = None
    scanned_at: datetime
    mode: str
    district: str | None = None
    state: str | None = None
    product_name: str | None = None


class ViolationListResponse(BaseModel):
    items: list[ViolationListItem]
    total: int
    page: int
    limit: int
    severity_summary: dict[str, int] = Field(default_factory=dict)
