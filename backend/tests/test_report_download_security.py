import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, get_password_hash
from app.models.report import Report
from app.models.scan import Scan
from app.models.user import User


async def create_user_with_role(role: str, is_active: bool = True) -> tuple[User, str]:
    """Helper to create test users with specific roles and status."""
    async with AsyncSessionLocal() as session:
        user = User(
            name=f"Test {role.capitalize()}",
            email=f"user_{role}_{uuid.uuid4().hex[:6]}@legalmetro.gov.in",
            password_hash=get_password_hash("SecretPass123!"),
            role=role,
            district="North Delhi",
            state="Delhi",
            is_active=is_active,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    token = create_access_token(user_id=user.id, role=role)
    return user, token


async def create_fixture_report_and_scan(owner: User) -> Report:
    """Helper to create a Report in DB."""
    async with AsyncSessionLocal() as session:
        scan = Scan(
            scanned_by=owner.id,
            mode="retail",
            image_urls=["scans/sample.jpg"],
            status="completed",
            verdict="compliant",
            compliance_score=95.0,
            font_check_mode="relative",
        )
        session.add(scan)
        await session.flush()

        report_id = uuid.uuid4()
        report = Report(
            id=report_id,
            scan_id=scan.id,
            pdf_url=f"reports/{scan.id}/{report_id}.pdf",
            docx_url=f"reports/{scan.id}/{report_id}.docx",
            generated_by=owner.id,
            generated_at=datetime.now(UTC),
        )
        session.add(report)
        await session.commit()
        await session.refresh(report)
    return report


@pytest.mark.anyio
class TestReportDownloadSecurity:
    async def test_unauthenticated_request_returns_401(self, async_client: AsyncClient):
        random_id = uuid.uuid4()
        response = await async_client.get(f"/api/v1/reports/{random_id}/download?format=pdf")
        assert response.status_code == 401

    async def test_deactivated_user_returns_403(self, async_client: AsyncClient):
        inactive_user, token = await create_user_with_role("inspector", is_active=False)
        report = await create_fixture_report_and_scan(inactive_user)

        response = await async_client.get(
            f"/api/v1/reports/{report.id}/download?format=pdf",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        data = response.json()
        assert (
            "inactive" in data.get("detail", "").lower()
            or "pending" in data.get("detail", "").lower()
        )

    async def test_admin_can_download_any_report(self, async_client: AsyncClient, monkeypatch):
        monkeypatch.setattr(
            "app.api.v1.reports.presign_get_url",
            lambda object_name, expires_seconds: (
                f"https://minio.test/{object_name}?signed=1&exp={expires_seconds}"
            ),
        )

        inspector, _ = await create_user_with_role("inspector")
        report = await create_fixture_report_and_scan(inspector)

        admin, admin_token = await create_user_with_role("admin")

        # Download PDF
        res_pdf = await async_client.get(
            f"/api/v1/reports/{report.id}/download?format=pdf",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res_pdf.status_code == 200
        data_pdf = res_pdf.json()
        assert data_pdf["format"] == "pdf"
        assert data_pdf["expires_in"] == 300
        assert "minio.test" in data_pdf["download_url"]
        assert data_pdf["filename"].endswith(".pdf")

        # Download DOCX
        res_docx = await async_client.get(
            f"/api/v1/reports/{report.id}/download?format=docx",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res_docx.status_code == 200
        data_docx = res_docx.json()
        assert data_docx["format"] == "docx"
        assert data_docx["expires_in"] == 300
        assert data_docx["filename"].endswith(".docx")

    async def test_inspector_can_download_reports(self, async_client: AsyncClient, monkeypatch):
        monkeypatch.setattr(
            "app.api.v1.reports.presign_get_url",
            lambda object_name, expires_seconds: (
                f"https://minio.test/{object_name}?signed=1&exp={expires_seconds}"
            ),
        )

        inspector1, token1 = await create_user_with_role("inspector")
        report = await create_fixture_report_and_scan(inspector1)

        response = await async_client.get(
            f"/api/v1/reports/{report.id}/download?format=pdf",
            headers={"Authorization": f"Bearer {token1}"},
        )
        assert response.status_code == 200
        assert response.json()["expires_in"] == 300

    async def test_viewer_without_ownership_is_forbidden_403(self, async_client: AsyncClient):
        inspector, _ = await create_user_with_role("inspector")
        report = await create_fixture_report_and_scan(inspector)

        other_viewer, viewer_token = await create_user_with_role("viewer")

        response = await async_client.get(
            f"/api/v1/reports/{report.id}/download?format=pdf",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert response.status_code == 403
        data = response.json()
        assert (
            "ownership" in data.get("detail", "").lower()
            or "viewers" in data.get("detail", "").lower()
        )

    async def test_viewer_with_ownership_is_permitted(self, async_client: AsyncClient, monkeypatch):
        monkeypatch.setattr(
            "app.api.v1.reports.presign_get_url",
            lambda object_name, expires_seconds: (
                f"https://minio.test/{object_name}?signed=1&exp={expires_seconds}"
            ),
        )

        viewer_owner, viewer_token = await create_user_with_role("viewer")
        report = await create_fixture_report_and_scan(viewer_owner)

        response = await async_client.get(
            f"/api/v1/reports/{report.id}/download?format=pdf",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert response.status_code == 200
        assert response.json()["format"] == "pdf"

    async def test_invalid_format_parameter_returns_400(self, async_client: AsyncClient):
        admin, admin_token = await create_user_with_role("admin")
        report = await create_fixture_report_and_scan(admin)

        for bad_format in ["exe", "txt", "sh", "html", "../../etc/passwd"]:
            response = await async_client.get(
                f"/api/v1/reports/{report.id}/download?format={bad_format}",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            assert response.status_code == 400
            assert "Unsupported Format" in response.json().get("title", "")

    async def test_non_existent_report_returns_404(self, async_client: AsyncClient):
        admin, admin_token = await create_user_with_role("admin")
        non_existent_id = uuid.uuid4()

        response = await async_client.get(
            f"/api/v1/reports/{non_existent_id}/download?format=pdf",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404
