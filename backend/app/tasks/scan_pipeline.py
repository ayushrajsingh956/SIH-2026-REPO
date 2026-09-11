import asyncio
import concurrent.futures
import json
import logging
import time
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.models.extraction import Extraction
from app.models.rule_config import RuleConfig
from app.models.scan import Scan
from app.models.violation import Violation
from app.services.extraction.gemini_extractor import extract_with_gemini
from app.services.extraction.groq_extractor import extract_with_groq
from app.services.extraction.preprocessor import preprocess_image
from app.services.extraction.prompts import CURRENT_PROMPT_VERSION
from app.services.extraction.tesseract_fallback import extract_with_tesseract_fallback
from app.services.notifications import get_notification_service
from app.services.rules import compute_score_and_verdict, evaluate_rules
from app.services.storage.minio_client import get_object_bytes, put_object_bytes
from app.services.storage.security import sanitize_storage_key, validate_image_bytes
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_task_engine = None
_TaskSessionLocal = None
_redis_pool = None


def get_task_session() -> AsyncSession:
    """Provides a dedicated async session with NullPool for Celery worker processes."""
    global _task_engine, _TaskSessionLocal
    if _task_engine is None:
        _task_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
        _TaskSessionLocal = async_sessionmaker(
            bind=_task_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
        )
    return _TaskSessionLocal()


def run_async(coro: Any) -> Any:
    """Safely executes an async coroutine from synchronous Celery task or async test environment."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()
    else:
        return asyncio.run(coro)


def get_redis_client() -> Any:
    """Provides a reusable Redis client using a shared connection pool."""
    global _redis_pool
    if _redis_pool is None:
        import redis

        _redis_pool = redis.ConnectionPool.from_url(settings.REDIS_URL)
    import redis

    return redis.Redis(connection_pool=_redis_pool)


def publish_scan_event(scan_id: str, event_data: dict[str, Any]) -> None:
    """Publishes real-time scan event to Redis pub/sub channel for WebSocket clients."""
    try:
        r = get_redis_client()
        r.publish(f"scan:{scan_id}:events", json.dumps(event_data))
    except Exception as exc:
        logger.debug("Failed to publish scan event to Redis: %s", exc)


async def _async_scan_pipeline(task_self: Any, scan_id: str) -> dict[str, Any]:
    """Async execution body for scan pipeline."""
    t_start = time.perf_counter()
    scan_uuid = uuid.UUID(scan_id)

    async with get_task_session() as session:
        # 1. Fetch scan
        stmt = select(Scan).where(Scan.id == scan_uuid)
        result = await session.execute(stmt)
        scan = result.scalar_one_or_none()

        if not scan:
            logger.error("Scan %s not found in database.", scan_id)
            return {"status": "error", "message": "Scan not found"}

        # 2. Update status -> processing (preprocessing stage)
        scan.status = "processing"
        scan.pipeline_meta = {
            "stage": "preprocessing",
            "attempt": task_self.request.retries + 1 if task_self else 1,
        }
        await session.commit()
        publish_scan_event(
            scan_id, {"scan_id": scan_id, "status": "processing", "stage": "preprocessing"}
        )

        # 3. Step A: Preprocess images
        t_prep_start = time.perf_counter()
        original_keys: list[str] = scan.image_urls or []
        if not original_keys:
            raise ValueError("Scan contains no original image URLs.")

        processed_keys: list[str] = []
        processed_buffers: list[bytes] = []
        prep_metadata: list[dict[str, Any]] = []

        for idx, orig_key in enumerate(original_keys):
            # Fetch from MinIO
            raw_bytes = get_object_bytes(orig_key)
            # Recheck magic bytes in worker to defend against poisoned payloads in storage
            validate_image_bytes(raw_bytes)
            # Preprocess with OpenCV
            proc_bytes, meta = preprocess_image(raw_bytes)
            # Store processed image in MinIO
            proc_key = sanitize_storage_key(scan_uuid, "processed", idx, "png")
            put_object_bytes(proc_key, proc_bytes, "image/png")

            processed_keys.append(proc_key)
            processed_buffers.append(proc_bytes)
            prep_metadata.append(meta)

        t_prep_duration = round((time.perf_counter() - t_prep_start) * 1000, 2)

        # 4. Step B & C: Extraction with Gemini + Tesseract Fallback
        meta = dict(scan.pipeline_meta or {})
        meta["stage"] = "extracting"
        scan.pipeline_meta = meta
        flag_modified(scan, "pipeline_meta")
        await session.commit()
        publish_scan_event(
            scan_id, {"scan_id": scan_id, "status": "processing", "stage": "extracting"}
        )

        t_extract_start = time.perf_counter()
        provider = settings.OCR_PROVIDER
        model_name = ""
        extraction_result = None
        avg_confidence = 0.0
        fallback_used = False
        fallback_chain: list[str] = []

        # Determine primary provider
        primary_provider = settings.OCR_PROVIDER
        if primary_provider == "gemini" and not settings.GEMINI_API_KEY and settings.GROQ_API_KEY:
            primary_provider = "groq"

        if primary_provider == "groq" and bool(settings.GROQ_API_KEY):
            fallback_chain.append(f"groq:{settings.GROQ_MODEL}")
            try:
                extraction_result, avg_confidence, model_used = extract_with_groq(
                    processed_buffers,
                    mime_types=["image/png"] * len(processed_buffers),
                )
                provider = "groq"
                model_name = model_used
                if avg_confidence < 0.5:
                    logger.warning(
                        "Groq extraction avg confidence (%s) < 0.5 for scan %s.",
                        avg_confidence,
                        scan_id,
                    )
                    fallback_used = True
            except Exception as exc:
                logger.warning("Groq extraction failed for scan %s: %s", scan_id, exc)
                fallback_used = True

            # Secondary fallback to Gemini if Groq failed or had low confidence
            if (fallback_used or extraction_result is None) and bool(settings.GEMINI_API_KEY):
                gemini_model = settings.GEMINI_MODEL or "gemini-3.1-flash-lite"
                fallback_chain.append(f"gemini:{gemini_model}")
                try:
                    extraction_result, avg_confidence = extract_with_gemini(
                        processed_buffers,
                        mime_types=["image/png"] * len(processed_buffers),
                    )
                    provider = "gemini"
                    model_name = gemini_model
                    if avg_confidence >= 0.5:
                        fallback_used = False
                except Exception as exc:
                    logger.warning("Gemini secondary fallback failed for scan %s: %s", scan_id, exc)

        elif primary_provider == "gemini" and bool(settings.GEMINI_API_KEY):
            gemini_model = settings.GEMINI_MODEL or "gemini-3.1-flash-lite"
            fallback_chain.append(f"gemini:{gemini_model}")
            try:
                extraction_result, avg_confidence = extract_with_gemini(
                    processed_buffers,
                    mime_types=["image/png"] * len(processed_buffers),
                )
                provider = "gemini"
                model_name = gemini_model
                if avg_confidence < 0.5:
                    logger.warning(
                        "Gemini extraction avg confidence (%s) < 0.5 for scan %s.",
                        avg_confidence,
                        scan_id,
                    )
                    fallback_used = True
            except Exception as exc:
                logger.warning("Gemini extraction failed for scan %s: %s", scan_id, exc)
                fallback_used = True

            # Secondary fallback to Groq if Gemini failed or had low confidence
            if (fallback_used or extraction_result is None) and bool(settings.GROQ_API_KEY):
                fallback_chain.append(f"groq:{settings.GROQ_MODEL}")
                try:
                    extraction_result, avg_confidence, model_used = extract_with_groq(
                        processed_buffers,
                        mime_types=["image/png"] * len(processed_buffers),
                    )
                    provider = "groq"
                    model_name = model_used
                    if avg_confidence >= 0.5:
                        fallback_used = False
                except Exception as exc:
                    logger.warning("Groq secondary fallback failed for scan %s: %s", scan_id, exc)
        else:
            fallback_used = True

        # Tertiary fallback to offline Tesseract OCR if cloud extractors failed or are unconfigured
        if fallback_used or extraction_result is None:
            fallback_chain.append("tesseract:tesseract-ocr-fallback")
            provider = "tesseract"
            model_name = "tesseract-ocr-fallback"
            extraction_result, avg_confidence = extract_with_tesseract_fallback(processed_buffers)
            fallback_used = True

        t_extract_duration = round((time.perf_counter() - t_extract_start) * 1000, 2)
        total_duration = round((time.perf_counter() - t_start) * 1000, 2)

        # 5. Evaluate Compliance Rules & Score
        rule_configs_res = await session.execute(select(RuleConfig))
        rule_configs = rule_configs_res.scalars().all()

        violations, needs_review_flag = evaluate_rules(
            fields=extraction_result.fields,
            scan_mode=scan.mode,
            surface_area_cm2=scan.surface_area_cm2,
            font_check_mode=scan.font_check_mode,
            detected_text_blocks=extraction_result.detected_text_blocks,
            raw_text=extraction_result.raw_text,
            rule_overrides=rule_configs,
        )

        score, verdict = compute_score_and_verdict(
            violations=violations,
            needs_review_flag=needs_review_flag,
            confidence_score=avg_confidence,
        )

        # Status Transition: completed / needs_review
        if avg_confidence < 0.6 or verdict == "needs_review":
            final_status = "needs_review"
        else:
            final_status = "completed"

        pipeline_meta = {
            "model": model_name,
            "provider": provider,
            "prompt_version": CURRENT_PROMPT_VERSION,
            "avg_confidence": avg_confidence,
            "fallback_used": fallback_used,
            "fallback_chain": fallback_chain,
            "compliance_score": score,
            "verdict": verdict,
            "violations_count": len(violations),
            "durations": {
                "preprocess_ms": t_prep_duration,
                "extract_ms": t_extract_duration,
                "total_ms": total_duration,
            },
            "processed_image_urls": processed_keys,
            "preprocessing_details": prep_metadata,
        }

        # 6. Persist Extraction & Violations & Update Scan
        existing_extr = await session.execute(
            select(Extraction).where(Extraction.scan_id == scan_uuid)
        )
        existing_obj = existing_extr.scalar_one_or_none()
        if existing_obj:
            await session.delete(existing_obj)

        existing_violations = await session.execute(
            select(Violation).where(Violation.scan_id == scan_uuid)
        )
        for ev in existing_violations.scalars().all():
            await session.delete(ev)

        extraction = Extraction(
            scan_id=scan.id,
            fields=extraction_result.fields.model_dump(),
            raw_text=extraction_result.raw_text,
            model=model_name,
        )
        session.add(extraction)

        for v in violations:
            violation_model = Violation(
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
            session.add(violation_model)

        scan.compliance_score = score
        scan.verdict = verdict
        scan.status = final_status
        scan.pipeline_meta = pipeline_meta
        await session.commit()

        # 7. Notify client of completion
        terminal_event = {
            "scan_id": scan_id,
            "status": final_status,
            "verdict": verdict,
            "compliance_score": score,
            "violations_count": len(violations),
            "pipeline_meta": pipeline_meta,
        }
        publish_scan_event(scan_id, terminal_event)

        # Trigger notification service if scan requires officer review
        if final_status == "needs_review":
            try:
                notif_svc = get_notification_service()
                await notif_svc.notify_scan_needs_review(
                    scan_id=scan_id,
                    reason=f"Scan completed with verdict '{verdict}' and confidence {avg_confidence:.2f}",
                    metadata={"confidence": avg_confidence, "score": score, "verdict": verdict},
                )
            except Exception as notif_err:
                logger.warning(
                    "Failed to dispatch needs_review notification for scan %s: %s",
                    scan_id,
                    notif_err,
                )

        logger.info(
            "Scan %s completed with status=%s, verdict=%s, score=%.1f, violations=%d",
            scan_id,
            final_status,
            verdict,
            score,
            len(violations),
        )
        return terminal_event


async def _async_mark_scan_failed(scan_id: str, error_msg: str) -> None:
    """Updates scan status to failed on unrecoverable error."""
    try:
        scan_uuid = uuid.UUID(scan_id)
        async with get_task_session() as session:
            stmt = select(Scan).where(Scan.id == scan_uuid)
            result = await session.execute(stmt)
            scan = result.scalar_one_or_none()
            if scan:
                scan.status = "failed"
                scan.pipeline_meta = {
                    **(scan.pipeline_meta or {}),
                    "error": error_msg,
                    "failed_at": time.time(),
                }
                await session.commit()
                publish_scan_event(
                    scan_id, {"scan_id": scan_id, "status": "failed", "error": error_msg}
                )
        # Trigger notification service on pipeline failure
        try:
            notif_svc = get_notification_service()
            await notif_svc.notify_scan_failed(
                scan_id=scan_id,
                error_msg=error_msg,
                metadata={"error": error_msg},
            )
        except Exception as notif_err:
            logger.warning(
                "Failed to dispatch failed notification for scan %s: %s", scan_id, notif_err
            )
    except Exception as exc:
        logger.error("Failed to mark scan %s as failed: %s", scan_id, exc)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=5,
    acks_late=True,
    retry_backoff=True,
    retry_jitter=True,
    rate_limit="30/m",
    name="scan_pipeline",
)
def scan_pipeline_task(self, scan_id: str) -> dict[str, Any]:
    """Celery task executing the complete label scan pipeline.

    Safe against worker crashes:
    - Retries up to 3 times on transient errors
    - Marks scan 'failed' upon exhausted retries or poison image
    """
    logger.info(
        "Starting scan_pipeline for scan_id=%s (attempt %d/%d)",
        scan_id,
        self.request.retries + 1,
        self.max_retries,
    )
    try:
        return run_async(_async_scan_pipeline(self, scan_id))
    except ValueError as val_err:
        # Poison image or bad input: unrecoverable, do not retry, mark failed
        logger.error("Poison image or unrecoverable error in scan %s: %s", scan_id, val_err)
        run_async(_async_mark_scan_failed(scan_id, str(val_err)))
        return {"scan_id": scan_id, "status": "failed", "error": str(val_err)}
    except Exception as exc:
        logger.exception("Unexpected error processing scan %s: %s", scan_id, exc)
        if self.request.retries < self.max_retries:
            logger.warning("Retrying scan %s (retry %d)...", scan_id, self.request.retries + 1)
            raise self.retry(exc=exc) from exc
        # All retries exhausted -> mark failed
        err_msg = f"Exceeded max retries: {exc}"
        run_async(_async_mark_scan_failed(scan_id, err_msg))
        return {"scan_id": scan_id, "status": "failed", "error": err_msg}
