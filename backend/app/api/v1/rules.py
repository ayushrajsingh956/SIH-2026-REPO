import logging

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit_event
from app.core.database import get_db
from app.core.deps import require_role
from app.core.exceptions import ProblemDetailException
from app.models.product import Product
from app.models.rule_config import RuleConfig
from app.models.scan import Scan
from app.models.user import User
from app.models.violation import Violation
from app.schemas.rule import RuleAdminUpdateRequest, RuleRecentScanItem, RuleResponse
from app.services.rules import get_all_rules, get_rule

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Rules"])
admin_router = APIRouter(tags=["Admin Rules"])


@router.get(
    "",
    response_model=list[RuleResponse],
    summary="List all compliance rules merged with database configuration and trigger statistics",
)
async def list_rules(
    current_user: User = Depends(require_role("admin", "inspector", "viewer")),
    db: AsyncSession = Depends(get_db),
) -> list[RuleResponse]:
    all_rules = get_all_rules()

    # Query rule configs from database
    configs_stmt = select(RuleConfig)
    configs_res = await db.execute(configs_stmt)
    configs_by_code = {c.code: c for c in configs_res.scalars().all()}

    # Query trigger counts from violations table
    counts_stmt = select(Violation.rule_code, func.count(Violation.id)).group_by(
        Violation.rule_code
    )
    counts_res = await db.execute(counts_stmt)
    trigger_counts = {row[0]: row[1] for row in counts_res.all()}

    results: list[RuleResponse] = []
    for rule_id, rule_def in all_rules.items():
        cfg = configs_by_code.get(rule_id)
        is_enabled = cfg.is_enabled if cfg else True
        severity_override = cfg.severity_override if cfg else None
        thresholds = cfg.thresholds if cfg else None
        effective_severity = severity_override if severity_override else rule_def.severity
        count = trigger_counts.get(rule_id, 0)

        results.append(
            RuleResponse(
                id=rule_def.id,
                title=rule_def.title,
                citation=rule_def.citation,
                severity=rule_def.severity,
                effective_severity=effective_severity,
                applies_to=rule_def.applies_to,
                check=rule_def.check,
                params=rule_def.params,
                description_plain=rule_def.description_plain,
                mandatory=rule_def.mandatory,
                is_enabled=is_enabled,
                severity_override=severity_override,
                thresholds=thresholds,
                trigger_count=count,
            )
        )

    return sorted(results, key=lambda r: r.id)


@router.get(
    "/{code}",
    response_model=RuleResponse,
    summary="Get single rule definition and statistics by rule code",
)
async def get_rule_by_code(
    code: str,
    current_user: User = Depends(require_role("admin", "inspector", "viewer")),
    db: AsyncSession = Depends(get_db),
) -> RuleResponse:
    rule_def = get_rule(code)
    if not rule_def:
        raise ProblemDetailException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Rule Not Found",
            detail=f"Rule '{code}' not found.",
            type_url="https://errors.legalmetro.gov.in/rule-not-found",
        )

    cfg_stmt = select(RuleConfig).where(RuleConfig.code == code)
    cfg_res = await db.execute(cfg_stmt)
    cfg = cfg_res.scalar_one_or_none()

    count_stmt = select(func.count(Violation.id)).where(Violation.rule_code == code)
    count_res = await db.execute(count_stmt)
    trigger_count = count_res.scalar_one()

    is_enabled = cfg.is_enabled if cfg else True
    severity_override = cfg.severity_override if cfg else None
    thresholds = cfg.thresholds if cfg else None
    effective_severity = severity_override if severity_override else rule_def.severity

    return RuleResponse(
        id=rule_def.id,
        title=rule_def.title,
        citation=rule_def.citation,
        severity=rule_def.severity,
        effective_severity=effective_severity,
        applies_to=rule_def.applies_to,
        check=rule_def.check,
        params=rule_def.params,
        description_plain=rule_def.description_plain,
        mandatory=rule_def.mandatory,
        is_enabled=is_enabled,
        severity_override=severity_override,
        thresholds=thresholds,
        trigger_count=trigger_count,
    )


@router.get(
    "/{code}/recent-scans",
    response_model=list[RuleRecentScanItem],
    summary="Get recent scans and violations triggering this rule",
)
async def get_rule_recent_scans(
    code: str,
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(require_role("admin", "inspector", "viewer")),
    db: AsyncSession = Depends(get_db),
) -> list[RuleRecentScanItem]:
    stmt = (
        select(
            Violation,
            Scan.mode,
            Scan.scanned_at,
            Scan.verdict,
            User.name.label("inspector_name"),
            Product.name.label("product_name"),
        )
        .join(Scan, Violation.scan_id == Scan.id)
        .outerjoin(User, Scan.scanned_by == User.id)
        .outerjoin(Product, Scan.product_id == Product.id)
        .where(Violation.rule_code == code)
        .order_by(Scan.scanned_at.desc())
        .limit(limit)
    )
    res = await db.execute(stmt)
    rows = res.all()

    items: list[RuleRecentScanItem] = []
    for v, mode, scanned_at, verdict, inspector_name, product_name in rows:
        items.append(
            RuleRecentScanItem(
                scan_id=str(v.scan_id),
                violation_id=str(v.id),
                mode=mode,
                scanned_at=scanned_at.isoformat(),
                verdict=verdict,
                observed_value=v.observed_value,
                expected_value=v.expected_value,
                field_name=v.field_name,
                overridden=v.overridden,
                inspector_name=inspector_name,
                product_name=product_name,
            )
        )
    return items


@admin_router.put(
    "/{code}",
    response_model=RuleResponse,
    summary="Admin enables/disables rule or updates severity override",
)
async def update_rule_config(
    code: str,
    update_req: RuleAdminUpdateRequest,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> RuleResponse:
    rule_def = get_rule(code)
    if not rule_def:
        raise ProblemDetailException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Rule Not Found",
            detail=f"Rule '{code}' not found in registered rules.",
            type_url="https://errors.legalmetro.gov.in/rule-not-found",
        )

    cfg_stmt = select(RuleConfig).where(RuleConfig.code == code)
    cfg_res = await db.execute(cfg_stmt)
    cfg = cfg_res.scalar_one_or_none()

    if not cfg:
        cfg = RuleConfig(
            code=code,
            is_enabled=True,
            severity_override=None,
            thresholds=None,
            updated_by=current_user.id,
        )
        db.add(cfg)

    if update_req.is_enabled is not None:
        cfg.is_enabled = update_req.is_enabled

    if update_req.severity_override is not None:
        if update_req.severity_override == "":
            cfg.severity_override = None
        else:
            cfg.severity_override = update_req.severity_override

    if update_req.thresholds is not None:
        cfg.thresholds = update_req.thresholds

    cfg.updated_by = current_user.id

    # Record audit log
    await record_audit_event(
        db=db,
        action="ADMIN_UPDATE_RULE",
        entity_type="rule_config",
        user_id=current_user.id,
        entity_id=None,
        detail={
            "rule_code": code,
            "is_enabled": cfg.is_enabled,
            "severity_override": cfg.severity_override,
            "thresholds": cfg.thresholds,
        },
    )

    await db.commit()
    await db.refresh(cfg)

    count_stmt = select(func.count(Violation.id)).where(Violation.rule_code == code)
    count_res = await db.execute(count_stmt)
    trigger_count = count_res.scalar_one()

    effective_severity = cfg.severity_override if cfg.severity_override else rule_def.severity

    return RuleResponse(
        id=rule_def.id,
        title=rule_def.title,
        citation=rule_def.citation,
        severity=rule_def.severity,
        effective_severity=effective_severity,
        applies_to=rule_def.applies_to,
        check=rule_def.check,
        params=rule_def.params,
        description_plain=rule_def.description_plain,
        mandatory=rule_def.mandatory,
        is_enabled=cfg.is_enabled,
        severity_override=cfg.severity_override,
        thresholds=cfg.thresholds,
        trigger_count=trigger_count,
    )
