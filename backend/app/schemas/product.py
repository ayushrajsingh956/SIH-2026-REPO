import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ProductListItem(BaseModel):
    id: uuid.UUID
    name: str
    brand: str | None = None
    manufacturer_name: str | None = None
    category: str | None = None
    barcode: str | None = None
    gtin: str | None = None
    first_scanned: datetime
    last_scanned_at: datetime | None = None
    total_scans: int = 0
    compliance_badge: str = "unscanned"  # compliant, non_compliant, needs_review, unscanned
    latest_score: float | None = None
    violations_count: int = 0


class ProductListResponse(BaseModel):
    items: list[ProductListItem]
    total: int
    page: int
    limit: int


class ProductScanViolationSummary(BaseModel):
    id: uuid.UUID
    rule_code: str
    rule_title: str
    citation: str
    severity: str
    field_name: str
    overridden: bool = False


class ProductScanItem(BaseModel):
    id: uuid.UUID
    mode: str
    status: str
    verdict: str | None = None
    compliance_score: float | None = None
    scanned_at: datetime
    inspector_name: str | None = None
    violations: list[ProductScanViolationSummary] = Field(default_factory=list)


class RecurrentViolationItem(BaseModel):
    rule_code: str
    rule_title: str
    citation: str
    severity: str
    count: int
    scan_ids: list[uuid.UUID]


class ProductDetailResponse(BaseModel):
    id: uuid.UUID
    name: str
    brand: str | None = None
    manufacturer_name: str | None = None
    category: str | None = None
    barcode: str | None = None
    gtin: str | None = None
    first_scanned: datetime
    total_scans: int = 0
    compliance_rate: float = 0.0
    is_repeat_offender: bool = False
    recurrent_violations: list[RecurrentViolationItem] = Field(default_factory=list)


class ProductScansResponse(BaseModel):
    product: ProductDetailResponse
    scans: list[ProductScanItem]
    is_repeat_offender: bool
    recurrent_violations: list[RecurrentViolationItem]
