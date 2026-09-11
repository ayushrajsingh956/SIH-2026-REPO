from datetime import datetime

from pydantic import BaseModel, Field


class DashboardSummaryResponse(BaseModel):
    total_scans: int = Field(..., description="Total scans in selected period")
    compliant_scans: int = Field(..., description="Number of compliant scans")
    non_compliant_scans: int = Field(..., description="Number of non-compliant scans")
    needs_review_scans: int = Field(..., description="Number of scans requiring manual review")
    compliance_rate: float = Field(..., description="Percentage of compliant scans (0-100)")
    avg_compliance_score: float = Field(..., description="Average compliance score across scans")
    pending_reviews: int = Field(..., description="Scans currently awaiting officer action")
    total_violations: int = Field(..., description="Total statutory violations detected")
    critical_violations: int = Field(..., description="Critical severity violations detected")
    scans_comparison_pct: float | None = Field(
        None, description="Percentage change compared to previous period"
    )


class ViolationsByRuleItem(BaseModel):
    rule_code: str
    rule_title: str
    citation: str
    severity: str
    count: int


class ViolationsBySeverityItem(BaseModel):
    severity: str
    count: int
    percentage: float


class ComplianceTrendItem(BaseModel):
    date: str
    total_scans: int
    compliant_scans: int
    non_compliant_scans: int
    compliance_rate: float
    avg_score: float


class DistrictHeatItem(BaseModel):
    district: str
    state: str
    total_scans: int
    compliant_scans: int
    compliance_rate: float
    critical_violations: int
    last_activity: datetime | None = None
