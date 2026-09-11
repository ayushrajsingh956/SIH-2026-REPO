import datetime
import logging
import re
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.extraction import ExtractionFields, TextBlock
from app.schemas.rule import RuleDefinitionSchema

logger = logging.getLogger(__name__)


class ViolationData(BaseModel):
    rule_code: str
    rule_title: str
    citation: str
    severity: str
    field_name: str
    observed_value: str | None = None
    expected_value: str | None = None
    bbox: dict[str, Any] | None = None


class ValidationContext(BaseModel):
    scan_mode: str = "retail"
    surface_area_cm2: float | None = None
    font_check_mode: str = "relative"
    detected_text_blocks: list[TextBlock] = Field(default_factory=list)
    raw_text: str | None = None
    rule_overrides: dict[str, Any] | None = None


class BaseValidator(ABC):
    @abstractmethod
    def validate(
        self,
        rule: RuleDefinitionSchema,
        fields: ExtractionFields,
        context: ValidationContext,
    ) -> list[ViolationData]:
        pass


def _has_val(val: Any) -> bool:
    if val is None:
        return False
    if isinstance(val, str):
        return bool(val.strip())
    return True


class PresenceValidator(BaseValidator):
    def validate(
        self,
        rule: RuleDefinitionSchema,
        fields: ExtractionFields,
        context: ValidationContext,
    ) -> list[ViolationData]:
        violations: list[ViolationData] = []
        field_name = rule.params.get("field")
        if not field_name:
            return violations

        field_obj = getattr(fields, field_name, None)
        is_missing = False
        observed = "Missing"

        if field_obj is None:
            is_missing = True
        else:
            present = getattr(field_obj, "present", True)
            if not present:
                is_missing = True
            else:
                if field_name == "manufacturer_name":
                    raw = getattr(field_obj, "raw", None)
                    norm = getattr(field_obj, "normalized", None)
                    if not _has_val(raw) and not _has_val(norm):
                        is_missing = True
                    # Check secondary field if specified
                    sec_name = rule.params.get("secondary_field")
                    if sec_name:
                        sec_obj = getattr(fields, sec_name, None)
                        if not sec_obj or not (
                            _has_val(getattr(sec_obj, "raw", None))
                            or _has_val(getattr(sec_obj, "normalized", None))
                        ):
                            is_missing = True
                            observed = "Incomplete (Missing Address)"
                elif field_name == "net_quantity":
                    val = getattr(field_obj, "value", None)
                    raw = getattr(field_obj, "raw", None)
                    if val is None and not _has_val(raw):
                        is_missing = True
                elif field_name == "mrp":
                    val = getattr(field_obj, "value", None)
                    raw = getattr(field_obj, "raw", None)
                    if val is None and not _has_val(raw):
                        is_missing = True
                elif field_name == "mfg_date":
                    month = getattr(field_obj, "month", None)
                    year = getattr(field_obj, "year", None)
                    raw = getattr(field_obj, "raw", None)
                    if month is None and year is None and not _has_val(raw):
                        is_missing = True
                elif field_name == "consumer_care":
                    phone = getattr(field_obj, "phone", [])
                    email = getattr(field_obj, "email", None)
                    addr = getattr(field_obj, "address", None)
                    raw = getattr(field_obj, "raw", None)
                    if (
                        not phone
                        and not _has_val(email)
                        and not _has_val(addr)
                        and not _has_val(raw)
                    ):
                        is_missing = True
                elif field_name == "country_of_origin":
                    raw = getattr(field_obj, "raw", None)
                    norm = getattr(field_obj, "normalized", None)
                    if not _has_val(raw) and not _has_val(norm):
                        is_missing = True
                else:
                    raw = getattr(field_obj, "raw", None)
                    norm = getattr(field_obj, "normalized", None)
                    if not _has_val(raw) and not _has_val(norm):
                        is_missing = True

        if is_missing:
            bbox_coords = getattr(field_obj, "bbox", None) if field_obj else None
            bbox_dict = {"coords": bbox_coords} if bbox_coords else None
            violations.append(
                ViolationData(
                    rule_code=rule.id,
                    rule_title=rule.title,
                    citation=rule.citation,
                    severity=rule.severity,
                    field_name=field_name,
                    observed_value=observed,
                    expected_value=f"Visible and legible declaration of {field_name.replace('_', ' ')}",
                    bbox=bbox_dict,
                )
            )

        return violations


class RegexFormatValidator(BaseValidator):
    def validate(
        self,
        rule: RuleDefinitionSchema,
        fields: ExtractionFields,
        context: ValidationContext,
    ) -> list[ViolationData]:
        violations: list[ViolationData] = []
        field_name = rule.params.get("field")
        pattern = rule.params.get("pattern")
        if not field_name or not pattern:
            return violations

        field_obj = getattr(fields, field_name, None)
        if not field_obj or not getattr(field_obj, "present", True):
            return violations

        text = getattr(field_obj, "normalized", None) or getattr(field_obj, "raw", None) or ""
        if not text.strip():
            return violations

        if not re.search(pattern, text, re.IGNORECASE):
            bbox_coords = getattr(field_obj, "bbox", None)
            bbox_dict = {"coords": bbox_coords} if bbox_coords else None
            violations.append(
                ViolationData(
                    rule_code=rule.id,
                    rule_title=rule.title,
                    citation=rule.citation,
                    severity=rule.severity,
                    field_name=field_name,
                    observed_value=text,
                    expected_value=rule.params.get(
                        "expected_format", f"Value matching pattern: {pattern}"
                    ),
                    bbox=bbox_dict,
                )
            )
        return violations


class DateValidNotFutureValidator(BaseValidator):
    def validate(
        self,
        rule: RuleDefinitionSchema,
        fields: ExtractionFields,
        context: ValidationContext,
    ) -> list[ViolationData]:
        violations: list[ViolationData] = []
        field_name = rule.params.get("field", "mfg_date")
        field_obj = getattr(fields, field_name, None)
        if not field_obj or not getattr(field_obj, "present", True):
            return violations

        month = getattr(field_obj, "month", None)
        year = getattr(field_obj, "year", None)
        raw = getattr(field_obj, "raw", None)

        now = datetime.datetime.now(datetime.UTC)
        curr_year = now.year
        curr_month = now.month
        tolerance = int(rule.params.get("tolerance_months", 1))

        # If month and year are parsed
        if month is not None or year is not None:
            if month is not None and (month < 1 or month > 12):
                violations.append(
                    ViolationData(
                        rule_code=rule.id,
                        rule_title=rule.title,
                        citation=rule.citation,
                        severity=rule.severity,
                        field_name=field_name,
                        observed_value=f"Month {month} (Year {year})",
                        expected_value="Valid month between 01 and 12",
                    )
                )
                return violations

            if year is not None:
                # 2-digit year conversion if needed
                y = year + 2000 if year < 100 else year
                if y < 2000 or y > curr_year + 5:
                    violations.append(
                        ViolationData(
                            rule_code=rule.id,
                            rule_title=rule.title,
                            citation=rule.citation,
                            severity=rule.severity,
                            field_name=field_name,
                            observed_value=f"Year {year}",
                            expected_value=f"Reasonable manufacture year between 2000 and {curr_year}",
                        )
                    )
                    return violations

                m = month if month is not None else 1
                # Check future date
                future_limit_month = curr_month + tolerance
                future_limit_year = curr_year
                if future_limit_month > 12:
                    future_limit_year += 1
                    future_limit_month -= 12

                if (y > future_limit_year) or (y == future_limit_year and m > future_limit_month):
                    violations.append(
                        ViolationData(
                            rule_code=rule.id,
                            rule_title=rule.title,
                            citation=rule.citation,
                            severity=rule.severity,
                            field_name=field_name,
                            observed_value=f"{m:02d}/{y}",
                            expected_value=f"Date on or before {curr_month:02d}/{curr_year} (+{tolerance}m packing allowance)",
                        )
                    )
                    return violations

        elif raw and raw.strip():
            # Fallback regex search on raw date string
            match = re.search(r"\b(\d{1,2})[/\-\.](\d{2,4})\b", raw)
            if match:
                m = int(match.group(1))
                y = int(match.group(2))
                y = y + 2000 if y < 100 else y
                if m < 1 or m > 12:
                    violations.append(
                        ViolationData(
                            rule_code=rule.id,
                            rule_title=rule.title,
                            citation=rule.citation,
                            severity=rule.severity,
                            field_name=field_name,
                            observed_value=f"Invalid month {m} in '{raw}'",
                            expected_value="Valid month between 01 and 12",
                        )
                    )
                    return violations
                if y < 2000 or y > curr_year + 5:
                    violations.append(
                        ViolationData(
                            rule_code=rule.id,
                            rule_title=rule.title,
                            citation=rule.citation,
                            severity=rule.severity,
                            field_name=field_name,
                            observed_value=f"Year {y}",
                            expected_value=f"Reasonable manufacture year between 2000 and {curr_year}",
                        )
                    )
                    return violations
                future_limit_month = curr_month + tolerance
                future_limit_year = curr_year
                if future_limit_month > 12:
                    future_limit_year += 1
                    future_limit_month -= 12
                if (y > future_limit_year) or (y == future_limit_year and m > future_limit_month):
                    violations.append(
                        ViolationData(
                            rule_code=rule.id,
                            rule_title=rule.title,
                            citation=rule.citation,
                            severity=rule.severity,
                            field_name=field_name,
                            observed_value=raw,
                            expected_value=f"Date on or before {curr_month:02d}/{curr_year} (+{tolerance}m allowance)",
                        )
                    )

        return violations


class MRPFormatValidator(BaseValidator):
    def validate(
        self,
        rule: RuleDefinitionSchema,
        fields: ExtractionFields,
        context: ValidationContext,
    ) -> list[ViolationData]:
        violations: list[ViolationData] = []
        mrp = fields.mrp
        if not mrp or not mrp.present:
            return violations

        val = mrp.value
        raw = mrp.raw or ""

        # Check currency designation per Rule 9(1)
        foreign_currencies = [r"\$", r"€", r"£", r"¥", r"\busd\b", r"\beur\b", r"\bgbp\b"]
        if mrp.currency and mrp.currency.strip().upper() not in ("INR", "RS", "RUPEES", ""):
            violations.append(
                ViolationData(
                    rule_code=rule.id,
                    rule_title=rule.title,
                    citation=rule.citation,
                    severity=rule.severity,
                    field_name="mrp",
                    observed_value=f"Currency: {mrp.currency}",
                    expected_value="Retail sale price must be declared in Indian Rupees (INR, Rs., or ₹)",
                )
            )
            return violations

        if raw and any(re.search(p, raw, re.IGNORECASE) for p in foreign_currencies):
            violations.append(
                ViolationData(
                    rule_code=rule.id,
                    rule_title=rule.title,
                    citation=rule.citation,
                    severity=rule.severity,
                    field_name="mrp",
                    observed_value=raw,
                    expected_value="Retail sale price must be declared in Indian Rupees (INR, Rs., or ₹)",
                )
            )
            return violations

        if val is None:
            # Check if raw text contains any number
            match = re.search(r"(\d+(?:\.\d{1,2})?)", raw)
            if match:
                val = float(match.group(1))
            else:
                violations.append(
                    ViolationData(
                        rule_code=rule.id,
                        rule_title=rule.title,
                        citation=rule.citation,
                        severity=rule.severity,
                        field_name="mrp",
                        observed_value=raw or "No numerical price found",
                        expected_value="Positive numerical retail price (e.g. ₹99.00)",
                    )
                )
                return violations

        if val <= 0:
            violations.append(
                ViolationData(
                    rule_code=rule.id,
                    rule_title=rule.title,
                    citation=rule.citation,
                    severity=rule.severity,
                    field_name="mrp",
                    observed_value=str(val),
                    expected_value="Maximum Retail Price must be strictly greater than 0.00",
                )
            )

        return violations


class TaxesInclusiveTextValidator(BaseValidator):
    def validate(
        self,
        rule: RuleDefinitionSchema,
        fields: ExtractionFields,
        context: ValidationContext,
    ) -> list[ViolationData]:
        violations: list[ViolationData] = []
        mrp = fields.mrp
        if not mrp or not mrp.present:
            return violations

        combined_text = f"{mrp.taxes_inclusive_text or ''} {mrp.raw or ''}".lower()
        required_patterns = [
            r"incl(?:usive)?\.?\s*(?:of\s*)?(?:all\s*)?taxes",
            r"all\s*taxes\s*incl(?:uded)?",
        ]

        matched = any(re.search(p, combined_text, re.IGNORECASE) for p in required_patterns)
        if not matched and context.raw_text:
            matched = any(re.search(p, context.raw_text, re.IGNORECASE) for p in required_patterns)

        if not matched:
            violations.append(
                ViolationData(
                    rule_code=rule.id,
                    rule_title=rule.title,
                    citation=rule.citation,
                    severity=rule.severity,
                    field_name="mrp",
                    observed_value=mrp.taxes_inclusive_text
                    or mrp.raw
                    or "Missing tax inclusion statement",
                    expected_value="Declaration 'inclusive of all taxes' or 'incl. of all taxes'",
                )
            )

        return violations


class NetQuantityUnitStandardValidator(BaseValidator):
    def validate(
        self,
        rule: RuleDefinitionSchema,
        fields: ExtractionFields,
        context: ValidationContext,
    ) -> list[ViolationData]:
        violations: list[ViolationData] = []
        net_qty = fields.net_quantity
        if not net_qty or not net_qty.present:
            return violations

        allowed_units = [
            u.lower()
            for u in rule.params.get(
                "allowed_units",
                ["g", "kg", "ml", "l", "m", "cm", "mm", "u", "n", "piece", "pieces", "count"],
            )
        ]

        unit = (net_qty.unit or "").strip().lower()

        # If unit is empty, try to parse from raw
        if not unit and net_qty.raw:
            match = re.search(r"(\d+(?:\.\d+)?)\s*([a-zA-Z]+)", net_qty.raw)
            if match:
                unit = match.group(2).lower()

        if not unit:
            violations.append(
                ViolationData(
                    rule_code=rule.id,
                    rule_title=rule.title,
                    citation=rule.citation,
                    severity=rule.severity,
                    field_name="net_quantity",
                    observed_value=net_qty.raw or "Missing unit",
                    expected_value=f"Standard unit: {', '.join(allowed_units[:6])}...",
                )
            )
            return violations

        # Disallow non-standard symbols and plurals (e.g. gms, kgs, mls)
        disallowed_plurals = {
            "gms": "g",
            "kgs": "kg",
            "mls": "ml",
            "ltrs": "l",
            "ltr": "l",
            "gm": "g",
        }
        if unit in disallowed_plurals or unit not in allowed_units:
            expected_suggestion = disallowed_plurals.get(
                unit, f"Standard metric unit from: {', '.join(allowed_units[:6])}"
            )
            violations.append(
                ViolationData(
                    rule_code=rule.id,
                    rule_title=rule.title,
                    citation=rule.citation,
                    severity=rule.severity,
                    field_name="net_quantity",
                    observed_value=unit,
                    expected_value=f"Standard singular metric symbol '{expected_suggestion}'",
                )
            )

        return violations


class NetQuantityPlacementValidator(BaseValidator):
    def validate(
        self,
        rule: RuleDefinitionSchema,
        fields: ExtractionFields,
        context: ValidationContext,
    ) -> list[ViolationData]:
        violations: list[ViolationData] = []
        net_qty = fields.net_quantity
        if not net_qty or not net_qty.present:
            return violations

        raw = (net_qty.raw or "").lower()
        disallowed = rule.params.get(
            "disallowed_qualifiers",
            ["approx", "approx.", "approximately", "when packed", "minimum", "min.", "average"],
        )

        found_qualifiers = [q for q in disallowed if re.search(r"\b" + re.escape(q) + r"\b", raw)]
        if found_qualifiers:
            violations.append(
                ViolationData(
                    rule_code=rule.id,
                    rule_title=rule.title,
                    citation=rule.citation,
                    severity=rule.severity,
                    field_name="net_quantity",
                    observed_value=f"Contains qualifier: {', '.join(found_qualifiers)}",
                    expected_value="Net quantity must be declared without qualifiers like 'approx' or 'when packed'",
                )
            )

        return violations


def _is_mandatory_declaration_block(block: TextBlock, fields: ExtractionFields) -> bool:
    text = (getattr(block, "text", "") or "").strip().lower()
    if not text:
        return False
    # Must contain at least one digit
    if not any(c.isdigit() for c in text):
        return False

    # Check pattern matching MRP or Net Qty declarations
    if re.search(r"(?:mrp|rs\.?|₹|inr|net\s*(?:wt|weight|qty|quantity))\s*[:.]?\s*\d+", text):
        return True

    # Check against fields.net_quantity
    nq = getattr(fields, "net_quantity", None)
    if nq:
        raw_nq = (getattr(nq, "raw", "") or "").strip().lower()
        if raw_nq and (raw_nq in text or text in raw_nq):
            return True
        val_nq = getattr(nq, "value", None)
        if val_nq is not None:
            val_str = str(
                int(val_nq) if isinstance(val_nq, float) and val_nq.is_integer() else val_nq
            )
            if val_str in text:
                return True

    # Check against fields.mrp
    mrp = getattr(fields, "mrp", None)
    if mrp:
        raw_mrp = (getattr(mrp, "raw", "") or "").strip().lower()
        if raw_mrp and (raw_mrp in text or text in raw_mrp):
            return True
        val_mrp = getattr(mrp, "value", None)
        if val_mrp is not None:
            val_str = str(
                int(val_mrp) if isinstance(val_mrp, float) and val_mrp.is_integer() else val_mrp
            )
            if val_str in text:
                return True

    return False


class FontSizeSurfaceAreaValidator(BaseValidator):
    def validate(
        self,
        rule: RuleDefinitionSchema,
        fields: ExtractionFields,
        context: ValidationContext,
    ) -> list[ViolationData]:
        violations: list[ViolationData] = []
        if context.font_check_mode != "surface_area":
            return violations

        surface_area = context.surface_area_cm2
        if surface_area is None or surface_area <= 0:
            # If no surface area provided, surface area check is skipped
            return violations

        # Determine minimum height in mm based on surface area brackets
        brackets = rule.params.get(
            "area_brackets",
            [
                {"max_area": 50, "min_height_mm": 1.0},
                {"max_area": 100, "min_height_mm": 1.5},
                {"max_area": 500, "min_height_mm": 2.5},
                {"max_area": 2500, "min_height_mm": 4.0},
                {"max_area": 999999, "min_height_mm": 6.0},
            ],
        )

        required_min_mm = 1.0
        for b in brackets:
            if surface_area <= b["max_area"]:
                required_min_mm = float(b["min_height_mm"])
                break

        # Check detected text blocks for mandatory declarations (net quantity / mrp numerals)
        for block in context.detected_text_blocks:
            if not _is_mandatory_declaration_block(block, fields):
                continue
            estimated_mm = getattr(block, "estimated_font_height_mm", None)
            if estimated_mm is not None and estimated_mm < required_min_mm:
                violations.append(
                    ViolationData(
                        rule_code=rule.id,
                        rule_title=rule.title,
                        citation=rule.citation,
                        severity=rule.severity,
                        field_name="font_size",
                        observed_value=f"{estimated_mm:.1f} mm (Surface Area: {surface_area} cm²)",
                        expected_value=f"Minimum font height of {required_min_mm:.1f} mm per Rule 9(5) Table 1",
                        bbox={"coords": block.bbox} if getattr(block, "bbox", None) else None,
                    )
                )
                break

        return violations


class FontSizeRelativeValidator(BaseValidator):
    def validate(
        self,
        rule: RuleDefinitionSchema,
        fields: ExtractionFields,
        context: ValidationContext,
    ) -> list[ViolationData]:
        violations: list[ViolationData] = []
        if context.font_check_mode != "relative":
            return violations

        min_px = float(rule.params.get("min_char_height_px", 10.0))

        if not context.detected_text_blocks:
            return violations

        for block in context.detected_text_blocks:
            if not _is_mandatory_declaration_block(block, fields):
                continue
            px = block.estimated_char_height_px
            if px is not None and 0 < px < min_px:
                violations.append(
                    ViolationData(
                        rule_code=rule.id,
                        rule_title=rule.title,
                        citation=rule.citation,
                        severity=rule.severity,
                        field_name="font_size",
                        observed_value=f"Estimated char height {px:.1f}px for text '{block.text[:30]}'",
                        expected_value=f"Legible font with minimum char height {min_px:.1f}px",
                        bbox={"coords": block.bbox} if block.bbox else None,
                    )
                )
                break

        return violations


class FieldPairMatchValidator(BaseValidator):
    def validate(
        self,
        rule: RuleDefinitionSchema,
        fields: ExtractionFields,
        context: ValidationContext,
    ) -> list[ViolationData]:
        violations: list[ViolationData] = []
        origin_val = (
            (fields.country_of_origin.normalized or fields.country_of_origin.raw or "")
            .strip()
            .lower()
        )
        excluded = [
            e.lower()
            for e in rule.params.get("non_domestic_values_exclude", ["india", "bharat", "in"])
        ]

        is_imported = context.scan_mode == "imported" or (origin_val and origin_val not in excluded)

        if is_imported:
            required_fields = rule.params.get(
                "required_fields", ["importer_name", "importer_address"]
            )
            for req_field in required_fields:
                field_obj = getattr(fields, req_field, None)
                present = getattr(field_obj, "present", False) if field_obj else False
                val = getattr(field_obj, "normalized", None) or getattr(field_obj, "raw", None)
                if not present or not val or not str(val).strip():
                    violations.append(
                        ViolationData(
                            rule_code=rule.id,
                            rule_title=rule.title,
                            citation=rule.citation,
                            severity=rule.severity,
                            field_name=req_field,
                            observed_value=str(val) if val else "Missing",
                            expected_value=f"Mandatory declaration of {req_field.replace('_', ' ')} for imported package (Origin: {origin_val or 'Foreign'})",
                        )
                    )

        return violations


class ConditionValidator(BaseValidator):
    def validate(
        self,
        rule: RuleDefinitionSchema,
        fields: ExtractionFields,
        context: ValidationContext,
    ) -> list[ViolationData]:
        violations: list[ViolationData] = []
        check_type = rule.params.get("check_type")

        if check_type == "dual_mrp":
            # Check for multiple differing MRPs in raw text or detected text blocks
            raw = (context.raw_text or "") + " " + (fields.mrp.raw or "")
            mrp_matches = re.findall(
                r"(?:mrp|rs\.?|₹)\s*[:.]?\s*(\d+(?:\.\d{1,2})?)", raw, re.IGNORECASE
            )
            distinct_prices = set()
            for m in mrp_matches:
                try:
                    val = float(m)
                    if val > 0:
                        distinct_prices.add(val)
                except ValueError:
                    continue

            if len(distinct_prices) > 1:
                violations.append(
                    ViolationData(
                        rule_code=rule.id,
                        rule_title=rule.title,
                        citation=rule.citation,
                        severity=rule.severity,
                        field_name="mrp",
                        observed_value=f"Multiple conflicting MRP values found: {sorted(distinct_prices)}",
                        expected_value="Single uniform Maximum Retail Price across package per Rule 9(3)",
                    )
                )

        return violations


# Validator registry instance
_VALIDATORS: dict[str, BaseValidator] = {
    "presence": PresenceValidator(),
    "regex_format": RegexFormatValidator(),
    "date_valid_not_future": DateValidNotFutureValidator(),
    "mrp_format": MRPFormatValidator(),
    "taxes_inclusive_text": TaxesInclusiveTextValidator(),
    "net_quantity_unit_standard": NetQuantityUnitStandardValidator(),
    "net_quantity_placement": NetQuantityPlacementValidator(),
    "font_size_surface_area": FontSizeSurfaceAreaValidator(),
    "font_size_relative": FontSizeRelativeValidator(),
    "field_pair_match": FieldPairMatchValidator(),
    "condition": ConditionValidator(),
}


def get_validator(check_name: str) -> BaseValidator | None:
    return _VALIDATORS.get(check_name)
