import uuid
from collections import defaultdict

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import require_role
from app.core.exceptions import ProblemDetailException
from app.core.pagination import paginate
from app.models.product import Product
from app.models.scan import Scan
from app.models.user import User
from app.models.violation import Violation
from app.schemas.product import (
    ProductDetailResponse,
    ProductListItem,
    ProductListResponse,
    ProductScanItem,
    ProductScansResponse,
    ProductScanViolationSummary,
    RecurrentViolationItem,
)

router = APIRouter(prefix="/products", tags=["Products"])


@router.get(
    "", response_model=ProductListResponse, summary="List products with FTS / trigram search"
)
async def list_products(
    q: str | None = Query(
        None, description="Search query by name, brand, manufacturer, or barcode"
    ),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=500),
    current_user: User = Depends(require_role("admin", "inspector", "viewer")),
    db: AsyncSession = Depends(get_db),
) -> ProductListResponse:
    query = select(Product)

    if q and q.strip():
        term = q.strip()
        # Combination of ILIKE and FTS vector matching
        query = query.where(
            Product.name.ilike(f"%{term}%")
            | Product.brand.ilike(f"%{term}%")
            | Product.manufacturer_name.ilike(f"%{term}%")
            | Product.barcode.ilike(f"%{term}%")
            | Product.gtin.ilike(f"%{term}%")
        )

    products, total = await paginate(db, query, page, limit, Product.first_scanned.desc())

    if not products:
        return ProductListResponse(items=[], total=total, page=page, limit=limit)

    product_ids = [p.id for p in products]

    # Fetch latest scans for these products to compute compliance badge and last scan date
    scans_stmt = (
        select(Scan).where(Scan.product_id.in_(product_ids)).order_by(Scan.scanned_at.desc())
    )
    scans_res = await db.execute(scans_stmt)
    all_scans = scans_res.scalars().all()

    scans_by_product = defaultdict(list)
    for s in all_scans:
        scans_by_product[s.product_id].append(s)

    # Fetch violations count per product
    v_stmt = (
        select(Scan.product_id, func.count(Violation.id))
        .join(Violation, Violation.scan_id == Scan.id)
        .where(Scan.product_id.in_(product_ids))
        .group_by(Scan.product_id)
    )
    v_res = await db.execute(v_stmt)
    violations_count_by_product = {row[0]: row[1] for row in v_res.all()}

    items: list[ProductListItem] = []
    for p in products:
        p_scans = scans_by_product.get(p.id, [])
        total_scans = len(p_scans)
        last_scan = p_scans[0] if p_scans else None

        badge = "unscanned"
        latest_score = None
        last_scanned_at = None

        if last_scan:
            last_scanned_at = last_scan.scanned_at
            latest_score = last_scan.compliance_score
            if last_scan.verdict:
                badge = last_scan.verdict
            elif last_scan.status == "needs_review":
                badge = "needs_review"
            elif last_scan.status == "completed":
                badge = "compliant"

        items.append(
            ProductListItem(
                id=p.id,
                name=p.name,
                brand=p.brand,
                manufacturer_name=p.manufacturer_name,
                category=p.category,
                barcode=p.barcode,
                gtin=p.gtin,
                first_scanned=p.first_scanned,
                last_scanned_at=last_scanned_at,
                total_scans=total_scans,
                compliance_badge=badge,
                latest_score=latest_score,
                violations_count=violations_count_by_product.get(p.id, 0),
            )
        )

    return ProductListResponse(items=items, total=total, page=page, limit=limit)


def _compute_product_recurrence(scans: list[Scan]) -> tuple[bool, list[RecurrentViolationItem]]:
    # Map rule_code -> list of (scan_id, rule_title, citation, severity)
    rule_map = defaultdict(list)
    for s in scans:
        for v in s.violations:
            rule_map[v.rule_code].append((s.id, v.rule_title, v.citation, v.severity))

    recurrent: list[RecurrentViolationItem] = []
    for r_code, occurrences in rule_map.items():
        distinct_scans = list({occ[0] for occ in occurrences})
        if len(distinct_scans) > 1:
            first = occurrences[0]
            recurrent.append(
                RecurrentViolationItem(
                    rule_code=r_code,
                    rule_title=first[1],
                    citation=first[2],
                    severity=first[3],
                    count=len(occurrences),
                    scan_ids=distinct_scans,
                )
            )

    is_repeat_offender = len(recurrent) > 0
    return is_repeat_offender, sorted(recurrent, key=lambda r: r.count, reverse=True)


@router.get(
    "/{id}",
    response_model=ProductDetailResponse,
    summary="Get single product details and recurrence summary",
)
async def get_product_detail(
    id: uuid.UUID,
    current_user: User = Depends(require_role("admin", "inspector", "viewer")),
    db: AsyncSession = Depends(get_db),
) -> ProductDetailResponse:
    p_stmt = select(Product).where(Product.id == id)
    p_res = await db.execute(p_stmt)
    product = p_res.scalar_one_or_none()

    if not product:
        raise ProblemDetailException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Product Not Found",
            detail=f"Product '{id}' not found.",
            type_url="https://errors.legalmetro.gov.in/product-not-found",
        )

    scans_stmt = (
        select(Scan)
        .options(selectinload(Scan.violations))
        .where(Scan.product_id == id)
        .order_by(Scan.scanned_at.desc())
    )
    scans_res = await db.execute(scans_stmt)
    scans = scans_res.scalars().all()

    total_scans = len(scans)
    compliant_scans = sum(1 for s in scans if s.verdict == "compliant")
    compliance_rate = round((compliant_scans / total_scans * 100), 1) if total_scans > 0 else 0.0

    is_repeat, recurrent = _compute_product_recurrence(scans)

    return ProductDetailResponse(
        id=product.id,
        name=product.name,
        brand=product.brand,
        manufacturer_name=product.manufacturer_name,
        category=product.category,
        barcode=product.barcode,
        gtin=product.gtin,
        first_scanned=product.first_scanned,
        total_scans=total_scans,
        compliance_rate=compliance_rate,
        is_repeat_offender=is_repeat,
        recurrent_violations=recurrent,
    )


@router.get(
    "/{id}/scans",
    response_model=ProductScansResponse,
    summary="Get chronological scans and recurrence breakdown",
)
async def get_product_scans(
    id: uuid.UUID,
    current_user: User = Depends(require_role("admin", "inspector", "viewer")),
    db: AsyncSession = Depends(get_db),
) -> ProductScansResponse:
    p_stmt = select(Product).where(Product.id == id)
    p_res = await db.execute(p_stmt)
    product = p_res.scalar_one_or_none()

    if not product:
        raise ProblemDetailException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Product Not Found",
            detail=f"Product '{id}' not found.",
            type_url="https://errors.legalmetro.gov.in/product-not-found",
        )

    scans_stmt = (
        select(Scan)
        .options(selectinload(Scan.violations), selectinload(Scan.inspector))
        .where(Scan.product_id == id)
        .order_by(Scan.scanned_at.desc())
    )
    scans_res = await db.execute(scans_stmt)
    scans = scans_res.scalars().all()

    total_scans = len(scans)
    compliant_scans = sum(1 for s in scans if s.verdict == "compliant")
    compliance_rate = round((compliant_scans / total_scans * 100), 1) if total_scans > 0 else 0.0

    is_repeat, recurrent = _compute_product_recurrence(scans)

    detail = ProductDetailResponse(
        id=product.id,
        name=product.name,
        brand=product.brand,
        manufacturer_name=product.manufacturer_name,
        category=product.category,
        barcode=product.barcode,
        gtin=product.gtin,
        first_scanned=product.first_scanned,
        total_scans=total_scans,
        compliance_rate=compliance_rate,
        is_repeat_offender=is_repeat,
        recurrent_violations=recurrent,
    )

    scan_items = []
    for s in scans:
        v_summaries = [
            ProductScanViolationSummary(
                id=v.id,
                rule_code=v.rule_code,
                rule_title=v.rule_title,
                citation=v.citation,
                severity=v.severity,
                field_name=v.field_name,
                overridden=v.overridden,
            )
            for v in s.violations
        ]
        scan_items.append(
            ProductScanItem(
                id=s.id,
                mode=s.mode,
                status=s.status,
                verdict=s.verdict,
                compliance_score=s.compliance_score,
                scanned_at=s.scanned_at,
                inspector_name=s.inspector.name if s.inspector else None,
                violations=v_summaries,
            )
        )

    return ProductScansResponse(
        product=detail,
        scans=scan_items,
        is_repeat_offender=is_repeat,
        recurrent_violations=recurrent,
    )
