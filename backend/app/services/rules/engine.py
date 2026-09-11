import logging
import traceback
from collections.abc import Sequence
from typing import Any

from app.schemas.extraction import ExtractionFields, TextBlock
from app.services.rules.registry import get_all_rules
from app.services.rules.validators import ValidationContext, ViolationData, get_validator

logger = logging.getLogger(__name__)


def evaluate_rules(
    fields: ExtractionFields | dict[str, Any],
    scan_mode: str = "retail",
    surface_area_cm2: float | None = None,
    font_check_mode: str = "relative",
    detected_text_blocks: Sequence[TextBlock | dict[str, Any]] | None = None,
    raw_text: str | None = None,
    rule_overrides: dict[str, Any] | list[Any] | None = None,
) -> tuple[list[ViolationData], bool]:
    """
    Evaluates all applicable LMPC rules against extracted packaging data.

    Determinism Guarantee:
    Given the identical extraction fields, scan mode, and overrides,
    this function will always return the exact same violations.

    Exception Safety:
    Any unexpected validator failure is caught, logged, and sets `needs_review=True`
    without aborting the pipeline or crashing worker threads.
    """
    needs_review = False
    violations: list[ViolationData] = []

    # 1. Normalize ExtractionFields
    if isinstance(fields, dict):
        # Could be ExtractionResultSchema dict or ExtractionFields dict
        if "fields" in fields and isinstance(fields["fields"], dict):
            fields_obj = ExtractionFields.model_validate(fields["fields"])
        else:
            fields_obj = ExtractionFields.model_validate(fields)
    elif hasattr(fields, "fields") and isinstance(fields.fields, ExtractionFields):
        fields_obj = fields.fields
    elif isinstance(fields, ExtractionFields):
        fields_obj = fields
    else:
        fields_obj = ExtractionFields()

    # 2. Normalize TextBlocks
    blocks_obj: list[TextBlock] = []
    if detected_text_blocks:
        for b in detected_text_blocks:
            if isinstance(b, dict):
                blocks_obj.append(TextBlock.model_validate(b))
            elif isinstance(b, TextBlock):
                blocks_obj.append(b)
            elif hasattr(b, "text"):
                blocks_obj.append(
                    TextBlock(
                        text=getattr(b, "text", ""),
                        bbox=getattr(b, "bbox", []),
                        estimated_char_height_px=getattr(b, "estimated_char_height_px", None),
                        estimated_font_height_mm=getattr(b, "estimated_font_height_mm", None),
                    )
                )

    # 3. Normalize Rule Overrides
    overrides_map: dict[str, dict[str, Any]] = {}
    if isinstance(rule_overrides, list):
        for ro in rule_overrides:
            code = getattr(ro, "code", None) or (ro.get("code") if isinstance(ro, dict) else None)
            if code:
                is_en = (
                    getattr(ro, "is_enabled", True)
                    if hasattr(ro, "is_enabled")
                    else ro.get("is_enabled", True)
                )
                sev_ovr = (
                    getattr(ro, "severity_override", None)
                    if hasattr(ro, "severity_override")
                    else ro.get("severity_override")
                )
                overrides_map[code] = {"is_enabled": is_en, "severity_override": sev_ovr}
    elif isinstance(rule_overrides, dict):
        overrides_map = rule_overrides

    # 4. Prepare Context
    context = ValidationContext(
        scan_mode=scan_mode,
        surface_area_cm2=surface_area_cm2,
        font_check_mode=font_check_mode,
        detected_text_blocks=blocks_obj,
        raw_text=raw_text,
        rule_overrides=overrides_map,
    )

    # 5. Fetch all registered rules
    all_rules = get_all_rules()

    # 6. Evaluate each applicable rule
    for rule_id, rule_def in all_rules.items():
        # Check rule override for enable/disable
        override_info = overrides_map.get(rule_id, {})
        if override_info.get("is_enabled") is False:
            logger.debug(f"Rule {rule_id} is disabled by admin configuration; skipping.")
            continue

        # Check mode applicability
        if scan_mode not in rule_def.applies_to:
            continue

        # Apply severity override if configured
        active_rule = rule_def
        sev_override = override_info.get("severity_override")
        if sev_override and sev_override in ["critical", "major", "minor", "advisory"]:
            active_rule = rule_def.model_copy(update={"severity": sev_override})

        validator = get_validator(active_rule.check)
        if not validator:
            logger.warning(
                f"Validator '{active_rule.check}' for rule '{rule_id}' not found in registry."
            )
            continue

        try:
            rule_violations = validator.validate(active_rule, fields_obj, context)
            if rule_violations:
                violations.extend(rule_violations)
        except Exception as exc:
            logger.error(
                f"Exception during rule validation for '{rule_id}': {exc}\n{traceback.format_exc()}"
            )
            needs_review = True

    return violations, needs_review
