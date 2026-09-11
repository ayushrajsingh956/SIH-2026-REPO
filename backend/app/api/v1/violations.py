import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import require_role
from app.core.exceptions import ProblemDetailException
from app.core.pagination import paginate
from app.models.scan import Scan
from app.models.user import User
from app.models.violation import Violation
from app.schemas.violation import ViolationListItem, ViolationListResponse

router = APIRouter(prefix="/violations", tags=["Violations"])


@router.get(
    "",
    response_model=ViolationListResponse,
    summary="Cross-scan violation search with multi-filters",
)
async def list_violations(
    rule_code: str | None = Query(None, description="Filter by LMPC rule code"),
    severity: str | None = Query(
        None, description="Filter by severity: critical, major, minor, advisory"
    ),
    district: str | None = Query(None, description="Filter by inspector district"),
    start_date: datetime | None = Query(None, description="Filter by earliest scan date"),
    end_date: datetime | None = Query(None, description="Filter by latest scan date"),
    overridden: bool | None = Query(None, description="Filter by override status"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=500),
    current_user: User = Depends(require_role("admin", "inspector", "viewer")),
    db: AsyncSession = Depends(get_db),
) -> ViolationListResponse:
    query = (
        select(Violation)
        .join(Scan, Violation.scan_id == Scan.id)
        .outerjoin(User, Scan.scanned_by == User.id)
        .options(
            selectinload(Violation.scan).selectinload(Scan.inspector),
            selectinload(Violation.scan).selectinload(Scan.product),
        )
    )

    if rule_code:
        query = query.where(Violation.rule_code == rule_code)
    if severity:
        query = query.where(Violation.severity == severity)
    if district:
        query = query.where(User.district == district)
    if start_date:
        query = query.where(Scan.scanned_at >= start_date)
    if end_date:
        query = query.where(Scan.scanned_at <= end_date)
    if overridden is not None:
        query = query.where(Violation.overridden == overridden)

    # Compute severity summary for current filters
    sev_stmt = (
        select(Violation.severity, func.count(Violation.id))
        .join(Scan, Violation.scan_id == Scan.id)
        .outerjoin(User, Scan.scanned_by == User.id)
    )
    if rule_code:
        sev_stmt = sev_stmt.where(Violation.rule_code == rule_code)
    if district:
        sev_stmt = sev_stmt.where(User.district == district)
    if start_date:
        sev_stmt = sev_stmt.where(Scan.scanned_at >= start_date)
    if end_date:
        sev_stmt = sev_stmt.where(Scan.scanned_at <= end_date)
    if overridden is not None:
        sev_stmt = sev_stmt.where(Violation.overridden == overridden)
    sev_stmt = sev_stmt.group_by(Violation.severity)

    sev_res = await db.execute(sev_stmt)
    severity_summary = {row[0]: row[1] for row in sev_res.all()}

    # Paginate rows
    violations, total = await paginate(db, query, page, limit, Scan.scanned_at.desc())

    items: list[ViolationListItem] = []
    for v in violations:
        scan = v.scan
        inspector = scan.inspector if scan else None
        product = scan.product if scan else None
        items.append(
            ViolationListItem(
                id=v.id,
                scan_id=v.scan_id,
                rule_code=v.rule_code,
                rule_title=v.rule_title,
                citation=v.citation,
                severity=v.severity,
                field_name=v.field_name,
                observed_value=v.observed_value,
                expected_value=v.expected_value,
                bbox=v.bbox,
                overridden=v.overridden,
                override_reason=v.override_reason,
                scanned_at=scan.scanned_at if scan else datetime.utcnow(),
                mode=scan.mode if scan else "retail",
                district=inspector.district if inspector else None,
                state=inspector.state if inspector else None,
                product_name=product.name if product else None,
            )
        )

    return ViolationListResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
        severity_summary=severity_summary,
    )


@router.get("/{id}", response_model=ViolationListItem, summary="Get single violation detail")
async def get_violation_detail(
    id: uuid.UUID,
    current_user: User = Depends(require_role("admin", "inspector", "viewer")),
    db: AsyncSession = Depends(get_db),
) -> ViolationListItem:
    stmt = (
        select(Violation)
        .options(
            selectinload(Violation.scan).selectinload(Scan.inspector),
            selectinload(Violation.scan).selectinload(Scan.product),
        )
        .where(Violation.id == id)
    )
    res = await db.execute(stmt)
    v = res.scalar_one_or_none()

    if not v:
        raise ProblemDetailException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Violation Not Found",
            detail=f"Violation '{id}' not found.",
            type_url="https://errors.legalmetro.gov.in/violation-not-found",
        )

    scan = v.scan
    inspector = scan.inspector if scan else None
    product = scan.product if scan else None

    return ViolationListItem(
        id=v.id,
        scan_id=v.scan_id,
        rule_code=v.rule_code,
        rule_title=v.rule_title,
        citation=v.citation,
        severity=v.severity,
        field_name=v.field_name,
        observed_value=v.observed_value,
        expected_value=v.expected_value,
        bbox=v.bbox,
        overridden=v.overridden,
        override_reason=v.override_reason,
        scanned_at=scan.scanned_at if scan else datetime.utcnow(),
        mode=scan.mode if scan else "retail",
        district=inspector.district if inspector else None,
        state=inspector.state if inspector else None,
        product_name=product.name if product else None,
    )
