import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ProblemDetailException
from app.models.report import Report
from app.models.scan import Scan
from app.models.user import User
from app.services.reports.docx_generator import generate_docx_report
from app.services.reports.pdf_generator import generate_pdf_report
from app.services.storage.minio_client import put_object_bytes

logger = logging.getLogger(__name__)


async def generate_scan_reports(
    scan_id: uuid.UUID,
    user: User,
    db: AsyncSession,
) -> Report:
    """Generates both PDF and DOCX statutory reports, uploads to MinIO, and creates Report record."""
    # 1. Fetch scan with all relationships eagerly loaded
    stmt = (
        select(Scan)
        .options(
            selectinload(Scan.product),
            selectinload(Scan.inspector),
            selectinload(Scan.extraction),
            selectinload(Scan.violations),
        )
        .where(Scan.id == scan_id)
    )
    res = await db.execute(stmt)
    scan = res.scalar_one_or_none()

    if not scan:
        raise ProblemDetailException(
            status_code=404,
            title="Scan Not Found",
            detail=f"Scan record '{scan_id}' does not exist.",
            type_url="https://errors.legalmetro.gov.in/scan-not-found",
        )

    report_id = uuid.uuid4()
    pdf_key = f"reports/{scan.id}/{report_id}.pdf"
    docx_key = f"reports/{scan.id}/{report_id}.docx"

    # 2. Generate PDF via WeasyPrint
    try:
        pdf_bytes = generate_pdf_report(scan)
        put_object_bytes(
            object_name=pdf_key,
            data=pdf_bytes,
            content_type="application/pdf",
        )
    except Exception as exc:
        logger.exception("Failed to generate or upload PDF report for scan %s: %s", scan_id, exc)
        raise ProblemDetailException(
            status_code=500,
            title="PDF Generation Error",
            detail=f"Failed to generate statutory PDF report: {exc}",
            type_url="https://errors.legalmetro.gov.in/report-generation-error",
        ) from exc

    # 3. Generate DOCX via python-docx
    try:
        docx_bytes = generate_docx_report(scan)
        put_object_bytes(
            object_name=docx_key,
            data=docx_bytes,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except Exception as exc:
        logger.exception("Failed to generate or upload DOCX report for scan %s: %s", scan_id, exc)
        raise ProblemDetailException(
            status_code=500,
            title="DOCX Generation Error",
            detail=f"Failed to generate editable DOCX report: {exc}",
            type_url="https://errors.legalmetro.gov.in/report-generation-error",
        ) from exc

    # 4. Save Report row in Postgres
    report = Report(
        id=report_id,
        scan_id=scan.id,
        pdf_url=pdf_key,
        docx_url=docx_key,
        generated_by=user.id,
        generated_at=datetime.now(UTC),
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    logger.info("Successfully generated statutory report %s for scan %s", report.id, scan.id)
    return report
