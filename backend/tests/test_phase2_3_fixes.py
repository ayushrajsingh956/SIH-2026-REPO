import uuid

import pytest
import respx
from httpx import AsyncClient
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api.v1.scans import safe_http_get
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, get_password_hash
from app.main import app
from app.models.extraction import Extraction
from app.models.scan import Scan
from app.models.user import User
from app.models.violation import Violation
from app.schemas.extraction import ExtractionFields, MRPField, NetQuantityField, TextBlock
from app.services.rules import evaluate_rules
from app.services.storage.security import validate_ssrf_url


async def create_user_with_role(role: str) -> tuple[User, str]:
    async with AsyncSessionLocal() as session:
        user = User(
            name=f"User {role}",
            email=f"{role}_{uuid.uuid4().hex[:8]}@example.com",
            password_hash=get_password_hash("ValidPassword123!"),
            role=role,
            is_active=True,
            district="District Test",
            state="State Test",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    token = create_access_token(user_id=user.id, role=role)
    return user, token


class TestSSRFRemediation:
    def test_multicast_and_reserved_ips_blocked(self):
        with pytest.raises(ValueError, match="Access to IP '224.0.0.1' is blocked"):
            validate_ssrf_url("http://224.0.0.1/test")

        with pytest.raises(ValueError, match="Access to IP '240.0.0.1' is blocked"):
            validate_ssrf_url("http://240.0.0.1/test")

        with pytest.raises(ValueError, match="Access to IP '127.0.0.1' is blocked"):
            validate_ssrf_url("http://127.0.0.1/")

        with pytest.raises(ValueError, match="Access to IP '169.254.169.254' is blocked"):
            validate_ssrf_url("http://169.254.169.254/latest/meta-data/")

    @pytest.mark.asyncio
    @respx.mock
    async def test_redirect_to_internal_metadata_blocked(self):
        # Initial safe URL responds with 302 redirecting to AWS metadata
        respx.get("https://example.com/product").respond(
            status_code=302,
            headers={"Location": "http://169.254.169.254/latest/meta-data/"},
        )

        with pytest.raises(ValueError, match="Access to IP '169.254.169.254' is blocked"):
            await safe_http_get("https://example.com/product")

    @pytest.mark.asyncio
    @respx.mock
    async def test_safe_redirect_followed(self):
        respx.get("https://example.com/start").respond(
            status_code=301,
            headers={"Location": "https://example.com/final"},
        )
        respx.get("https://example.com/final").respond(
            status_code=200,
            text="<html>Final Content</html>",
        )

        resp = await safe_http_get("https://example.com/start")
        assert resp.status_code == 200
        assert "Final Content" in resp.text


class TestWebSocketAuthentication:
    @pytest.mark.asyncio
    async def test_websocket_unauthenticated_connection_rejected_1008(self):
        user, _ = await create_user_with_role("inspector")
        scan_id = uuid.uuid4()
        async with AsyncSessionLocal() as session:
            scan = Scan(
                id=scan_id,
                scanned_by=user.id,
                mode="retail",
                image_urls=["scans/mock.png"],
                status="completed",
                pipeline_meta={},
            )
            session.add(scan)
            await session.commit()

        client = TestClient(app)
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/api/v1/scans/{scan_id}/events"):
                pass
        assert exc_info.value.code == 1008

    @pytest.mark.asyncio
    async def test_websocket_authenticated_connection_succeeds(self):
        user, token = await create_user_with_role("inspector")
        scan_id = uuid.uuid4()
        async with AsyncSessionLocal() as session:
            scan = Scan(
                id=scan_id,
                scanned_by=user.id,
                mode="retail",
                image_urls=["scans/mock.png"],
                status="completed",
                pipeline_meta={"stage": "done"},
            )
            session.add(scan)
            await session.commit()

        client = TestClient(app)
        with client.websocket_connect(f"/api/v1/scans/{scan_id}/events?token={token}") as ws:
            data = ws.receive_json()
            assert data["scan_id"] == str(scan_id)
            assert data["status"] == "completed"


class TestOverridePreservationAndStatusSync:
    @pytest.mark.asyncio
    async def test_patch_extraction_preserves_inspector_overrides(self, async_client: AsyncClient):
        inspector, token = await create_user_with_role("inspector")
        scan_id = uuid.uuid4()

        async with AsyncSessionLocal() as session:
            scan = Scan(
                id=scan_id,
                scanned_by=inspector.id,
                mode="retail",
                image_urls=["scans/test.png"],
                status="needs_review",
                compliance_score=50.0,
                verdict="non_compliant",
            )
            session.add(scan)
            await session.flush()

            extraction = Extraction(
                scan_id=scan_id,
                fields={
                    "manufacturer_name": {"raw": "Acme Ltd", "present": True},
                    "mrp": {
                        "raw": "₹100",
                        "value": 100.0,
                        "present": True,
                        "taxes_inclusive_text": None,
                    },
                },
                raw_text="Acme Ltd",
                model="gemini-2.5-flash",
            )
            session.add(extraction)

            # Add existing violation marked as overridden
            v = Violation(
                scan_id=scan_id,
                rule_code="LMPC-R9-1b",
                rule_title="MRP Taxes Inclusive Statement",
                citation="Rule 9(1)(b)",
                severity="major",
                field_name="mrp",
                observed_value="Missing",
                expected_value="Inclusive of all taxes",
                overridden=True,
                override_reason="Exempt under legal ruling 2026",
            )
            session.add(v)
            await session.commit()

        # Update extraction via PATCH
        headers = {"Authorization": f"Bearer {token}"}
        resp = await async_client.patch(
            f"/api/v1/scans/{scan_id}/extraction",
            headers=headers,
            json={
                "fields": {
                    "net_quantity": {"raw": "500 g", "value": 500.0, "unit": "g", "present": True}
                }
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        violations = data["violations"]

        # Find LMPC-R9-1b violation and assert overridden is preserved!
        r9_1b = next((v for v in violations if v["rule_code"] == "LMPC-R9-1b"), None)
        assert r9_1b is not None
        assert r9_1b["overridden"] is True
        assert r9_1b["override_reason"] == "Exempt under legal ruling 2026"

    @pytest.mark.asyncio
    async def test_override_flips_verdict_and_completes_scan_status(
        self, async_client: AsyncClient
    ):
        inspector, token = await create_user_with_role("inspector")
        scan_id = uuid.uuid4()
        viol_id = uuid.uuid4()

        async with AsyncSessionLocal() as session:
            scan = Scan(
                id=scan_id,
                scanned_by=inspector.id,
                mode="retail",
                image_urls=["scans/test.png"],
                status="needs_review",
                compliance_score=60.0,
                verdict="non_compliant",
            )
            session.add(scan)
            await session.flush()

            v = Violation(
                id=viol_id,
                scan_id=scan_id,
                rule_code="LMPC-R9-1b",
                rule_title="MRP Taxes Inclusive",
                citation="Rule 9(1)(b)",
                severity="major",
                field_name="mrp",
                observed_value="Missing",
                expected_value="Inclusive of all taxes",
                overridden=False,
            )
            session.add(v)
            await session.commit()

        # Override the single violation
        headers = {"Authorization": f"Bearer {token}"}
        resp = await async_client.post(
            f"/api/v1/scans/{scan_id}/violations/{viol_id}/override",
            headers=headers,
            json={"reason": "Government regulatory exemption granted"},
        )
        assert resp.status_code == 200
        assert resp.json()["overridden"] is True

        # Verify scan status is synced to 'completed'
        scan_resp = await async_client.get(f"/api/v1/scans/{scan_id}", headers=headers)
        assert scan_resp.status_code == 200
        scan_data = scan_resp.json()
        assert scan_data["verdict"] == "compliant"
        assert scan_data["status"] == "completed"


class TestFontRuleIsolationAndMRP:
    def test_font_relative_mode_skips_surface_area_rule(self):
        blocks = [
            TextBlock(
                text="MRP 100",
                estimated_char_height_px=20.0,
                estimated_font_height_mm=0.5,
                bbox=[0, 0, 5, 5],
            )
        ]
        fields = ExtractionFields(mrp=MRPField(value=100.0, raw="MRP 100", present=True))

        violations, _ = evaluate_rules(
            fields=fields,
            surface_area_cm2=600.0,
            font_check_mode="relative",
            detected_text_blocks=blocks,
        )
        # Surface area rule (LMPC-R9-5) must not fire when mode is relative
        assert not any(v.rule_code == "LMPC-R9-5" for v in violations)

    def test_font_surface_area_mode_skips_relative_rule(self):
        blocks = [
            TextBlock(
                text="MRP 100",
                estimated_char_height_px=5.0,
                estimated_font_height_mm=5.0,
                bbox=[0, 0, 5, 5],
            )
        ]
        fields = ExtractionFields(mrp=MRPField(value=100.0, raw="MRP 100", present=True))

        violations, _ = evaluate_rules(
            fields=fields,
            surface_area_cm2=40.0,
            font_check_mode="surface_area",
            detected_text_blocks=blocks,
        )
        # Relative rule (LMPC-R9-5-rel) must not fire when mode is surface_area
        assert not any(v.rule_code == "LMPC-R9-5-rel" for v in violations)

    def test_font_ignores_ingredient_text(self):
        # Ingredient text with small px should NOT trigger font_size violation
        blocks = [
            TextBlock(
                text="Ingredients: Sugar, Cocoa Solids, Milk Powder, Emulsifier (E322)",
                estimated_char_height_px=4.0,
                bbox=[0, 0, 5, 5],
            )
        ]
        fields = ExtractionFields(
            net_quantity=NetQuantityField(value=500.0, raw="500 g", unit="g", present=True),
            mrp=MRPField(value=100.0, raw="₹100", present=True),
        )
        violations, _ = evaluate_rules(
            fields=fields,
            font_check_mode="relative",
            detected_text_blocks=blocks,
        )
        assert not any(v.rule_code == "LMPC-R9-5-rel" for v in violations)

    def test_foreign_currency_flags_violation(self):
        fields = ExtractionFields(
            mrp=MRPField(value=50.0, raw="$50.00", currency="USD", present=True)
        )
        violations, _ = evaluate_rules(fields=fields)
        r9_1a = next((v for v in violations if v.rule_code == "LMPC-R9-1a"), None)
        assert r9_1a is not None

    def test_taxes_inclusive_fallback_raw_text(self):
        fields = ExtractionFields(
            mrp=MRPField(value=100.0, raw="MRP 100", taxes_inclusive_text=None, present=True)
        )
        violations, _ = evaluate_rules(
            fields=fields,
            raw_text="Batch 101 Mfg 2026 MRP 100 inclusive of all taxes Acme Ltd",
        )
        assert not any(v.rule_code == "LMPC-R9-1b" for v in violations)


class TestAdminRuleThresholdsAndRFC7807:
    @pytest.mark.asyncio
    async def test_admin_rule_thresholds_update_and_fetch(self, async_client: AsyncClient):
        admin, token = await create_user_with_role("admin")
        headers = {"Authorization": f"Bearer {token}"}

        # Update threshold for LMPC-R9-5
        resp = await async_client.put(
            "/api/v1/admin/rules/LMPC-R9-5",
            headers=headers,
            json={
                "thresholds": {"custom_bracket": 150, "min_mm": 2.0},
                "is_enabled": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["thresholds"] == {"custom_bracket": 150, "min_mm": 2.0}

        # Fetch via GET
        get_resp = await async_client.get("/api/v1/rules/LMPC-R9-5", headers=headers)
        assert get_resp.status_code == 200
        assert get_resp.json()["thresholds"] == {"custom_bracket": 150, "min_mm": 2.0}

    @pytest.mark.asyncio
    async def test_rfc7807_problem_detail_format(self, async_client: AsyncClient):
        viewer, token = await create_user_with_role("viewer")
        headers = {"Authorization": f"Bearer {token}"}
        random_id = uuid.uuid4()

        resp = await async_client.get(f"/api/v1/scans/{random_id}", headers=headers)
        assert resp.status_code == 404
        assert resp.headers.get("content-type") == "application/problem+json"
        body = resp.json()
        assert body["type"] == "https://errors.legalmetro.gov.in/scan-not-found"
        assert body["title"] == "Scan Not Found"
        assert body["status"] == 404
        assert "not found" in body["detail"]
        assert body["instance"] == f"/api/v1/scans/{random_id}"
