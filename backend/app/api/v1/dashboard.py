from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_role
from app.models.scan import Scan
from app.models.user import User
from app.models.violation import Violation
from app.schemas.dashboard import (
    ComplianceTrendItem,
    DashboardSummaryResponse,
    DistrictHeatItem,
    ViolationsByRuleItem,
    ViolationsBySeverityItem,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _parse_range_to_delta(range_str: str) -> timedelta:
    if range_str == "7d":
        return timedelta(days=7)
    elif range_str == "90d":
        return timedelta(days=90)
    elif range_str == "365d":
        return timedelta(days=365)
    return timedelta(days=30)  # default 30d


@router.get("/summary", response_model=DashboardSummaryResponse, summary="Dashboard KPI metrics")
async def get_dashboard_summary(
    range: Literal["7d", "30d", "90d", "365d"] = "30d",
    current_user: User = Depends(require_role("admin", "inspector", "viewer")),
    db: AsyncSession = Depends(get_db),
) -> DashboardSummaryResponse:
    now = datetime.now(UTC)
    delta = _parse_range_to_delta(range)
    start_date = now - delta
    prev_start = start_date - delta

    # Current period scans
    scans_stmt = select(Scan).where(Scan.scanned_at >= start_date)
    scans_res = await db.execute(scans_stmt)
    scans = scans_res.scalars().all()

    total_scans = len(scans)
    compliant_scans = sum(1 for s in scans if s.verdict == "compliant")
    non_compliant_scans = sum(1 for s in scans if s.verdict == "non_compliant")
    needs_review_scans = sum(
        1 for s in scans if s.verdict == "needs_review" or s.status == "needs_review"
    )

    compliance_rate = round((compliant_scans / total_scans * 100), 1) if total_scans > 0 else 0.0
    scored_scans = [s.compliance_score for s in scans if s.compliance_score is not None]
    avg_score = round(sum(scored_scans) / len(scored_scans), 1) if scored_scans else 0.0

    # Pending reviews (active system-wide)
    pending_stmt = select(func.count(Scan.id)).where(
        Scan.status.in_(["needs_review", "queued", "processing"])
    )
    pending_res = await db.execute(pending_stmt)
    pending_reviews = pending_res.scalar_one()

    # Violations in range
    scan_ids = [s.id for s in scans]
    total_violations = 0
    critical_violations = 0
    if scan_ids:
        v_stmt = (
            select(Violation.severity, func.count(Violation.id))
            .where(Violation.scan_id.in_(scan_ids))
            .group_by(Violation.severity)
        )
        v_res = await db.execute(v_stmt)
        for sev, count in v_res.all():
            total_violations += count
            if sev == "critical":
                critical_violations += count

    # Previous period comparison
    prev_stmt = select(func.count(Scan.id)).where(
        Scan.scanned_at >= prev_start, Scan.scanned_at < start_date
    )
    prev_res = await db.execute(prev_stmt)
    prev_scans = prev_res.scalar_one()

    scans_comparison_pct: float | None = None
    if prev_scans > 0:
        scans_comparison_pct = round(((total_scans - prev_scans) / prev_scans) * 100, 1)

    return DashboardSummaryResponse(
        total_scans=total_scans,
        compliant_scans=compliant_scans,
        non_compliant_scans=non_compliant_scans,
        needs_review_scans=needs_review_scans,
        compliance_rate=compliance_rate,
        avg_compliance_score=avg_score,
        pending_reviews=pending_reviews,
        total_violations=total_violations,
        critical_violations=critical_violations,
        scans_comparison_pct=scans_comparison_pct,
    )


@router.get(
    "/violations/by-rule",
    response_model=list[ViolationsByRuleItem],
    summary="Violations grouped by rule",
)
async def get_violations_by_rule(
    range: Literal["7d", "30d", "90d", "365d"] = "30d",
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(require_role("admin", "inspector", "viewer")),
    db: AsyncSession = Depends(get_db),
) -> list[ViolationsByRuleItem]:
    now = datetime.now(UTC)
    delta = _parse_range_to_delta(range)
    start_date = now - delta

    stmt = (
        select(
            Violation.rule_code,
            Violation.rule_title,
            Violation.citation,
            Violation.severity,
            func.count(Violation.id).label("count"),
        )
        .join(Scan, Violation.scan_id == Scan.id)
        .where(Scan.scanned_at >= start_date)
        .group_by(Violation.rule_code, Violation.rule_title, Violation.citation, Violation.severity)
        .order_by(func.count(Violation.id).desc())
        .limit(limit)
    )
    res = await db.execute(stmt)
    return [
        ViolationsByRuleItem(
            rule_code=row[0],
            rule_title=row[1],
            citation=row[2],
            severity=row[3],
            count=row[4],
        )
        for row in res.all()
    ]


@router.get(
    "/violations/by-severity",
    response_model=list[ViolationsBySeverityItem],
    summary="Violations grouped by severity",
)
async def get_violations_by_severity(
    range: Literal["7d", "30d", "90d", "365d"] = "30d",
    current_user: User = Depends(require_role("admin", "inspector", "viewer")),
    db: AsyncSession = Depends(get_db),
) -> list[ViolationsBySeverityItem]:
    now = datetime.now(UTC)
    delta = _parse_range_to_delta(range)
    start_date = now - delta

    stmt = (
        select(Violation.severity, func.count(Violation.id).label("count"))
        .join(Scan, Violation.scan_id == Scan.id)
        .where(Scan.scanned_at >= start_date)
        .group_by(Violation.severity)
    )
    res = await db.execute(stmt)
    raw_counts = {row[0]: row[1] for row in res.all()}
    total = sum(raw_counts.values())

    order = ["critical", "major", "minor", "advisory"]
    items = []
    for sev in order:
        count = raw_counts.get(sev, 0)
        pct = round((count / total * 100), 1) if total > 0 else 0.0
        items.append(ViolationsBySeverityItem(severity=sev, count=count, percentage=pct))
    return items


@router.get(
    "/compliance/trend",
    response_model=list[ComplianceTrendItem],
    summary="Compliance time-series trend",
)
async def get_compliance_trend(
    range: Literal["7d", "30d", "90d", "365d"] = "30d",
    granularity: Literal["day", "week", "month"] = "day",
    current_user: User = Depends(require_role("admin", "inspector", "viewer")),
    db: AsyncSession = Depends(get_db),
) -> list[ComplianceTrendItem]:
    now = datetime.now(UTC)
    delta = _parse_range_to_delta(range)
    start_date = now - delta

    stmt = (
        select(Scan.scanned_at, Scan.verdict, Scan.compliance_score)
        .where(Scan.scanned_at >= start_date)
        .order_by(Scan.scanned_at.asc())
    )
    res = await db.execute(stmt)
    rows = res.all()

    # Bucket in Python
    buckets = defaultdict(lambda: {"total": 0, "compliant": 0, "non_compliant": 0, "scores": []})

    for scanned_at, verdict, score in rows:
        if granularity == "day":
            key = scanned_at.strftime("%Y-%m-%d")
        elif granularity == "week":
            year, week, _ = scanned_at.isocalendar()
            key = f"{year}-W{week:02d}"
        else:
            key = scanned_at.strftime("%Y-%m")

        buckets[key]["total"] += 1
        if verdict == "compliant":
            buckets[key]["compliant"] += 1
        elif verdict == "non_compliant":
            buckets[key]["non_compliant"] += 1
        if score is not None:
            buckets[key]["scores"].append(score)

    items: list[ComplianceTrendItem] = []
    for key in sorted(buckets.keys()):
        b = buckets[key]
        rate = round((b["compliant"] / b["total"] * 100), 1) if b["total"] > 0 else 0.0
        avg_s = round(sum(b["scores"]) / len(b["scores"]), 1) if b["scores"] else 0.0
        items.append(
            ComplianceTrendItem(
                date=key,
                total_scans=b["total"],
                compliant_scans=b["compliant"],
                non_compliant_scans=b["non_compliant"],
                compliance_rate=rate,
                avg_score=avg_s,
            )
        )

    return items


@router.get(
    "/districts",
    response_model=list[DistrictHeatItem],
    summary="District and state compliance breakdown",
)
async def get_districts_compliance(
    range: Literal["7d", "30d", "90d", "365d"] = "30d",
    current_user: User = Depends(require_role("admin", "inspector", "viewer")),
    db: AsyncSession = Depends(get_db),
) -> list[DistrictHeatItem]:
    now = datetime.now(UTC)
    delta = _parse_range_to_delta(range)
    start_date = now - delta

    # Join Scan and Inspector User
    stmt = (
        select(
            User.district,
            User.state,
            Scan.verdict,
            Scan.scanned_at,
            Scan.id,
        )
        .join(User, Scan.scanned_by == User.id)
        .where(Scan.scanned_at >= start_date)
    )
    res = await db.execute(stmt)
    rows = res.all()

    # Get critical violation counts per scan
    scan_ids = [r[4] for r in rows]
    critical_by_scan = defaultdict(int)
    if scan_ids:
        crit_stmt = (
            select(Violation.scan_id, func.count(Violation.id))
            .where(
                Violation.scan_id.in_(scan_ids),
                Violation.severity == "critical",
            )
            .group_by(Violation.scan_id)
        )
        crit_res = await db.execute(crit_stmt)
        for sid, cnt in crit_res.all():
            critical_by_scan[sid] = cnt

    district_map = defaultdict(
        lambda: {
            "state": "",
            "total": 0,
            "compliant": 0,
            "critical_violations": 0,
            "last_activity": None,
        }
    )

    for district, state, verdict, scanned_at, scan_id in rows:
        d_name = district or "Unassigned"
        s_name = state or "Central"
        d = district_map[d_name]
        d["state"] = s_name
        d["total"] += 1
        if verdict == "compliant":
            d["compliant"] += 1
        d["critical_violations"] += critical_by_scan.get(scan_id, 0)
        if d["last_activity"] is None or scanned_at > d["last_activity"]:
            d["last_activity"] = scanned_at

    items: list[DistrictHeatItem] = []
    for d_name, data in district_map.items():
        rate = round((data["compliant"] / data["total"] * 100), 1) if data["total"] > 0 else 0.0
        items.append(
            DistrictHeatItem(
                district=d_name,
                state=data["state"],
                total_scans=data["total"],
                compliant_scans=data["compliant"],
                compliance_rate=rate,
                critical_violations=data["critical_violations"],
                last_activity=data["last_activity"],
            )
        )

    return sorted(items, key=lambda x: x.total_scans, reverse=True)
