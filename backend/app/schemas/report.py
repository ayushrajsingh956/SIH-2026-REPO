import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ReportListItem(BaseModel):
    id: uuid.UUID
    scan_id: uuid.UUID
    pdf_url: str | None = None
    docx_url: str | None = None
    generated_by: uuid.UUID
    generator_name: str | None = None
    generated_at: datetime
    product_name: str | None = None
    scan_verdict: str | None = None
    scan_score: float | None = None


class ReportListResponse(BaseModel):
    items: list[ReportListItem]
    total: int
    page: int
    limit: int


class ReportGenerateRequest(BaseModel):
    scan_id: uuid.UUID


class ReportDownloadResponse(BaseModel):
    report_id: uuid.UUID
    scan_id: uuid.UUID
    format: str = Field(..., description="File format: pdf or docx")
    download_url: str = Field(..., description="5-minute presigned download URL")
    expires_in: int = Field(300, description="Expiration in seconds (300 seconds / 5 minutes)")
    filename: str = Field(..., description="Recommended statutory file name")
