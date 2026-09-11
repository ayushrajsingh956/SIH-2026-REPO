import asyncio
import json
import logging
import urllib.parse
import uuid
from typing import Any

import httpx
from bs4 import BeautifulSoup
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from redis.asyncio import from_url as redis_from_url
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.audit import record_audit_event
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import require_role
from app.core.exceptions import ProblemDetailException
from app.core.limiter import limiter
from app.core.security import decode_access_token
from app.models.rule_config import RuleConfig
from app.models.scan import Scan
from app.models.user import User
from app.models.violation import Violation
from app.schemas.rule import (
    ScanExtractionUpdateRequest,
    ViolationOverrideRequest,
    ViolationResponse,
)
from app.schemas.scan import (
    ScanCreateResponse,
    ScanDetailResponse,
    ScanListResponse,
    ScanUrlRequest,
)
from app.services.rules import compute_score_and_verdict, evaluate_rules
from app.services.storage.minio_client import presign_get_url, put_object_bytes
from app.services.storage.security import (
    MAX_IMAGE_SIZE_BYTES,
    MAX_IMAGES_PER_SCAN,
    sanitize_storage_key,
    validate_image_bytes,
    validate_ssrf_url,
)
from app.tasks.scan_pipeline import scan_pipeline_task

logger = logging.getLogger(__name__)


async def safe_http_get(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: float = 15.0,
    max_redirects: int = 3,
) -> httpx.Response:
    """Performs HTTP GET with SSRF re-validation at each redirect hop (max 3 hops)."""
    current_url = validate_ssrf_url(url)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        redirect_count = 0
        while True:
            resp = await client.get(current_url, headers=headers)
            if resp.is_redirect:
                redirect_count += 1
                if redirect_count > max_redirects:
                    raise ValueError("Too many redirects during URL fetch.")
                location = resp.headers.get("location")
                if not location:
                    raise ValueError("Redirect response missing Location header.")
                next_url = urllib.parse.urljoin(current_url, location)
                current_url = validate_ssrf_url(next_url)
                continue
            return resp


def serialize_violation(v: Violation) -> dict[str, Any]:
    return {
        "id": str(v.id),
        "scan_id": str(v.scan_id),
        "rule_code": v.rule_code,
        "rule_title": v.rule_title,
        "citation": v.citation,
        "severity": v.severity,
        "field_name": v.field_name,
        "observed_value": v.observed_value,
        "expected_value": v.expected_value,
        "bbox": v.bbox,
        "overridden": v.overridden,
        "override_reason": v.override_reason,
    }


def serialize_extraction(extraction: Any) -> dict[str, Any] | None:
    if not extraction:
        return None
    return {
        "fields": extraction.fields,
        "raw_text": extraction.raw_text,
        "model": extraction.model,
        "created_at": extraction.created_at,
    }


def serialize_scan_detail(scan: Scan, presign: bool = True) -> ScanDetailResponse:
    presigned: list[str] = []
    if presign and scan.image_urls:
        for key in scan.image_urls:
            try:
                presigned.append(presign_get_url(key))
            except Exception:
                presigned.append(key)

    return ScanDetailResponse(
        id=scan.id,
        product_id=scan.product_id,
        scanned_by=scan.scanned_by,
        mode=scan.mode,
        status=scan.status,
        verdict=scan.verdict,
        compliance_score=scan.compliance_score,
        font_check_mode=scan.font_check_mode,
        surface_area_cm2=scan.surface_area_cm2,
        image_urls=scan.image_urls or [],
        presigned_image_urls=presigned,
        pipeline_meta=scan.pipeline_meta or {},
        scanned_at=scan.scanned_at,
        extraction=serialize_extraction(scan.extraction),
        violations=[serialize_violation(v) for v in (scan.violations or [])],
    )


router = APIRouter(prefix="/scans", tags=["Scans"])


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ScanCreateResponse,
    summary="Upload packaged commodity photos and enqueue compliance scan (Admin/Inspector)",
)
@limiter.limit("30/minute")
async def create_scan(
    request: Request,
    images: list[UploadFile] = File(...),
    mode: str = Form(default="retail"),
    font_check_mode: str = Form(default="relative"),
    surface_area_cm2: float | None = Form(default=None),
    current_user: User = Depends(require_role("admin", "inspector")),
    db: AsyncSession = Depends(get_db),
) -> ScanCreateResponse:
    # 1. Enforce images per scan limit
    if len(images) < 1 or len(images) > MAX_IMAGES_PER_SCAN:
        raise ProblemDetailException(
            status_code=status.HTTP_400_BAD_REQUEST,
            title="Invalid Image Count",
            detail=f"Images count must be between 1 and {MAX_IMAGES_PER_SCAN} per scan.",
            type_url="https://errors.legalmetro.gov.in/invalid-image-count",
        )

    scan_id = uuid.uuid4()
    stored_keys: list[str] = []

    # 2. Process each image stream with size limits & magic byte verification
    for idx, upload in enumerate(images):
        # Stream read with 10MB limit enforcement
        total_read = 0
        chunks = []
        while True:
            chunk = await upload.read(1024 * 1024)  # 1MB chunks
            if not chunk:
                break
            total_read += len(chunk)
            if total_read > MAX_IMAGE_SIZE_BYTES:
                raise ProblemDetailException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    title="Image Too Large",
                    detail=f"Image #{idx + 1} exceeds maximum allowed size limit of 10MB.",
                    type_url="https://errors.legalmetro.gov.in/image-too-large",
                )
            chunks.append(chunk)

        data = b"".join(chunks)

        try:
            content_type, canonical_ext = validate_image_bytes(data, upload.filename)
        except ValueError as err:
            raise ProblemDetailException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                title="Unsupported Media Type",
                detail=f"Image #{idx + 1} rejected: {err}",
                type_url="https://errors.legalmetro.gov.in/unsupported-media-type",
            ) from err

        # 3. Store to MinIO with sanitized UUID key (never trust client filename)
        storage_key = sanitize_storage_key(scan_id, "original", idx, canonical_ext)
        put_object_bytes(storage_key, data, content_type)
        stored_keys.append(storage_key)

    # 4. Create Scan record in DB
    scan = Scan(
        id=scan_id,
        scanned_by=current_user.id,
        mode=mode,
        image_urls=stored_keys,
        status="queued",
        font_check_mode=font_check_mode,
        surface_area_cm2=surface_area_cm2,
        pipeline_meta={"images_count": len(stored_keys), "source": "multipart_upload"},
    )
    db.add(scan)
    await db.commit()

    # 5. Enqueue Celery pipeline task
    try:
        scan_pipeline_task.delay(str(scan_id))
    except Exception as exc:
        logger.error("Failed to enqueue scan %s to Celery: %s", scan_id, exc)
        scan.status = "failed"
        scan.pipeline_meta = {"error": "Queue service unavailable", "detail": str(exc)}
        await db.commit()
        raise ProblemDetailException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            title="Service Unavailable",
            detail="Scan processing queue is currently unavailable. Please try again later.",
            type_url="https://errors.legalmetro.gov.in/queue-unavailable",
        ) from exc

    return ScanCreateResponse(
        scan_id=str(scan_id),
        status="queued",
        message="Scan initiated and queued successfully",
        images_count=len(stored_keys),
    )


@router.post(
    "/url",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ScanCreateResponse,
    summary="Scrape e-commerce product page, extract og:image set, and enqueue scan",
)
async def create_scan_from_url(
    payload: ScanUrlRequest,
    current_user: User = Depends(require_role("admin", "inspector")),
    db: AsyncSession = Depends(get_db),
) -> ScanCreateResponse:
    # 1. Fetch page content via safe HTTP client (hop-by-hop SSRF validation)
    headers = {
        "User-Agent": "LegalMetro-Shield-Compliance-Bot/1.0 (+https://legalmetro.gov.in)",
        "Accept": "text/html,application/xhtml+xml",
    }
    try:
        resp = await safe_http_get(payload.url, headers=headers, timeout=15.0, max_redirects=3)
        if resp.status_code != 200:
            raise ProblemDetailException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                title="E-Commerce Page Fetch Failed",
                detail=f"Failed to fetch e-commerce page (HTTP {resp.status_code})",
                type_url="https://errors.legalmetro.gov.in/page-fetch-failed",
            )
        html_text = resp.text
    except ValueError as err:
        raise ProblemDetailException(
            status_code=status.HTTP_400_BAD_REQUEST,
            title="SSRF Prohibited",
            detail=str(err),
            type_url="https://errors.legalmetro.gov.in/ssrf-prohibited",
        ) from err
    except httpx.RequestError as exc:
        raise ProblemDetailException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            title="Connection Error",
            detail=f"Connection error while fetching URL: {exc}",
            type_url="https://errors.legalmetro.gov.in/connection-error",
        ) from exc

    # 2. Parse OpenGraph and image tags
    soup = BeautifulSoup(html_text, "html.parser")
    image_candidates: list[str] = []

    # og:image
    for meta_tag in soup.find_all("meta", property="og:image"):
        img_url = meta_tag.get("content")
        if img_url and img_url not in image_candidates:
            image_candidates.append(img_url)

    # Fallback to standard <img> tags if no og:image
    if not image_candidates:
        for img_tag in soup.find_all("img"):
            src = img_tag.get("src")
            if src and src.startswith("http") and src not in image_candidates:
                image_candidates.append(src)
            if len(image_candidates) >= MAX_IMAGES_PER_SCAN:
                break

    if not image_candidates:
        raise ProblemDetailException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            title="No Images Found",
            detail="No product images found at the provided URL.",
            type_url="https://errors.legalmetro.gov.in/no-images-found",
        )

    # Extract title
    title = None
    title_tag = soup.find("meta", property="og:title")
    if title_tag and title_tag.get("content"):
        title = title_tag.get("content")
    elif soup.title and soup.title.string:
        title = soup.title.string.strip()

    scan_id = uuid.uuid4()
    stored_keys: list[str] = []

    # 3. Download images (up to 6) and validate magic bytes with safe_http_get
    for idx, img_url in enumerate(image_candidates[:MAX_IMAGES_PER_SCAN]):
        try:
            img_resp = await safe_http_get(img_url, timeout=15.0, max_redirects=3)
            if img_resp.status_code == 200 and len(img_resp.content) > 0:
                data = img_resp.content
                if len(data) > MAX_IMAGE_SIZE_BYTES:
                    continue
                content_type, canonical_ext = validate_image_bytes(data)
                storage_key = sanitize_storage_key(scan_id, "original", idx, canonical_ext)
                put_object_bytes(storage_key, data, content_type)
                stored_keys.append(storage_key)
        except Exception as exc:
            logger.warning("Failed downloading product image %s: %s", img_url, exc)

    if not stored_keys:
        raise ProblemDetailException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            title="Image Download Failed",
            detail="Failed to download any valid images from the listing.",
            type_url="https://errors.legalmetro.gov.in/image-download-failed",
        )

    # 4. Persist Scan
    scan = Scan(
        id=scan_id,
        scanned_by=current_user.id,
        mode="ecommerce",
        image_urls=stored_keys,
        status="queued",
        font_check_mode=payload.font_check_mode,
        surface_area_cm2=payload.surface_area_cm2,
        pipeline_meta={
            "source": "ecommerce_url",
            "url": payload.url,
            "title": title,
            "images_count": len(stored_keys),
        },
    )
    db.add(scan)
    await db.commit()

    # 5. Enqueue Celery pipeline task
    try:
        scan_pipeline_task.delay(str(scan_id))
    except Exception as exc:
        logger.error("Failed to enqueue scan %s to Celery: %s", scan_id, exc)
        scan.status = "failed"
        scan.pipeline_meta = {"error": "Queue service unavailable", "detail": str(exc)}
        await db.commit()
        raise ProblemDetailException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            title="Service Unavailable",
            detail="Scan processing queue is currently unavailable. Please try again later.",
            type_url="https://errors.legalmetro.gov.in/queue-unavailable",
        ) from exc

    return ScanCreateResponse(
        scan_id=str(scan_id),
        status="queued",
        message="E-commerce scan initiated successfully",
        images_count=len(stored_keys),
    )


@router.get(
    "/{id}",
    response_model=ScanDetailResponse,
    summary="Polling endpoint for scan status and results",
)
async def get_scan_detail(
    id: uuid.UUID,
    current_user: User = Depends(require_role("admin", "inspector", "viewer")),
    db: AsyncSession = Depends(get_db),
) -> ScanDetailResponse:
    stmt = (
        select(Scan)
        .options(selectinload(Scan.extraction), selectinload(Scan.violations))
        .where(Scan.id == id)
    )
    result = await db.execute(stmt)
    scan = result.scalar_one_or_none()

    if not scan:
        raise ProblemDetailException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Scan Not Found",
            detail=f"Scan {id} not found.",
            type_url="https://errors.legalmetro.gov.in/scan-not-found",
        )

    return serialize_scan_detail(scan, presign=True)


@router.get(
    "",
    response_model=ScanListResponse,
    summary="List scans with pagination and filters",
)
async def list_scans(
    limit: int = 20,
    offset: int = 0,
    status: str | None = None,
    verdict: str | None = None,
    mode: str | None = None,
    current_user: User = Depends(require_role("admin", "inspector", "viewer")),
    db: AsyncSession = Depends(get_db),
) -> ScanListResponse:
    base_query = select(Scan)
    count_query = select(func.count(Scan.id))

    filters = []
    if status:
        filters.append(Scan.status == status)
    if verdict:
        filters.append(Scan.verdict == verdict)
    if mode:
        filters.append(Scan.mode == mode)

    if filters:
        base_query = base_query.where(*filters)
        count_query = count_query.where(*filters)

    total_res = await db.execute(count_query)
    total = total_res.scalar_one()

    stmt = (
        base_query.options(selectinload(Scan.extraction), selectinload(Scan.violations))
        .order_by(desc(Scan.scanned_at))
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    scans = result.scalars().all()

    items = [serialize_scan_detail(scan, presign=False) for scan in scans]
    return ScanListResponse(items=items, total=total)


@router.patch(
    "/{id}/extraction",
    response_model=ScanDetailResponse,
    summary="Inspector/Admin updates extraction fields and re-evaluates compliance rules",
)
async def update_scan_extraction(
    id: uuid.UUID,
    payload: ScanExtractionUpdateRequest,
    current_user: User = Depends(require_role("admin", "inspector")),
    db: AsyncSession = Depends(get_db),
) -> ScanDetailResponse:
    stmt = (
        select(Scan)
        .options(selectinload(Scan.extraction), selectinload(Scan.violations))
        .where(Scan.id == id)
    )
    result = await db.execute(stmt)
    scan = result.scalar_one_or_none()
    if not scan:
        raise ProblemDetailException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Scan Not Found",
            detail=f"Scan {id} not found.",
            type_url="https://errors.legalmetro.gov.in/scan-not-found",
        )
    if not scan.extraction:
        raise ProblemDetailException(
            status_code=status.HTTP_400_BAD_REQUEST,
            title="Extraction Missing",
            detail="Scan has no extracted fields to update.",
            type_url="https://errors.legalmetro.gov.in/extraction-missing",
        )

    # Deep merge or update current extraction fields
    current_fields = dict(scan.extraction.fields or {})
    for k, v in payload.fields.items():
        if isinstance(v, dict) and isinstance(current_fields.get(k), dict):
            current_fields[k].update(v)
        else:
            current_fields[k] = v

    scan.extraction.fields = current_fields

    # Load rule configurations
    rule_configs_res = await db.execute(select(RuleConfig))
    rule_configs = rule_configs_res.scalars().all()

    # Re-evaluate rules deterministically
    violations, needs_review_flag = evaluate_rules(
        fields=current_fields,
        scan_mode=scan.mode,
        surface_area_cm2=scan.surface_area_cm2,
        font_check_mode=scan.font_check_mode,
        raw_text=scan.extraction.raw_text,
        rule_overrides=rule_configs,
    )

    # Preserve existing inspector overrides matching (rule_code, field_name)
    existing_overrides = {
        (v.rule_code, v.field_name): (v.overridden, v.override_reason)
        for v in scan.violations
        if v.overridden
    }

    # Remove existing violations and replace with new evaluation results
    for old_v in list(scan.violations):
        await db.delete(old_v)
    scan.violations = []

    new_violations: list[Violation] = []
    active_violations_for_scoring: list[Any] = []
    for v in violations:
        key = (v.rule_code, v.field_name)
        was_overridden, reason = existing_overrides.get(key, (False, None))
        vm = Violation(
            scan_id=scan.id,
            rule_code=v.rule_code,
            rule_title=v.rule_title,
            citation=v.citation,
            severity=v.severity,
            field_name=v.field_name,
            observed_value=v.observed_value,
            expected_value=v.expected_value,
            bbox=v.bbox,
            overridden=was_overridden,
            override_reason=reason,
        )
        db.add(vm)
        new_violations.append(vm)
        if not was_overridden:
            active_violations_for_scoring.append(v)

    score, verdict = compute_score_and_verdict(
        violations=active_violations_for_scoring,
        needs_review_flag=needs_review_flag,
    )

    scan.violations = new_violations
    scan.compliance_score = score
    scan.verdict = verdict
    if scan.status in ("needs_review", "queued", "processing") and verdict != "needs_review":
        scan.status = "completed"

    # Audit log
    await record_audit_event(
        db=db,
        action="UPDATE_EXTRACTION",
        entity_type="scan",
        user_id=current_user.id,
        entity_id=scan.id,
        detail={
            "fields_updated": list(payload.fields.keys()),
            "new_score": score,
            "new_verdict": verdict,
            "violations_count": len(violations),
        },
    )

    await db.commit()
    db.expire_all()

    # Re-query with relations loaded
    refreshed_stmt = (
        select(Scan)
        .options(selectinload(Scan.extraction), selectinload(Scan.violations))
        .where(Scan.id == id)
    )
    refreshed_scan = (await db.execute(refreshed_stmt)).scalar_one()
    return serialize_scan_detail(refreshed_scan, presign=True)


@router.post(
    "/{id}/violations/{vid}/override",
    response_model=ViolationResponse,
    summary="Inspector/Admin overrides a rule violation with written justification",
)
async def override_scan_violation(
    id: uuid.UUID,
    vid: uuid.UUID,
    request: ViolationOverrideRequest,
    current_user: User = Depends(require_role("admin", "inspector")),
    db: AsyncSession = Depends(get_db),
) -> ViolationResponse:
    # 1. Fetch violation
    stmt = select(Violation).where(Violation.id == vid, Violation.scan_id == id)
    result = await db.execute(stmt)
    violation = result.scalar_one_or_none()

    if not violation:
        raise ProblemDetailException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Violation Not Found",
            detail=f"Violation {vid} for scan {id} not found.",
            type_url="https://errors.legalmetro.gov.in/violation-not-found",
        )

    # 2. Mark overridden
    violation.overridden = True
    violation.override_reason = request.reason

    # 3. Load all violations for scan to recompute compliance score
    all_v_stmt = select(Violation).where(Violation.scan_id == id)
    all_violations = (await db.execute(all_v_stmt)).scalars().all()

    new_score, new_verdict = compute_score_and_verdict(all_violations)

    # 4. Update scan score & verdict, and sync status to completed if compliant
    scan_stmt = select(Scan).where(Scan.id == id)
    scan = (await db.execute(scan_stmt)).scalar_one_or_none()
    if scan:
        scan.compliance_score = new_score
        scan.verdict = new_verdict
        if new_verdict == "compliant" and scan.status in ("needs_review", "queued", "processing"):
            scan.status = "completed"

    # 5. Record structured audit event
    await record_audit_event(
        db=db,
        action="OVERRIDE_VIOLATION",
        entity_type="violation",
        user_id=current_user.id,
        entity_id=violation.id,
        detail={
            "scan_id": str(id),
            "rule_code": violation.rule_code,
            "reason": request.reason,
            "new_compliance_score": new_score,
            "new_verdict": new_verdict,
        },
    )

    await db.commit()
    await db.refresh(violation)

    return ViolationResponse(
        id=str(violation.id),
        scan_id=str(violation.scan_id),
        rule_code=violation.rule_code,
        rule_title=violation.rule_title,
        citation=violation.citation,
        severity=violation.severity,
        field_name=violation.field_name,
        observed_value=violation.observed_value,
        expected_value=violation.expected_value,
        bbox=violation.bbox,
        overridden=violation.overridden,
        override_reason=violation.override_reason,
    )


@router.websocket("/{id}/events")
async def scan_events_websocket(
    websocket: WebSocket,
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """WebSocket endpoint pushing real-time status changes and progress updates."""
    # 1. Authenticate connection via token query parameter or Authorization header
    token = websocket.query_params.get("token")
    if not token:
        auth_hdr = websocket.headers.get("authorization")
        if auth_hdr and auth_hdr.startswith("Bearer "):
            token = auth_hdr.split(" ", 1)[1]

    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        token_payload = decode_access_token(token)
        user_id = uuid.UUID(token_payload["sub"])
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Verify user exists and is active
    user_stmt = select(User).where(User.id == user_id, User.is_active == True)  # noqa: E712
    user_res = await db.execute(user_stmt)
    user = user_res.scalar_one_or_none()
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # 2. Verify scan exists
    stmt = select(Scan).where(Scan.id == id)
    result = await db.execute(stmt)
    scan = result.scalar_one_or_none()

    if not scan:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()

    # 3. Push initial current state
    await websocket.send_json(
        {
            "scan_id": str(scan.id),
            "status": scan.status,
            "pipeline_meta": scan.pipeline_meta,
        }
    )

    # If scan is already completed/failed/needs_review, close cleanly
    if scan.status in ("completed", "needs_review", "failed"):
        await websocket.close(code=status.WS_1000_NORMAL_CLOSURE)
        return

    # 4. Subscribe to Redis pub/sub channel
    redis_client = None
    pubsub = None
    try:
        redis_client = redis_from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(f"scan:{id}:events")

        while True:
            # Poll for Redis message or client disconnect
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message.get("data"):
                try:
                    event_payload = json.loads(message["data"])
                    await websocket.send_json(event_payload)
                    if event_payload.get("status") in ("completed", "needs_review", "failed"):
                        break
                except Exception as exc:
                    logger.debug("Failed sending websocket event: %s", exc)
            await asyncio.sleep(0.1)

    except WebSocketDisconnect:
        logger.debug("Client disconnected from scan %s events", id)
    except Exception as exc:
        logger.warning("Error in scan websocket events: %s", exc)
    finally:
        if pubsub:
            await pubsub.unsubscribe(f"scan:{id}:events")
            await pubsub.aclose()
        if redis_client:
            await redis_client.aclose()
        try:
            await websocket.close()
        except Exception:
            pass
