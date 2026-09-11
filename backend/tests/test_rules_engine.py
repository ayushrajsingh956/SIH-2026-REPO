from unittest.mock import patch

from app.schemas.extraction import (
    ConsumerCareField,
    DateField,
    ExtractionFields,
    MRPField,
    NetQuantityField,
    StandardTextField,
)
from app.services.rules import (
    compute_score_and_verdict,
    evaluate_rules,
)
from app.services.rules.validators import ViolationData


def create_compliant_fields() -> ExtractionFields:
    return ExtractionFields(
        manufacturer_name=StandardTextField(
            raw="Good Foods Pvt Ltd", normalized="Good Foods Pvt Ltd", present=True
        ),
        manufacturer_address=StandardTextField(
            raw="Plot 10, Sector 5, Gurgaon", normalized="Plot 10, Sector 5, Gurgaon", present=True
        ),
        country_of_origin=StandardTextField(raw="India", normalized="India", present=True),
        generic_name=StandardTextField(
            raw="Roasted Almonds", normalized="Roasted Almonds", present=True
        ),
        net_quantity=NetQuantityField(raw="250 g", value=250.0, unit="g", present=True),
        mrp=MRPField(
            raw="₹299.00 incl. of all taxes",
            value=299.0,
            taxes_inclusive_text="incl. of all taxes",
            present=True,
        ),
        mfg_date=DateField(raw="01/2026", month=1, year=2026, present=True),
        consumer_care=ConsumerCareField(
            raw="care@goodfoods.com, 1800-000-111",
            email="care@goodfoods.com",
            phone=["1800000111"],
            present=True,
        ),
    )


class TestRulesEngineDeterminism:
    def test_evaluate_rules_deterministic_output(self):
        fields = create_compliant_fields()
        # Introduce two intentional violations
        fields.mrp.value = 0.0
        fields.net_quantity.unit = "gms"

        run1_violations, run1_flag = evaluate_rules(fields=fields, scan_mode="retail")
        run2_violations, run2_flag = evaluate_rules(fields=fields, scan_mode="retail")

        assert run1_flag is False and run2_flag is False
        assert len(run1_violations) == len(run2_violations)
        for v1, v2 in zip(run1_violations, run2_violations, strict=True):
            assert v1.rule_code == v2.rule_code
            assert v1.severity == v2.severity
            assert v1.field_name == v2.field_name


class TestComplianceScoringAndVerdicts:
    def test_perfect_compliance(self):
        fields = create_compliant_fields()
        violations, needs_review = evaluate_rules(fields=fields, scan_mode="retail")
        assert len(violations) == 0

        score, verdict = compute_score_and_verdict(violations, needs_review_flag=needs_review)
        assert score == 100.0
        assert verdict == "compliant"

    def test_minor_violation_retains_compliant_status(self):
        # 1 minor violation (-5 deduction) = 95.0 -> compliant
        minor_v = [
            ViolationData(
                rule_code="LMPC-R10-2",
                rule_title="Placement",
                citation="Rule 10(2)",
                severity="minor",
                field_name="net_quantity",
            )
        ]
        score, verdict = compute_score_and_verdict(minor_v)
        assert score == 95.0
        assert verdict == "compliant"

    def test_major_violation_renders_non_compliant(self):
        # 1 major violation (-15 deduction) = 85.0 -> non_compliant
        major_v = [
            ViolationData(
                rule_code="LMPC-R10-1",
                rule_title="Units",
                citation="Rule 10(1)",
                severity="major",
                field_name="net_quantity",
            )
        ]
        score, verdict = compute_score_and_verdict(major_v)
        assert score == 85.0
        assert verdict == "non_compliant"

    def test_critical_violation_renders_non_compliant(self):
        # 1 critical violation (-30 deduction) = 70.0 -> non_compliant
        crit_v = [
            ViolationData(
                rule_code="LMPC-R6-1d",
                rule_title="MRP Presence",
                citation="Rule 6(1)(d)",
                severity="critical",
                field_name="mrp",
            )
        ]
        score, verdict = compute_score_and_verdict(crit_v)
        assert score == 70.0
        assert verdict == "non_compliant"

    def test_score_clamping_at_zero(self):
        # 4 critical violations (4 * 30 = 120 deduction) -> score clamped to 0.0
        crit_vs = [
            ViolationData(
                rule_code=f"RULE-{i}",
                rule_title=f"Crit {i}",
                citation=f"Citation {i}",
                severity="critical",
                field_name=f"field_{i}",
            )
            for i in range(4)
        ]
        score, verdict = compute_score_and_verdict(crit_vs)
        assert score == 0.0
        assert verdict == "non_compliant"

    def test_overridden_violations_do_not_deduct_points(self):
        crit_v = {
            "rule_code": "LMPC-R6-1d",
            "rule_title": "MRP Presence",
            "citation": "Rule 6(1)(d)",
            "severity": "critical",
            "field_name": "mrp",
            "overridden": True,
        }
        score, verdict = compute_score_and_verdict([crit_v])
        assert score == 100.0
        assert verdict == "compliant"

    def test_low_confidence_triggers_needs_review(self):
        # Even with 0 violations, confidence < 0.60 sets needs_review
        score, verdict = compute_score_and_verdict([], confidence_score=0.55)
        assert score == 100.0
        assert verdict == "needs_review"

    def test_validator_exception_safety(self):
        """Worker must never crash if a validator raises an unexpected error; flag needs_review."""
        fields = create_compliant_fields()

        with patch("app.services.rules.engine.get_validator") as mock_get_val:

            class FaultyValidator:
                def validate(self, *args, **kwargs):
                    raise RuntimeError("Simulated internal validator failure")

            mock_get_val.return_value = FaultyValidator()

            # Should not raise exception
            violations, needs_review = evaluate_rules(fields=fields, scan_mode="retail")
            assert needs_review is True

            score, verdict = compute_score_and_verdict(violations, needs_review_flag=needs_review)
            assert verdict == "needs_review"


class TestRuleConfigurationOverrides:
    def test_admin_disable_rule(self):
        fields = create_compliant_fields()
        fields.mrp.value = None
        fields.mrp.raw = ""
        fields.mrp.present = False

        # With default rules, LMPC-R6-1d triggers
        v_default, _ = evaluate_rules(fields=fields, scan_mode="retail")
        assert any(v.rule_code == "LMPC-R6-1d" for v in v_default)

        # Disable LMPC-R6-1d via overrides
        overrides = {"LMPC-R6-1d": {"is_enabled": False}}
        v_disabled, _ = evaluate_rules(fields=fields, scan_mode="retail", rule_overrides=overrides)
        assert not any(v.rule_code == "LMPC-R6-1d" for v in v_disabled)

    def test_admin_severity_override(self):
        fields = create_compliant_fields()
        fields.mrp.value = None
        fields.mrp.raw = ""
        fields.mrp.present = False

        # Override severity of LMPC-R6-1d from critical to minor
        overrides = {"LMPC-R6-1d": {"is_enabled": True, "severity_override": "minor"}}
        violations, _ = evaluate_rules(fields=fields, scan_mode="retail", rule_overrides=overrides)
        mrp_v = next(v for v in violations if v.rule_code == "LMPC-R6-1d")
        assert mrp_v.severity == "minor"

        score, verdict = compute_score_and_verdict(violations)
        # Deduction should now be 5 instead of 30
        assert score == 95.0
        assert verdict == "compliant"
