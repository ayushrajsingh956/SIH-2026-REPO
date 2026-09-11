import asyncio
import json
import logging
import uuid

import httpx
from bs4 import BeautifulSoup
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
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

router = APIRouter(prefix="/scans", tags=["Scans"])


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ScanCreateResponse,
    summary="Upload packaged commodity photos and enqueue compliance scan (Admin/Inspector)",
)
async def create_scan(
    images: list[UploadFile] = File(...),
    mode: str = Form(default="retail"),
    font_check_mode: str = Form(default="relative"),
    surface_area_cm2: float | None = Form(default=None),
    current_user: User = Depends(require_role("admin", "inspector")),
    db: AsyncSession = Depends(get_db),
) -> ScanCreateResponse:
    # 1. Enforce images per scan limit
    if len(images) < 1 or len(images) > MAX_IMAGES_PER_SCAN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Images count must be between 1 and {MAX_IMAGES_PER_SCAN} per scan.",
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
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Image #{idx + 1} exceeds maximum allowed size limit of 10MB.",
                )
            chunks.append(chunk)

        data = b"".join(chunks)

        try:
            content_type, canonical_ext = validate_image_bytes(data, upload.filename)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Image #{idx + 1} rejected: {err}",
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
    scan_pipeline_task.delay(str(scan_id))

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
    # 1. SSRF Protection
    try:
        validated_url = validate_ssrf_url(payload.url)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        ) from err

    # 2. Fetch page content via HTTP client
    headers = {
        "User-Agent": "LegalMetro-Shield-Compliance-Bot/1.0 (+https://legalmetro.gov.in)",
        "Accept": "text/html,application/xhtml+xml",
    }
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(validated_url, headers=headers)
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Failed to fetch e-commerce page (HTTP {resp.status_code})",
                )
            html_text = resp.text
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Connection error while fetching URL: {exc}",
        ) from exc

    # 3. Parse OpenGraph and image tags
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
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No product images found at the provided URL.",
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

    # 4. Download images (up to 6) and validate magic bytes
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        for idx, img_url in enumerate(image_candidates[:MAX_IMAGES_PER_SCAN]):
            try:
                # SSRF check on target image URL
                safe_img_url = validate_ssrf_url(img_url)
                img_resp = await client.get(safe_img_url)
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
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Failed to download any valid images from the listing.",
        )

    # 5. Persist Scan
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
            "url": validated_url,
            "title": title,
            "images_count": len(stored_keys),
        },
    )
    db.add(scan)
    await db.commit()

    # 6. Enqueue Celery pipeline task
    scan_pipeline_task.delay(str(scan_id))

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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan {id} not found.",
        )

    # Generate presigned URLs for client viewing
    presigned: list[str] = []
    for key in scan.image_urls:
        try:
            presigned.append(presign_get_url(key))
        except Exception:
            presigned.append(key)

    extraction_dict = None
    if scan.extraction:
        extraction_dict = {
            "fields": scan.extraction.fields,
            "raw_text": scan.extraction.raw_text,
            "model": scan.extraction.model,
            "created_at": scan.extraction.created_at,
        }

    violations_list = [
        {
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
        for v in scan.violations
    ]

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
        image_urls=scan.image_urls,
        presigned_image_urls=presigned,
        pipeline_meta=scan.pipeline_meta,
        scanned_at=scan.scanned_at,
        extraction=extraction_dict,
        violations=violations_list,
    )


@router.get(
    "",
    response_model=ScanListResponse,
    summary="List scans with pagination and filters",
)
async def list_scans(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(require_role("admin", "inspector", "viewer")),
    db: AsyncSession = Depends(get_db),
) -> ScanListResponse:
    count_stmt = select(func.count(Scan.id))
    total_res = await db.execute(count_stmt)
    total = total_res.scalar_one()

    stmt = (
        select(Scan)
        .options(selectinload(Scan.extraction), selectinload(Scan.violations))
        .order_by(desc(Scan.scanned_at))
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    scans = result.scalars().all()

    items = []
    for scan in scans:
        extraction_dict = None
        if scan.extraction:
            extraction_dict = {
                "fields": scan.extraction.fields,
                "raw_text": scan.extraction.raw_text,
                "model": scan.extraction.model,
                "created_at": scan.extraction.created_at,
            }
        violations_list = [
            {
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
            for v in scan.violations
        ]
        items.append(
            ScanDetailResponse(
                id=scan.id,
                product_id=scan.product_id,
                scanned_by=scan.scanned_by,
                mode=scan.mode,
                status=scan.status,
                verdict=scan.verdict,
                compliance_score=scan.compliance_score,
                font_check_mode=scan.font_check_mode,
                surface_area_cm2=scan.surface_area_cm2,
                image_urls=scan.image_urls,
                pipeline_meta=scan.pipeline_meta,
                scanned_at=scan.scanned_at,
                extraction=extraction_dict,
                violations=violations_list,
            )
        )

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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan {id} not found.",
        )
    if not scan.extraction:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scan has no extracted fields to update.",
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

    score, verdict = compute_score_and_verdict(
        violations=violations,
        needs_review_flag=needs_review_flag,
    )

    # Remove existing violations and replace with new evaluation results
    for old_v in list(scan.violations):
        await db.delete(old_v)
    scan.violations = []

    new_violations: list[Violation] = []
    for v in violations:
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
            overridden=False,
        )
        db.add(vm)
        new_violations.append(vm)

    scan.violations = new_violations
    scan.compliance_score = score
    scan.verdict = verdict
    if scan.status == "needs_review" and verdict != "needs_review":
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

    presigned = []
    for key in refreshed_scan.image_urls:
        try:
            presigned.append(presign_get_url(key))
        except Exception:
            presigned.append(key)

    violations_list = [
        {
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
        for v in refreshed_scan.violations
    ]

    extraction_dict = {
        "fields": refreshed_scan.extraction.fields,
        "raw_text": refreshed_scan.extraction.raw_text,
        "model": refreshed_scan.extraction.model,
        "created_at": refreshed_scan.extraction.created_at,
    }

    return ScanDetailResponse(
        id=refreshed_scan.id,
        product_id=refreshed_scan.product_id,
        scanned_by=refreshed_scan.scanned_by,
        mode=refreshed_scan.mode,
        status=refreshed_scan.status,
        verdict=refreshed_scan.verdict,
        compliance_score=refreshed_scan.compliance_score,
        font_check_mode=refreshed_scan.font_check_mode,
        surface_area_cm2=refreshed_scan.surface_area_cm2,
        image_urls=refreshed_scan.image_urls,
        presigned_image_urls=presigned,
        pipeline_meta=refreshed_scan.pipeline_meta,
        scanned_at=refreshed_scan.scanned_at,
        extraction=extraction_dict,
        violations=violations_list,
    )


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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Violation {vid} for scan {id} not found.",
        )

    # 2. Mark overridden
    violation.overridden = True
    violation.override_reason = request.reason

    # 3. Load all violations for scan to recompute compliance score
    all_v_stmt = select(Violation).where(Violation.scan_id == id)
    all_violations = (await db.execute(all_v_stmt)).scalars().all()

    new_score, new_verdict = compute_score_and_verdict(all_violations)

    # 4. Update scan score & verdict
    scan_stmt = select(Scan).where(Scan.id == id)
    scan = (await db.execute(scan_stmt)).scalar_one_or_none()
    if scan:
        scan.compliance_score = new_score
        scan.verdict = new_verdict

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
    # 1. Verify scan exists
    stmt = select(Scan).where(Scan.id == id)
    result = await db.execute(stmt)
    scan = result.scalar_one_or_none()

    if not scan:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()

    # 2. Push initial current state
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

    # 3. Subscribe to Redis pub/sub channel
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
