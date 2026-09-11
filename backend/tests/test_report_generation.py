import io
import uuid

import pytest
from docx import Document
from httpx import AsyncClient
from pypdf import PdfReader
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, get_password_hash
from app.models.extraction import Extraction
from app.models.product import Product
from app.models.report import Report
from app.models.scan import Scan
from app.models.user import User
from app.models.violation import Violation
from app.services.reports.docx_generator import generate_docx_report
from app.services.reports.pdf_generator import generate_pdf_report


async def create_fixture_scan() -> tuple[Scan, User]:
    """Creates a comprehensive scan with extraction and violations for reporting tests."""
    async with AsyncSessionLocal() as session:
        user = User(
            name="Insp. Rajesh Sharma",
            email=f"rajesh_{uuid.uuid4().hex[:6]}@legalmetro.gov.in",
            password_hash=get_password_hash("InspectPass123!"),
            role="inspector",
            district="Central Delhi",
            state="Delhi",
            is_active=True,
        )
        session.add(user)
        await session.flush()

        product = Product(
            name="Organic Sunflower Cooking Oil 1L",
            brand="Prakriti Agro",
            manufacturer_name="Prakriti Foods Pvt Ltd",
            category="Edible Oils",
            barcode=f"890123{uuid.uuid4().hex[:6]}",
        )
        session.add(product)
        await session.flush()

        scan = Scan(
            product_id=product.id,
            scanned_by=user.id,
            mode="retail",
            image_urls=["scans/sample/oil_bottle.jpg"],
            status="completed",
            verdict="non_compliant",
            compliance_score=70.0,
            font_check_mode="relative",
            pipeline_meta={"model": "gemini-2.5-flash"},
        )
        session.add(scan)
        await session.flush()

        extraction = Extraction(
            scan_id=scan.id,
            fields={
                "manufacturer_name": {"raw": "Prakriti Foods Pvt Ltd", "confidence": 0.96},
                "manufacturer_address": {
                    "raw": "Plot 42, Industrial Area, Okhla, New Delhi",
                    "confidence": 0.94,
                },
                "country_of_origin": {"raw": "India", "confidence": 0.98},
                "net_quantity": {"raw": "1 Litre", "normalized": "1000 ml", "confidence": 0.95},
                "mrp": {"raw": "Rs. 220/-", "normalized": 220.0, "confidence": 0.92},
                "mfg_date": {"raw": "01/2026", "confidence": 0.90},
                "consumer_care": {"raw": "care@prakriti.in, +91-11-23456789", "confidence": 0.91},
            },
            raw_text="Prakriti Agro Organic Sunflower Oil 1 Litre MRP Rs. 220/- Mfg 01/2026",
            model="gemini-2.5-flash",
        )
        session.add(extraction)

        violation1 = Violation(
            scan_id=scan.id,
            rule_code="LMPC-R6-1e",
            rule_title="MRP Format Non-Conformity",
            citation="Rule 6(1)(e), LMPC Rules 2011",
            severity="major",
            field_name="mrp",
            observed_value="Rs. 220/- (Missing 'inclusive of all taxes')",
            expected_value="Maximum Retail Price Rs. 220/- (inclusive of all taxes)",
            overridden=False,
        )
        violation2 = Violation(
            scan_id=scan.id,
            rule_code="LMPC-R9-3",
            rule_title="Net Quantity Font Size Non-Conformity",
            citation="Rule 9(3), LMPC Rules 2011",
            severity="minor",
            field_name="net_quantity",
            observed_value="Font height 2.5 mm",
            expected_value="Minimum height 4.0 mm for > 500g/ml volume",
            overridden=False,
        )
        session.add_all([violation1, violation2])

        await session.commit()
        await session.refresh(scan)
        # Load relationships
        res = await session.execute(select(Scan).where(Scan.id == scan.id))
        loaded_scan = res.scalar_one()

    return loaded_scan, user


@pytest.mark.anyio
class TestReportGeneration:
    async def test_weasyprint_pdf_bytes_are_valid(self):
        scan, user = await create_fixture_scan()
        # Query scan with all relationships
        async with AsyncSessionLocal() as session:
            from sqlalchemy.orm import selectinload

            stmt = (
                select(Scan)
                .options(
                    selectinload(Scan.product),
                    selectinload(Scan.inspector),
                    selectinload(Scan.extraction),
                    selectinload(Scan.violations),
                )
                .where(Scan.id == scan.id)
            )
            res = await session.execute(stmt)
            loaded_scan = res.scalar_one()

        pdf_bytes = generate_pdf_report(loaded_scan)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 1000
        assert pdf_bytes.startswith(b"%PDF")

        # Parse with pypdf to verify structural validity
        reader = PdfReader(io.BytesIO(pdf_bytes))
        assert len(reader.pages) >= 1

        # Extract text across pages and assert key report content
        all_text = " ".join([page.extract_text() for page in reader.pages])
        assert "STATUTORY COMPLIANCE INSPECTION REPORT" in all_text
        assert "LEGAL METROLOGY" in all_text.upper()
        assert "LMPC-R6-1e" in all_text
        assert "Prakriti Foods" in all_text

    async def test_python_docx_bytes_are_valid(self):
        scan, user = await create_fixture_scan()
        async with AsyncSessionLocal() as session:
            from sqlalchemy.orm import selectinload

            stmt = (
                select(Scan)
                .options(
                    selectinload(Scan.product),
                    selectinload(Scan.inspector),
                    selectinload(Scan.extraction),
                    selectinload(Scan.violations),
                )
                .where(Scan.id == scan.id)
            )
            res = await session.execute(stmt)
            loaded_scan = res.scalar_one()

        docx_bytes = generate_docx_report(loaded_scan)
        assert isinstance(docx_bytes, bytes)
        assert len(docx_bytes) > 2000

        # Parse with python-docx
        doc = Document(io.BytesIO(docx_bytes))
        paragraphs_text = [p.text for p in doc.paragraphs if p.text]
        doc_full_text = " ".join(paragraphs_text)

        assert "GOVERNMENT OF INDIA" in doc_full_text
        assert "STATUTORY COMPLIANCE INSPECTION REPORT" in doc_full_text

        # Verify tables exist in docx
        assert len(doc.tables) >= 3  # metadata, verdict, violations/declarations
        table_text = " ".join(
            [cell.text for t in doc.tables for row in t.rows for cell in row.cells]
        )
        assert "LMPC-R6-1e" in table_text
        assert "Rule 6(1)(e)" in table_text
        assert "Prakriti Foods" in table_text

    async def test_post_reports_api_generates_both_and_persists_row(
        self,
        async_client: AsyncClient,
        monkeypatch,
    ):
        scan, user = await create_fixture_scan()
        token = create_access_token(user_id=user.id, role=user.role)

        # Mock put_object_bytes to prevent external network requirements
        uploaded_objects = {}

        def mock_put_object_bytes(
            object_name: str, data: bytes, content_type: str, bucket_name: str | None = None
        ):
            uploaded_objects[object_name] = (data, content_type)
            return object_name

        monkeypatch.setattr("app.services.reports.service.put_object_bytes", mock_put_object_bytes)

        response = await async_client.post(
            "/api/v1/reports",
            json={"scan_id": str(scan.id)},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["scan_id"] == str(scan.id)
        assert data["pdf_url"].endswith(".pdf")
        assert data["docx_url"].endswith(".docx")
        assert data["generator_name"] == user.name
        assert data["scan_verdict"] == "non_compliant"
        assert data["scan_score"] == 70.0

        # Verify Report was stored in DB
        async with AsyncSessionLocal() as session:
            stmt = select(Report).where(Report.id == uuid.UUID(data["id"]))
            res = await session.execute(stmt)
            report_row = res.scalar_one_or_none()
            assert report_row is not None
            assert report_row.scan_id == scan.id
            assert report_row.generated_by == user.id

        # Verify both PDF and DOCX bytes were uploaded
        assert data["pdf_url"] in uploaded_objects
        assert data["docx_url"] in uploaded_objects
        assert uploaded_objects[data["pdf_url"]][1] == "application/pdf"
        assert "officedocument.wordprocessingml" in uploaded_objects[data["docx_url"]][1]
