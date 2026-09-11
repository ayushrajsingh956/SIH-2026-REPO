from typing import Any, Literal

from pydantic import BaseModel, Field


class RuleDefinitionSchema(BaseModel):
    id: str = Field(..., description="Unique rule code (e.g. LMPC-R6-1a)")
    title: str = Field(..., description="Short descriptive rule title")
    citation: str = Field(..., description="Verbatim legal citation under LMPC Rules, 2011")
    severity: Literal["critical", "major", "minor", "advisory"]
    applies_to: list[str] = Field(
        default_factory=lambda: ["retail", "wholesale", "imported", "ecommerce"]
    )
    check: str = Field(..., description="Validator type name registered in validator registry")
    params: dict[str, Any] = Field(default_factory=dict)
    description_plain: str = Field(..., description="Plain language explanation of requirement")
    mandatory: bool = Field(default=True)


class RuleResponse(BaseModel):
    id: str
    title: str
    citation: str
    severity: str
    effective_severity: str
    applies_to: list[str]
    check: str
    params: dict[str, Any]
    description_plain: str
    mandatory: bool
    is_enabled: bool = True
    severity_override: str | None = None
    trigger_count: int = 0


class RuleAdminUpdateRequest(BaseModel):
    is_enabled: bool | None = None
    severity_override: Literal["critical", "major", "minor", "advisory", ""] | None = None


class ViolationOverrideRequest(BaseModel):
    reason: str = Field(..., min_length=5, description="Inspector justification for override")


class ViolationResponse(BaseModel):
    id: str
    scan_id: str
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


class ScanExtractionUpdateRequest(BaseModel):
    fields: dict[str, Any]
