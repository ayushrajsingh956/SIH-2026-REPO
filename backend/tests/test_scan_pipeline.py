import uuid
from unittest.mock import patch

import cv2
import numpy as np
import pytest
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.extraction import Extraction
from app.models.scan import Scan
from app.models.user import User
from app.schemas.extraction import (
    ConsumerCareField,
    DateField,
    ExtractionFields,
    ExtractionResultSchema,
    MRPField,
    NetQuantityField,
    StandardTextField,
    TextBlock,
)
from app.tasks.scan_pipeline import scan_pipeline_task


def create_sample_label_image() -> bytes:
    """Generates a clean product label test image with standard declarations."""
    img = np.ones((400, 600, 3), dtype=np.uint8) * 255
    # Draw label text
    cv2.putText(
        img, "ORGANIC HERBAL SHAMPOO", (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2
    )
    cv2.putText(img, "Net Qty: 500 ml", (30, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    cv2.putText(
        img,
        "MRP: Rs. 299/- (Inclusive of all taxes)",
        (30, 160),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (0, 0, 0),
        2,
    )
    cv2.putText(img, "Mfg Date: 02/2026", (30, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 2)
    cv2.putText(
        img, "Mfd by: Apex Naturals Pvt Ltd", (30, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2
    )
    cv2.putText(img, "New Delhi - 110020", (30, 300), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
    cv2.putText(
        img,
        "Care: +91 9876543210 / care@apex.in",
        (30, 340),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 0, 0),
        2,
    )
    _, png_bytes = cv2.imencode(".png", img)
    return png_bytes.tobytes()


@pytest.fixture
async def sample_scan_record() -> tuple[Scan, User]:
    async with AsyncSessionLocal() as session:
        user = User(
            name="Pipeline Inspector",
            email=f"inspector_{uuid.uuid4().hex[:8]}@example.com",
            password_hash=get_password_hash("ValidPass123!"),
            role="inspector",
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        scan = Scan(
            id=uuid.uuid4(),
            scanned_by=user.id,
            mode="retail",
            image_urls=["scans/mock/label.png"],
            status="queued",
            font_check_mode="relative",
        )
        session.add(scan)
        await session.commit()
        await session.refresh(scan)
        return scan, user


class TestScanPipelineIntegration:
    async def test_happy_path_gemini_extraction(self, sample_scan_record):
        scan, _ = sample_scan_record
        sample_png = create_sample_label_image()

        # Recorded Gemini fixture response matching Spec §6
        mock_gemini_result = ExtractionResultSchema(
            fields=ExtractionFields(
                manufacturer_name=StandardTextField(
                    raw="Apex Naturals Pvt Ltd",
                    normalized="Apex Naturals Pvt Ltd",
                    confidence=0.95,
                    bbox=[650.0, 50.0, 750.0, 500.0],
                ),
                manufacturer_address=StandardTextField(
                    raw="New Delhi - 110020",
                    normalized="New Delhi - 110020",
                    confidence=0.92,
                    bbox=[750.0, 50.0, 850.0, 400.0],
                ),
                net_quantity=NetQuantityField(
                    raw="500 ml",
                    value=500.0,
                    unit="ml",
                    confidence=0.97,
                    bbox=[250.0, 50.0, 350.0, 300.0],
                ),
                mrp=MRPField(
                    raw="₹ 299/- (Inclusive of all taxes)",
                    value=299.0,
                    currency="INR",
                    taxes_inclusive_text="Inclusive of all taxes",
                    confidence=0.96,
                    bbox=[350.0, 50.0, 450.0, 550.0],
                ),
                mfg_date=DateField(
                    raw="02/2026",
                    month=2,
                    year=2026,
                    confidence=0.94,
                    bbox=[450.0, 50.0, 550.0, 350.0],
                ),
                consumer_care=ConsumerCareField(
                    phone=["9876543210"],
                    email="care@apex.in",
                    confidence=0.91,
                    bbox=[850.0, 50.0, 950.0, 600.0],
                ),
                generic_name=StandardTextField(
                    raw="Organic Herbal Shampoo",
                    normalized="Organic Herbal Shampoo",
                    confidence=0.98,
                    bbox=[100.0, 50.0, 200.0, 500.0],
                ),
            ),
            detected_text_blocks=[
                TextBlock(
                    text="ORGANIC HERBAL SHAMPOO",
                    bbox=[100.0, 50.0, 200.0, 500.0],
                    estimated_char_height_px=24,
                ),
            ],
            page_count=1,
            language_hints=["en"],
            raw_text="ORGANIC HERBAL SHAMPOO\nNet Qty: 500 ml\nMRP: Rs. 299/-\nMfg: 02/2026",
        )

        with (
            patch("app.tasks.scan_pipeline.get_object_bytes", return_value=sample_png),
            patch(
                "app.tasks.scan_pipeline.put_object_bytes", return_value="scans/mock/processed.png"
            ),
            patch("app.tasks.scan_pipeline.settings.GEMINI_API_KEY", "mock-valid-gemini-key"),
            patch(
                "app.tasks.scan_pipeline.extract_with_gemini",
                return_value=(mock_gemini_result, 0.95),
            ),
            patch("app.tasks.scan_pipeline.publish_scan_event"),
        ):
            # Run pipeline task
            result = scan_pipeline_task(str(scan.id))
            assert result["status"] == "completed"

            # Check DB state
            async with AsyncSessionLocal() as session:
                refreshed_scan = await session.get(Scan, scan.id)
                assert refreshed_scan.status == "completed"
                assert refreshed_scan.pipeline_meta["provider"] == "gemini"
                assert refreshed_scan.pipeline_meta["avg_confidence"] == 0.95
                assert refreshed_scan.pipeline_meta["fallback_used"] is False

                # Check Extraction row
                extr_res = await session.execute(
                    select(Extraction).where(Extraction.scan_id == scan.id)
                )
                extr = extr_res.scalar_one()
                assert extr.fields["mrp"]["value"] == 299.0
                assert extr.fields["net_quantity"]["value"] == 500.0
                assert extr.fields["mfg_date"]["year"] == 2026
                assert len(extr.fields["mrp"]["bbox"]) == 4

    async def test_low_confidence_triggers_fallback_and_needs_review(self, sample_scan_record):
        scan, _ = sample_scan_record
        sample_png = create_sample_label_image()

        # Low confidence gemini mock (< 0.5)
        low_conf_result = ExtractionResultSchema()
        low_conf_result.fields.generic_name = StandardTextField(confidence=0.30, raw="Blurry text")

        with (
            patch("app.tasks.scan_pipeline.get_object_bytes", return_value=sample_png),
            patch(
                "app.tasks.scan_pipeline.put_object_bytes", return_value="scans/mock/processed.png"
            ),
            patch("app.tasks.scan_pipeline.settings.GEMINI_API_KEY", "mock-key"),
            patch(
                "app.tasks.scan_pipeline.extract_with_gemini", return_value=(low_conf_result, 0.30)
            ),
            patch("app.tasks.scan_pipeline.publish_scan_event"),
        ):
            result = scan_pipeline_task(str(scan.id))
            assert result["status"] == "needs_review"

            async with AsyncSessionLocal() as session:
                refreshed_scan = await session.get(Scan, scan.id)
                assert refreshed_scan.status == "needs_review"
                assert refreshed_scan.pipeline_meta["provider"] == "tesseract"
                assert refreshed_scan.pipeline_meta["fallback_used"] is True

                extr_res = await session.execute(
                    select(Extraction).where(Extraction.scan_id == scan.id)
                )
                extr = extr_res.scalar_one()
                # Ensure fields flagged source=ocr_fallback
                assert extr.fields["mrp"]["source"] == "ocr_fallback"

    async def test_gemini_api_failure_triggers_fallback(self, sample_scan_record):
        scan, _ = sample_scan_record
        sample_png = create_sample_label_image()

        with (
            patch("app.tasks.scan_pipeline.get_object_bytes", return_value=sample_png),
            patch(
                "app.tasks.scan_pipeline.put_object_bytes", return_value="scans/mock/processed.png"
            ),
            patch("app.tasks.scan_pipeline.settings.GEMINI_API_KEY", "mock-key"),
            patch(
                "app.tasks.scan_pipeline.extract_with_gemini",
                side_effect=Exception("API 503 Quota Exceeded"),
            ),
            patch("app.tasks.scan_pipeline.publish_scan_event"),
        ):
            result = scan_pipeline_task(str(scan.id))
            assert result["status"] == "needs_review"

            async with AsyncSessionLocal() as session:
                refreshed_scan = await session.get(Scan, scan.id)
                assert refreshed_scan.status == "needs_review"
                assert refreshed_scan.pipeline_meta["provider"] == "tesseract"
                assert refreshed_scan.pipeline_meta["fallback_used"] is True

    async def test_poison_image_marks_failed_without_crashing_worker(self, sample_scan_record):
        scan, _ = sample_scan_record
        poison_bytes = b"corrupted_binary_junk_not_an_image"

        with (
            patch("app.tasks.scan_pipeline.get_object_bytes", return_value=poison_bytes),
            patch("app.tasks.scan_pipeline.publish_scan_event"),
        ):
            # Must NOT raise unhandled exception or crash
            result = scan_pipeline_task(str(scan.id))
            assert result["status"] == "failed"
            assert "error" in result

            async with AsyncSessionLocal() as session:
                refreshed_scan = await session.get(Scan, scan.id)
                assert refreshed_scan.status == "failed"
                assert "error" in refreshed_scan.pipeline_meta

    async def test_task_exhausted_retries_marks_scan_failed(self, sample_scan_record):
        scan, _ = sample_scan_record

        with (
            patch(
                "app.tasks.scan_pipeline.get_object_bytes",
                side_effect=ConnectionError("MinIO connection reset"),
            ),
            patch("app.tasks.scan_pipeline.publish_scan_event"),
            patch.object(scan_pipeline_task, "max_retries", 2),
        ):
            # Set task request retries to max_retries
            scan_pipeline_task.request.retries = 2

            result = scan_pipeline_task(str(scan.id))
            assert result["status"] == "failed"
            assert "Exceeded max retries" in result["error"]

            async with AsyncSessionLocal() as session:
                refreshed_scan = await session.get(Scan, scan.id)
                assert refreshed_scan.status == "failed"
                assert "Exceeded max retries" in refreshed_scan.pipeline_meta["error"]
