import logging
from collections.abc import Sequence
from typing import Any

logger = logging.getLogger(__name__)

SEVERITY_DEDUCTIONS = {
    "critical": 30.0,
    "major": 15.0,
    "minor": 5.0,
    "advisory": 0.0,
}


def compute_score_and_verdict(
    violations: Sequence[Any],
    needs_review_flag: bool = False,
    confidence_score: float | None = None,
) -> tuple[float, str]:
    """
    Computes deterministic compliance score (0-100) and verdict based on LMPC rules.

    Invariants (Spec §7):
    - Base score = 100
    - Deductions: Critical: -30, Major: -15, Minor: -5, Advisory: 0
    - Overridden violations do not deduct points.
    - score = max(0.0, 100.0 - total_deductions)
    - Verdict:
        - 'needs_review' if needs_review_flag is True or (confidence_score is not None and confidence_score < 0.60)
        - 'compliant' if score >= 90.0 and active_critical == 0 and active_major == 0
        - 'non_compliant' otherwise (score < 90.0 or any active critical/major violation)
    """
    deductions = 0.0
    active_critical = 0
    active_major = 0

    for v in violations:
        # Handle dict, Pydantic model, or SQLAlchemy Violation model
        overridden = False
        if hasattr(v, "overridden"):
            overridden = bool(v.overridden)
        elif isinstance(v, dict):
            overridden = bool(v.get("overridden", False))

        if overridden:
            continue

        severity = ""
        if hasattr(v, "severity"):
            severity = str(v.severity).lower()
        elif isinstance(v, dict):
            severity = str(v.get("severity", "")).lower()

        deduction = SEVERITY_DEDUCTIONS.get(severity, 0.0)
        deductions += deduction

        if severity == "critical":
            active_critical += 1
        elif severity == "major":
            active_major += 1

    score = max(0.0, round(100.0 - deductions, 2))

    # Determine verdict
    is_low_confidence = confidence_score is not None and confidence_score < 0.60
    if needs_review_flag or is_low_confidence:
        verdict = "needs_review"
    elif score >= 90.0 and active_critical == 0 and active_major == 0:
        verdict = "compliant"
    else:
        verdict = "non_compliant"

    return score, verdict
