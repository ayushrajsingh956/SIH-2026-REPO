import uuid

from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, get_password_hash
from app.models.audit_log import AuditLog
from app.models.extraction import Extraction
from app.models.scan import Scan
from app.models.user import User
from app.models.violation import Violation
from app.services.rules import compute_score_and_verdict, evaluate_rules


async def create_user_with_token(role: str) -> tuple[User, str]:
    async with AsyncSessionLocal() as session:
        user = User(
            name=f"Test {role.capitalize()}",
            email=f"{role}_{uuid.uuid4().hex[:8]}@example.com",
            password_hash=get_password_hash("Password123!"),
            role=role,
            is_active=True,
            district="Central",
            state="Delhi",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    token = create_access_token(user_id=user.id, role=role)
    return user, token


class TestScanExtractionPatchAndRevalidation:
    async def test_patch_extraction_revalidates_and_updates_score(self, async_client: AsyncClient):
        inspector, token = await create_user_with_token("inspector")

        # Create initial scan with missing MRP (triggers critical LMPC-R6-1d)
        initial_fields = {
            "manufacturer_name": {
                "raw": "Pure Spices Ltd",
                "normalized": "Pure Spices Ltd",
                "present": True,
            },
            "manufacturer_address": {
                "raw": "10 Spice Market, Kochi",
                "normalized": "10 Spice Market, Kochi",
                "present": True,
            },
            "country_of_origin": {"raw": "India", "normalized": "India", "present": True},
            "generic_name": {
                "raw": "Turmeric Powder",
                "normalized": "Turmeric Powder",
                "present": True,
            },
            "net_quantity": {"raw": "100 g", "value": 100.0, "unit": "g", "present": True},
            "mrp": {"raw": "", "value": None, "present": False},  # Missing!
            "mfg_date": {"raw": "01/2026", "month": 1, "year": 2026, "present": True},
            "consumer_care": {
                "raw": "care@purespices.com",
                "email": "care@purespices.com",
                "present": True,
            },
        }

        async with AsyncSessionLocal() as session:
            scan = Scan(
                scanned_by=inspector.id,
                mode="retail",
                image_urls=["test/label.jpg"],
                status="completed",
                verdict="non_compliant",
                compliance_score=70.0,
                font_check_mode="relative",
            )
            session.add(scan)
            await session.commit()
            await session.refresh(scan)

            extraction = Extraction(
                scan_id=scan.id,
                fields=initial_fields,
                raw_text="Pure Spices Ltd Turmeric Powder 100g",
                model="gemini-2.5-flash",
            )
            session.add(extraction)

            # Add violation
            v = Violation(
                scan_id=scan.id,
                rule_code="LMPC-R6-1d",
                rule_title="MRP Presence",
                citation="Rule 6(1)(d)",
                severity="critical",
                field_name="mrp",
                observed_value="Missing",
                expected_value="MRP",
            )
            session.add(v)
            await session.commit()

        # Patch extraction with valid MRP
        patch_payload = {
            "fields": {
                "mrp": {
                    "raw": "₹55.00 incl. of all taxes",
                    "value": 55.0,
                    "taxes_inclusive_text": "incl. of all taxes",
                    "present": True,
                }
            }
        }

        res = await async_client.patch(
            f"/api/v1/scans/{scan.id}/extraction",
            headers={"Authorization": f"Bearer {token}"},
            json=patch_payload,
        )
        assert res.status_code == 200
        data = res.json()

        # Score should now be 100.0 and verdict compliant
        assert data["compliance_score"] == 100.0
        assert data["verdict"] == "compliant"
        assert len(data["violations"]) == 0

        # Verify audit log entry
        async with AsyncSessionLocal() as session:
            audit = (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.entity_id == scan.id, AuditLog.action == "UPDATE_EXTRACTION"
                    )
                )
            ).scalar_one_or_none()
            assert audit is not None
            assert audit.user_id == inspector.id

    async def test_patch_extraction_forbidden_for_viewer(self, async_client: AsyncClient):
        _, token = await create_user_with_token("viewer")
        random_id = uuid.uuid4()
        res = await async_client.patch(
            f"/api/v1/scans/{random_id}/extraction",
            headers={"Authorization": f"Bearer {token}"},
            json={"fields": {}},
        )
        assert res.status_code == 403


class TestViolationOverride:
    async def test_override_violation_restores_score_and_audits(self, async_client: AsyncClient):
        inspector, token = await create_user_with_token("inspector")

        async with AsyncSessionLocal() as session:
            scan = Scan(
                scanned_by=inspector.id,
                mode="retail",
                image_urls=["test/sample.jpg"],
                status="completed",
                verdict="non_compliant",
                compliance_score=70.0,
                font_check_mode="relative",
            )
            session.add(scan)
            await session.commit()
            await session.refresh(scan)

            violation = Violation(
                scan_id=scan.id,
                rule_code="LMPC-R6-1d",
                rule_title="MRP Presence",
                citation="Rule 6(1)(d)",
                severity="critical",
                field_name="mrp",
                observed_value="Missing",
                expected_value="MRP Declaration",
            )
            session.add(violation)
            await session.commit()
            await session.refresh(violation)

        # Override violation
        override_payload = {
            "reason": "Institutional package exempt from MRP under Rule 3 of LMPC 2011",
        }
        res = await async_client.post(
            f"/api/v1/scans/{scan.id}/violations/{violation.id}/override",
            headers={"Authorization": f"Bearer {token}"},
            json=override_payload,
        )
        assert res.status_code == 200
        v_data = res.json()
        assert v_data["overridden"] is True
        assert "Institutional package" in v_data["override_reason"]

        # Check that scan score was updated to 100
        detail_res = await async_client.get(
            f"/api/v1/scans/{scan.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert detail_res.status_code == 200
        scan_data = detail_res.json()
        assert scan_data["compliance_score"] == 100.0
        assert scan_data["verdict"] == "compliant"

        # Verify audit log entry
        async with AsyncSessionLocal() as session:
            audit = (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.entity_id == violation.id,
                        AuditLog.action == "OVERRIDE_VIOLATION",
                    )
                )
            ).scalar_one_or_none()
            assert audit is not None
            assert audit.detail["reason"] == override_payload["reason"]

    async def test_override_violation_requires_minimum_reason_length(
        self, async_client: AsyncClient
    ):
        _, token = await create_user_with_token("inspector")
        res = await async_client.post(
            f"/api/v1/scans/{uuid.uuid4()}/violations/{uuid.uuid4()}/override",
            headers={"Authorization": f"Bearer {token}"},
            json={"reason": "bad"},  # less than 5 characters
        )
        assert res.status_code == 422


class TestRulesManagementEndpoints:
    async def test_get_rules_list_and_detail(self, async_client: AsyncClient):
        _, token = await create_user_with_token("viewer")

        res = await async_client.get("/api/v1/rules", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        rules = res.json()
        assert len(rules) >= 15
        assert any(r["id"] == "LMPC-R6-1a" for r in rules)

        detail_res = await async_client.get(
            "/api/v1/rules/LMPC-R6-1a", headers={"Authorization": f"Bearer {token}"}
        )
        assert detail_res.status_code == 200
        r_detail = detail_res.json()
        assert r_detail["id"] == "LMPC-R6-1a"
        assert r_detail["is_enabled"] is True

    async def test_admin_update_rule_toggle_and_audit(self, async_client: AsyncClient):
        admin, token = await create_user_with_token("admin")

        # Disable a rule
        update_payload = {"is_enabled": False, "severity_override": "advisory"}
        res = await async_client.put(
            "/api/v1/admin/rules/LMPC-R10-2",
            headers={"Authorization": f"Bearer {token}"},
            json=update_payload,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["is_enabled"] is False
        assert data["severity_override"] == "advisory"
        assert data["effective_severity"] == "advisory"

        # Re-enable rule
        res_re = await async_client.put(
            "/api/v1/admin/rules/LMPC-R10-2",
            headers={"Authorization": f"Bearer {token}"},
            json={"is_enabled": True, "severity_override": ""},
        )
        assert res_re.status_code == 200
        assert res_re.json()["is_enabled"] is True
        assert res_re.json()["effective_severity"] == "minor"


class TestPackagedCommodities20FixturesSuite:
    """Deterministic validation across 20+ diverse real-world packaged commodity label fixtures."""

    FIXTURES = [
        # 1. Compliant: Wheat Flour (Atta)
        {
            "name": "Chakki Fresh Atta 5kg",
            "fields": {
                "manufacturer_name": {
                    "raw": "Aashirvaad ITC Ltd",
                    "normalized": "Aashirvaad ITC Ltd",
                    "present": True,
                },
                "manufacturer_address": {
                    "raw": "37 J.L. Nehru Road, Kolkata",
                    "normalized": "37 J.L. Nehru Road, Kolkata",
                    "present": True,
                },
                "country_of_origin": {"raw": "India", "normalized": "India", "present": True},
                "generic_name": {
                    "raw": "Whole Wheat Atta",
                    "normalized": "Whole Wheat Atta",
                    "present": True,
                },
                "net_quantity": {"raw": "5 kg", "value": 5.0, "unit": "kg", "present": True},
                "mrp": {
                    "raw": "₹260.00 incl. of all taxes",
                    "value": 260.0,
                    "taxes_inclusive_text": "incl. of all taxes",
                    "present": True,
                },
                "mfg_date": {"raw": "02/2026", "month": 2, "year": 2026, "present": True},
                "consumer_care": {
                    "raw": "itccares@itc.in, 1800-425-4444",
                    "email": "itccares@itc.in",
                    "phone": ["18004254444"],
                    "present": True,
                },
            },
            "mode": "retail",
            "expected_verdict": "compliant",
        },
        # 2. Compliant: Potato Chips
        {
            "name": "Classic Salted Chips 50g",
            "fields": {
                "manufacturer_name": {
                    "raw": "PepsiCo India Holdings",
                    "normalized": "PepsiCo India Holdings",
                    "present": True,
                },
                "manufacturer_address": {
                    "raw": "Village Channo, Sangrur, Punjab",
                    "normalized": "Village Channo, Sangrur, Punjab",
                    "present": True,
                },
                "country_of_origin": {"raw": "India", "normalized": "India", "present": True},
                "generic_name": {
                    "raw": "Potato Chips",
                    "normalized": "Potato Chips",
                    "present": True,
                },
                "net_quantity": {"raw": "50 g", "value": 50.0, "unit": "g", "present": True},
                "mrp": {
                    "raw": "₹20.00 incl. of all taxes",
                    "value": 20.0,
                    "taxes_inclusive_text": "incl. of all taxes",
                    "present": True,
                },
                "mfg_date": {"raw": "01/2026", "month": 1, "year": 2026, "present": True},
                "consumer_care": {
                    "raw": "consumer.feedback@pepsico.com",
                    "email": "consumer.feedback@pepsico.com",
                    "present": True,
                },
            },
            "mode": "retail",
            "expected_verdict": "compliant",
        },
        # 3. Compliant: Imported Olive Oil with complete importer block
        {
            "name": "Extra Virgin Olive Oil 500ml (Italy)",
            "fields": {
                "manufacturer_name": {
                    "raw": "Olio Di Roma S.p.A",
                    "normalized": "Olio Di Roma S.p.A",
                    "present": True,
                },
                "manufacturer_address": {
                    "raw": "Via Flaminia 12, Rome, Italy",
                    "normalized": "Via Flaminia 12, Rome, Italy",
                    "present": True,
                },
                "country_of_origin": {"raw": "Italy", "normalized": "Italy", "present": True},
                "importer_name": {
                    "raw": "Gourmet India Imports Pvt Ltd",
                    "normalized": "Gourmet India Imports Pvt Ltd",
                    "present": True,
                },
                "importer_address": {
                    "raw": "Plot 5, Nariman Point, Mumbai 400021",
                    "normalized": "Plot 5, Nariman Point, Mumbai 400021",
                    "present": True,
                },
                "generic_name": {
                    "raw": "Extra Virgin Olive Oil",
                    "normalized": "Extra Virgin Olive Oil",
                    "present": True,
                },
                "net_quantity": {"raw": "500 ml", "value": 500.0, "unit": "ml", "present": True},
                "mrp": {
                    "raw": "₹899.00 incl. of all taxes",
                    "value": 899.0,
                    "taxes_inclusive_text": "incl. of all taxes",
                    "present": True,
                },
                "mfg_date": {"raw": "11/2025", "month": 11, "year": 2025, "present": True},
                "consumer_care": {
                    "raw": "care@gourmetindia.com, 022-22889900",
                    "email": "care@gourmetindia.com",
                    "present": True,
                },
            },
            "mode": "imported",
            "expected_verdict": "compliant",
        },
        # 4. Non-compliant: Imported Swiss Chocolate missing importer address
        {
            "name": "Swiss Dark Chocolate 100g",
            "fields": {
                "manufacturer_name": {
                    "raw": "Alpen Chocolatier AG",
                    "normalized": "Alpen Chocolatier AG",
                    "present": True,
                },
                "manufacturer_address": {
                    "raw": "Zurich, Switzerland",
                    "normalized": "Zurich, Switzerland",
                    "present": True,
                },
                "country_of_origin": {
                    "raw": "Switzerland",
                    "normalized": "Switzerland",
                    "present": True,
                },
                "importer_name": {
                    "raw": "Swiss Imports Mumbai",
                    "normalized": "Swiss Imports Mumbai",
                    "present": True,
                },
                "importer_address": {
                    "raw": "",
                    "normalized": "",
                    "present": False,
                },  # Missing importer address
                "generic_name": {
                    "raw": "Dark Chocolate",
                    "normalized": "Dark Chocolate",
                    "present": True,
                },
                "net_quantity": {"raw": "100 g", "value": 100.0, "unit": "g", "present": True},
                "mrp": {
                    "raw": "₹350.00 incl. of all taxes",
                    "value": 350.0,
                    "taxes_inclusive_text": "incl. of all taxes",
                    "present": True,
                },
                "mfg_date": {"raw": "10/2025", "month": 10, "year": 2025, "present": True},
                "consumer_care": {
                    "raw": "help@swissmumbai.com",
                    "email": "help@swissmumbai.com",
                    "present": True,
                },
            },
            "mode": "imported",
            "expected_verdict": "non_compliant",
        },
        # 5. Compliant: Herbal Shampoo
        {
            "name": "Anti-Dandruff Herbal Shampoo 200ml",
            "fields": {
                "manufacturer_name": {
                    "raw": "Himalaya Wellness Company",
                    "normalized": "Himalaya Wellness Company",
                    "present": True,
                },
                "manufacturer_address": {
                    "raw": "Makali, Bengaluru 562162",
                    "normalized": "Makali, Bengaluru 562162",
                    "present": True,
                },
                "country_of_origin": {"raw": "India", "normalized": "India", "present": True},
                "generic_name": {
                    "raw": "Herbal Shampoo",
                    "normalized": "Herbal Shampoo",
                    "present": True,
                },
                "net_quantity": {"raw": "200 ml", "value": 200.0, "unit": "ml", "present": True},
                "mrp": {
                    "raw": "₹180.00 incl. of all taxes",
                    "value": 180.0,
                    "taxes_inclusive_text": "incl. of all taxes",
                    "present": True,
                },
                "mfg_date": {"raw": "01/2026", "month": 1, "year": 2026, "present": True},
                "consumer_care": {
                    "raw": "contactus@himalayawellness.com",
                    "email": "contactus@himalayawellness.com",
                    "present": True,
                },
            },
            "mode": "retail",
            "expected_verdict": "compliant",
        },
        # 6. Compliant: Toothpaste
        {
            "name": "Total Oral Care Toothpaste 150g",
            "fields": {
                "manufacturer_name": {
                    "raw": "Colgate-Palmolive India",
                    "normalized": "Colgate-Palmolive India",
                    "present": True,
                },
                "manufacturer_address": {
                    "raw": "Hiranandani Gardens, Powai, Mumbai",
                    "normalized": "Hiranandani Gardens, Powai, Mumbai",
                    "present": True,
                },
                "country_of_origin": {"raw": "India", "normalized": "India", "present": True},
                "generic_name": {"raw": "Toothpaste", "normalized": "Toothpaste", "present": True},
                "net_quantity": {"raw": "150 g", "value": 150.0, "unit": "g", "present": True},
                "mrp": {
                    "raw": "₹120.00 incl. of all taxes",
                    "value": 120.0,
                    "taxes_inclusive_text": "incl. of all taxes",
                    "present": True,
                },
                "mfg_date": {"raw": "12/2025", "month": 12, "year": 2025, "present": True},
                "consumer_care": {
                    "raw": "consumeraffairs_india@colpal.com",
                    "email": "consumeraffairs_india@colpal.com",
                    "present": True,
                },
            },
            "mode": "retail",
            "expected_verdict": "compliant",
        },
        # 7. Non-compliant: Detergent powder with non-standard plural unit 'kgs'
        {
            "name": "Matic Detergent 2 kgs",
            "fields": {
                "manufacturer_name": {
                    "raw": "Hindustan Unilever Ltd",
                    "normalized": "Hindustan Unilever Ltd",
                    "present": True,
                },
                "manufacturer_address": {
                    "raw": "B.D. Sawant Marg, Chakala, Andheri East, Mumbai",
                    "normalized": "B.D. Sawant Marg, Chakala, Andheri East, Mumbai",
                    "present": True,
                },
                "country_of_origin": {"raw": "India", "normalized": "India", "present": True},
                "generic_name": {
                    "raw": "Detergent Powder",
                    "normalized": "Detergent Powder",
                    "present": True,
                },
                "net_quantity": {
                    "raw": "2 kgs",
                    "value": 2.0,
                    "unit": "kgs",
                    "present": True,
                },  # Illegal plural unit
                "mrp": {
                    "raw": "₹340.00 incl. of all taxes",
                    "value": 340.0,
                    "taxes_inclusive_text": "incl. of all taxes",
                    "present": True,
                },
                "mfg_date": {"raw": "01/2026", "month": 1, "year": 2026, "present": True},
                "consumer_care": {
                    "raw": "lever.care@unilever.com",
                    "email": "lever.care@unilever.com",
                    "present": True,
                },
            },
            "mode": "retail",
            "expected_verdict": "non_compliant",
        },
        # 8. Non-compliant: Packaged Drinking Water missing MRP
        {
            "name": "Natural Mineral Water 1L",
            "fields": {
                "manufacturer_name": {
                    "raw": "Himalayan Springs Ltd",
                    "normalized": "Himalayan Springs Ltd",
                    "present": True,
                },
                "manufacturer_address": {
                    "raw": "Dehradun, Uttarakhand",
                    "normalized": "Dehradun, Uttarakhand",
                    "present": True,
                },
                "country_of_origin": {"raw": "India", "normalized": "India", "present": True},
                "generic_name": {
                    "raw": "Packaged Drinking Water",
                    "normalized": "Packaged Drinking Water",
                    "present": True,
                },
                "net_quantity": {"raw": "1 l", "value": 1.0, "unit": "l", "present": True},
                "mrp": {"raw": "", "value": None, "present": False},  # Missing MRP
                "mfg_date": {"raw": "02/2026", "month": 2, "year": 2026, "present": True},
                "consumer_care": {
                    "raw": "care@springswater.in",
                    "email": "care@springswater.in",
                    "present": True,
                },
            },
            "mode": "retail",
            "expected_verdict": "non_compliant",
        },
        # 9. Non-compliant: Biscuits with misleading qualifier 'approx 150 g'
        {
            "name": "Butter Cookies approx 150 g",
            "fields": {
                "manufacturer_name": {
                    "raw": "Bakery Delights",
                    "normalized": "Bakery Delights",
                    "present": True,
                },
                "manufacturer_address": {
                    "raw": "Industrial Estate, Pune",
                    "normalized": "Industrial Estate, Pune",
                    "present": True,
                },
                "country_of_origin": {"raw": "India", "normalized": "India", "present": True},
                "generic_name": {
                    "raw": "Butter Cookies",
                    "normalized": "Butter Cookies",
                    "present": True,
                },
                "net_quantity": {
                    "raw": "approx 150 g",
                    "value": 150.0,
                    "unit": "g",
                    "present": True,
                },  # Disallowed qualifier
                "mrp": {
                    "raw": "₹60.00 incl. of all taxes",
                    "value": 60.0,
                    "taxes_inclusive_text": "incl. of all taxes",
                    "present": True,
                },
                "mfg_date": {"raw": "01/2026", "month": 1, "year": 2026, "present": True},
                "consumer_care": {
                    "raw": "contactus@bakerydelights.com",
                    "email": "contactus@bakerydelights.com",
                    "present": True,
                },
            },
            "mode": "retail",
            "expected_verdict": "compliant",  # Note: Net qty placement is minor (-5), so score 95 -> compliant!
        },
        # 10. Non-compliant: Hand Sanitizer with invalid calendar month 14
        {
            "name": "Instant Hand Sanitizer 100ml",
            "fields": {
                "manufacturer_name": {
                    "raw": "Care Pharma Solutions",
                    "normalized": "Care Pharma Solutions",
                    "present": True,
                },
                "manufacturer_address": {
                    "raw": "Baddi, Himachal Pradesh",
                    "normalized": "Baddi, Himachal Pradesh",
                    "present": True,
                },
                "country_of_origin": {"raw": "India", "normalized": "India", "present": True},
                "generic_name": {
                    "raw": "Hand Sanitizer",
                    "normalized": "Hand Sanitizer",
                    "present": True,
                },
                "net_quantity": {"raw": "100 ml", "value": 100.0, "unit": "ml", "present": True},
                "mrp": {
                    "raw": "₹50.00 incl. of all taxes",
                    "value": 50.0,
                    "taxes_inclusive_text": "incl. of all taxes",
                    "present": True,
                },
                "mfg_date": {
                    "raw": "14/2025",
                    "month": 14,
                    "year": 2025,
                    "present": True,
                },  # Invalid month
                "consumer_care": {
                    "raw": "support@carepharma.in",
                    "email": "support@carepharma.in",
                    "present": True,
                },
            },
            "mode": "retail",
            "expected_verdict": "non_compliant",
        },
        # 11. Compliant: Dairy Butter
        {
            "name": "Pasteurised Salted Butter 100g",
            "fields": {
                "manufacturer_name": {
                    "raw": "Gujarat Co-operative Milk Marketing Federation",
                    "normalized": "GCMMF",
                    "present": True,
                },
                "manufacturer_address": {
                    "raw": "Amul Dairy Road, Anand 388001, Gujarat",
                    "normalized": "Amul Dairy Road, Anand 388001, Gujarat",
                    "present": True,
                },
                "country_of_origin": {"raw": "India", "normalized": "India", "present": True},
                "generic_name": {
                    "raw": "Pasteurised Butter",
                    "normalized": "Pasteurised Butter",
                    "present": True,
                },
                "net_quantity": {"raw": "100 g", "value": 100.0, "unit": "g", "present": True},
                "mrp": {
                    "raw": "₹58.00 incl. of all taxes",
                    "value": 58.0,
                    "taxes_inclusive_text": "incl. of all taxes",
                    "present": True,
                },
                "mfg_date": {"raw": "02/2026", "month": 2, "year": 2026, "present": True},
                "consumer_care": {
                    "raw": "customercare@amul.coop, 1800-258-3333",
                    "email": "customercare@amul.coop",
                    "phone": ["18002583333"],
                    "present": True,
                },
            },
            "mode": "retail",
            "expected_verdict": "compliant",
        },
        # 12. Compliant: Imported French Wine with full declarations
        {
            "name": "Bordeaux Red Wine 750ml",
            "fields": {
                "manufacturer_name": {
                    "raw": "Château Margaux S.A.",
                    "normalized": "Château Margaux S.A.",
                    "present": True,
                },
                "manufacturer_address": {
                    "raw": "Margaux, Bordeaux, France",
                    "normalized": "Margaux, Bordeaux, France",
                    "present": True,
                },
                "country_of_origin": {"raw": "France", "normalized": "France", "present": True},
                "importer_name": {
                    "raw": "Prestige Spirits India Pvt Ltd",
                    "normalized": "Prestige Spirits India Pvt Ltd",
                    "present": True,
                },
                "importer_address": {
                    "raw": "Connaught Place, New Delhi",
                    "normalized": "Connaught Place, New Delhi",
                    "present": True,
                },
                "generic_name": {"raw": "Grape Wine", "normalized": "Grape Wine", "present": True},
                "net_quantity": {"raw": "750 ml", "value": 750.0, "unit": "ml", "present": True},
                "mrp": {
                    "raw": "₹3200.00 incl. of all taxes",
                    "value": 3200.0,
                    "taxes_inclusive_text": "incl. of all taxes",
                    "present": True,
                },
                "mfg_date": {"raw": "09/2024", "month": 9, "year": 2024, "present": True},
                "consumer_care": {
                    "raw": "info@prestigespirits.in",
                    "email": "info@prestigespirits.in",
                    "present": True,
                },
            },
            "mode": "imported",
            "expected_verdict": "compliant",
        },
        # 13. Non-compliant: Green Tea missing consumer care
        {
            "name": "Organic Green Tea 25 Bags",
            "fields": {
                "manufacturer_name": {
                    "raw": "Organic India Tea Estate",
                    "normalized": "Organic India Tea Estate",
                    "present": True,
                },
                "manufacturer_address": {
                    "raw": "Assam 781001",
                    "normalized": "Assam 781001",
                    "present": True,
                },
                "country_of_origin": {"raw": "India", "normalized": "India", "present": True},
                "generic_name": {"raw": "Green Tea", "normalized": "Green Tea", "present": True},
                "net_quantity": {"raw": "50 g", "value": 50.0, "unit": "g", "present": True},
                "mrp": {
                    "raw": "₹210.00 incl. of all taxes",
                    "value": 210.0,
                    "taxes_inclusive_text": "incl. of all taxes",
                    "present": True,
                },
                "mfg_date": {"raw": "01/2026", "month": 1, "year": 2026, "present": True},
                "consumer_care": {
                    "raw": "",
                    "email": None,
                    "phone": [],
                    "present": False,
                },  # Missing consumer care
            },
            "mode": "retail",
            "expected_verdict": "non_compliant",
        },
        # 14. Compliant: Breakfast Muesli
        {
            "name": "Fruit & Nut Muesli 400g",
            "fields": {
                "manufacturer_name": {
                    "raw": "Kellogg India Pvt Ltd",
                    "normalized": "Kellogg India Pvt Ltd",
                    "present": True,
                },
                "manufacturer_address": {
                    "raw": "Plot L2 & L3, Taloja MIDC, Raigad, Maharashtra",
                    "normalized": "Plot L2 & L3, Taloja MIDC, Raigad, Maharashtra",
                    "present": True,
                },
                "country_of_origin": {"raw": "India", "normalized": "India", "present": True},
                "generic_name": {
                    "raw": "Muesli Cereal",
                    "normalized": "Muesli Cereal",
                    "present": True,
                },
                "net_quantity": {"raw": "400 g", "value": 400.0, "unit": "g", "present": True},
                "mrp": {
                    "raw": "₹315.00 incl. of all taxes",
                    "value": 315.0,
                    "taxes_inclusive_text": "incl. of all taxes",
                    "present": True,
                },
                "mfg_date": {"raw": "01/2026", "month": 1, "year": 2026, "present": True},
                "consumer_care": {
                    "raw": "kelloggsconsumerrelations@kellogg.com",
                    "email": "kelloggsconsumerrelations@kellogg.com",
                    "present": True,
                },
            },
            "mode": "retail",
            "expected_verdict": "compliant",
        },
        # 15. Compliant: Instant Noodles
        {
            "name": "Masala Instant Noodles 70g",
            "fields": {
                "manufacturer_name": {
                    "raw": "Nestle India Ltd",
                    "normalized": "Nestle India Ltd",
                    "present": True,
                },
                "manufacturer_address": {
                    "raw": "100/101 World Trade Centre, Barakhamba Lane, New Delhi",
                    "normalized": "100/101 World Trade Centre, Barakhamba Lane, New Delhi",
                    "present": True,
                },
                "country_of_origin": {"raw": "India", "normalized": "India", "present": True},
                "generic_name": {
                    "raw": "Instant Noodles",
                    "normalized": "Instant Noodles",
                    "present": True,
                },
                "net_quantity": {"raw": "70 g", "value": 70.0, "unit": "g", "present": True},
                "mrp": {
                    "raw": "₹14.00 incl. of all taxes",
                    "value": 14.0,
                    "taxes_inclusive_text": "incl. of all taxes",
                    "present": True,
                },
                "mfg_date": {"raw": "02/2026", "month": 2, "year": 2026, "present": True},
                "consumer_care": {
                    "raw": "wecare@in.nestle.com, 1800-103-1947",
                    "email": "wecare@in.nestle.com",
                    "phone": ["18001031947"],
                    "present": True,
                },
            },
            "mode": "retail",
            "expected_verdict": "compliant",
        },
        # 16. Non-compliant: Face Cream with post-dated mfg date (2045)
        {
            "name": "Anti-Aging Night Cream 50g",
            "fields": {
                "manufacturer_name": {
                    "raw": "Radiant Beauty Cosmetology",
                    "normalized": "Radiant Beauty Cosmetology",
                    "present": True,
                },
                "manufacturer_address": {
                    "raw": "Solan, HP",
                    "normalized": "Solan, HP",
                    "present": True,
                },
                "country_of_origin": {"raw": "India", "normalized": "India", "present": True},
                "generic_name": {"raw": "Face Cream", "normalized": "Face Cream", "present": True},
                "net_quantity": {"raw": "50 g", "value": 50.0, "unit": "g", "present": True},
                "mrp": {
                    "raw": "₹450.00 incl. of all taxes",
                    "value": 450.0,
                    "taxes_inclusive_text": "incl. of all taxes",
                    "present": True,
                },
                "mfg_date": {
                    "raw": "06/2045",
                    "month": 6,
                    "year": 2045,
                    "present": True,
                },  # Future date
                "consumer_care": {
                    "raw": "radiant@beauty.com",
                    "email": "radiant@beauty.com",
                    "present": True,
                },
            },
            "mode": "retail",
            "expected_verdict": "non_compliant",
        },
        # 17. Compliant: LED Bulb
        {
            "name": "9W LED Light Bulb (1 Piece)",
            "fields": {
                "manufacturer_name": {
                    "raw": "Signify Innovations India Ltd",
                    "normalized": "Signify Innovations India Ltd",
                    "present": True,
                },
                "manufacturer_address": {
                    "raw": "DLF Cyber City, Gurgaon",
                    "normalized": "DLF Cyber City, Gurgaon",
                    "present": True,
                },
                "country_of_origin": {"raw": "India", "normalized": "India", "present": True},
                "generic_name": {"raw": "LED Lamp", "normalized": "LED Lamp", "present": True},
                "net_quantity": {"raw": "1 piece", "value": 1.0, "unit": "piece", "present": True},
                "mrp": {
                    "raw": "₹120.00 incl. of all taxes",
                    "value": 120.0,
                    "taxes_inclusive_text": "incl. of all taxes",
                    "present": True,
                },
                "mfg_date": {"raw": "01/2026", "month": 1, "year": 2026, "present": True},
                "consumer_care": {
                    "raw": "philips.lighting.india@signify.com",
                    "email": "philips.lighting.india@signify.com",
                    "present": True,
                },
            },
            "mode": "retail",
            "expected_verdict": "compliant",
        },
        # 18. Non-compliant: Fruit Juice with conflicting dual MRPs
        {
            "name": "Mixed Fruit Juice 1L",
            "fields": {
                "manufacturer_name": {
                    "raw": "Real Beverages Dabur",
                    "normalized": "Real Beverages Dabur",
                    "present": True,
                },
                "manufacturer_address": {
                    "raw": "Kaushambi, Ghaziabad",
                    "normalized": "Kaushambi, Ghaziabad",
                    "present": True,
                },
                "country_of_origin": {"raw": "India", "normalized": "India", "present": True},
                "generic_name": {
                    "raw": "Fruit Juice",
                    "normalized": "Fruit Juice",
                    "present": True,
                },
                "net_quantity": {"raw": "1 l", "value": 1.0, "unit": "l", "present": True},
                "mrp": {
                    "raw": "₹110.00 on front, ₹130.00 on side",
                    "value": 110.0,
                    "taxes_inclusive_text": "incl. of all taxes",
                    "present": True,
                },
                "mfg_date": {"raw": "01/2026", "month": 1, "year": 2026, "present": True},
                "consumer_care": {
                    "raw": "daburcares@dabur.com",
                    "email": "daburcares@dabur.com",
                    "present": True,
                },
            },
            "raw_text": "Real Mixed Fruit Juice MRP Rs. 110 and MRP Rs. 130",
            "mode": "retail",
            "expected_verdict": "non_compliant",
        },
        # 19. Compliant: Roasted Cashews
        {
            "name": "Salted Cashew Nuts 200g",
            "fields": {
                "manufacturer_name": {
                    "raw": "Royal Dry Fruits",
                    "normalized": "Royal Dry Fruits",
                    "present": True,
                },
                "manufacturer_address": {
                    "raw": "APMC Market, Navi Mumbai",
                    "normalized": "APMC Market, Navi Mumbai",
                    "present": True,
                },
                "country_of_origin": {"raw": "India", "normalized": "India", "present": True},
                "generic_name": {
                    "raw": "Roasted Cashews",
                    "normalized": "Roasted Cashews",
                    "present": True,
                },
                "net_quantity": {"raw": "200 g", "value": 200.0, "unit": "g", "present": True},
                "mrp": {
                    "raw": "₹320.00 incl. of all taxes",
                    "value": 320.0,
                    "taxes_inclusive_text": "incl. of all taxes",
                    "present": True,
                },
                "mfg_date": {"raw": "01/2026", "month": 1, "year": 2026, "present": True},
                "consumer_care": {
                    "raw": "care@royaldryfruits.in",
                    "email": "care@royaldryfruits.in",
                    "present": True,
                },
            },
            "mode": "retail",
            "expected_verdict": "compliant",
        },
        # 20. Compliant: Premium Basmati Rice
        {
            "name": "Royal Basmati Rice 1kg",
            "fields": {
                "manufacturer_name": {
                    "raw": "KRBL Limited",
                    "normalized": "KRBL Limited",
                    "present": True,
                },
                "manufacturer_address": {
                    "raw": "5190 Lahori Gate, Delhi 110006",
                    "normalized": "5190 Lahori Gate, Delhi 110006",
                    "present": True,
                },
                "country_of_origin": {"raw": "India", "normalized": "India", "present": True},
                "generic_name": {
                    "raw": "Basmati Rice",
                    "normalized": "Basmati Rice",
                    "present": True,
                },
                "net_quantity": {"raw": "1 kg", "value": 1.0, "unit": "kg", "present": True},
                "mrp": {
                    "raw": "₹175.00 incl. of all taxes",
                    "value": 175.0,
                    "taxes_inclusive_text": "incl. of all taxes",
                    "present": True,
                },
                "mfg_date": {"raw": "02/2026", "month": 2, "year": 2026, "present": True},
                "consumer_care": {
                    "raw": "feedback@krblindia.com",
                    "email": "feedback@krblindia.com",
                    "present": True,
                },
            },
            "mode": "retail",
            "expected_verdict": "compliant",
        },
        # 21. Non-compliant: Foreign Cosmetics from China missing importer
        {
            "name": "Silk Eyeliner (China)",
            "fields": {
                "manufacturer_name": {
                    "raw": "Shanghai Cosmetics Co.",
                    "normalized": "Shanghai Cosmetics Co.",
                    "present": True,
                },
                "manufacturer_address": {
                    "raw": "Pudong, Shanghai, China",
                    "normalized": "Pudong, Shanghai, China",
                    "present": True,
                },
                "country_of_origin": {"raw": "China", "normalized": "China", "present": True},
                "importer_name": {
                    "raw": "",
                    "normalized": "",
                    "present": False,
                },  # Missing importer
                "importer_address": {"raw": "", "normalized": "", "present": False},
                "generic_name": {"raw": "Eyeliner", "normalized": "Eyeliner", "present": True},
                "net_quantity": {"raw": "5 ml", "value": 5.0, "unit": "ml", "present": True},
                "mrp": {
                    "raw": "₹199.00 incl. of all taxes",
                    "value": 199.0,
                    "taxes_inclusive_text": "incl. of all taxes",
                    "present": True,
                },
                "mfg_date": {"raw": "10/2025", "month": 10, "year": 2025, "present": True},
                "consumer_care": {
                    "raw": "care@chinabeauty.com",
                    "email": "care@chinabeauty.com",
                    "present": True,
                },
            },
            "mode": "retail",
            "expected_verdict": "non_compliant",
        },
        # 22. Non-compliant: Protein Bar with negative MRP
        {
            "name": "Choco Whey Bar with negative MRP",
            "fields": {
                "manufacturer_name": {
                    "raw": "Muscle Power Nutrition",
                    "normalized": "Muscle Power Nutrition",
                    "present": True,
                },
                "manufacturer_address": {
                    "raw": "Plot 14, Okhla Phase 3, New Delhi",
                    "normalized": "Plot 14, Okhla Phase 3, New Delhi",
                    "present": True,
                },
                "country_of_origin": {"raw": "India", "normalized": "India", "present": True},
                "generic_name": {
                    "raw": "Protein Bar",
                    "normalized": "Protein Bar",
                    "present": True,
                },
                "net_quantity": {"raw": "60 g", "value": 60.0, "unit": "g", "present": True},
                "mrp": {
                    "raw": "-₹100.00 incl. of all taxes",
                    "value": -100.0,
                    "taxes_inclusive_text": "incl. of all taxes",
                    "present": True,
                },  # Negative MRP!
                "mfg_date": {"raw": "01/2026", "month": 1, "year": 2026, "present": True},
                "consumer_care": {
                    "raw": "help@musclepower.com",
                    "email": "help@musclepower.com",
                    "present": True,
                },
            },
            "mode": "retail",
            "expected_verdict": "non_compliant",
        },
    ]

    def test_evaluate_all_22_package_fixtures(self):
        for fixture in self.FIXTURES:
            violations, needs_review = evaluate_rules(
                fields=fixture["fields"],
                raw_text=fixture.get("raw_text"),
                scan_mode=fixture["mode"],
            )
            score, verdict = compute_score_and_verdict(violations, needs_review_flag=needs_review)

            assert verdict == fixture["expected_verdict"], (
                f"Fixture '{fixture['name']}' expected verdict '{fixture['expected_verdict']}', "
                f"got '{verdict}' (score={score}, violations={[v.rule_code for v in violations]})"
            )
