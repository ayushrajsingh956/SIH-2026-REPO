import uuid

import pytest
from httpx import AsyncClient

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, get_password_hash
from app.models.user import User


async def get_test_token(role: str = "inspector") -> tuple[User, str]:
    async with AsyncSessionLocal() as session:
        user = User(
            name=f"Analytics Test {role}",
            email=f"analytics_{role}_{uuid.uuid4().hex[:6]}@example.com",
            password_hash=get_password_hash("TestPass123!"),
            role=role,
            district="North Delhi",
            state="Delhi",
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    token = create_access_token(user_id=user.id, role=role)
    return user, token


@pytest.mark.anyio
class TestDashboardEndpoints:
    async def test_dashboard_summary_returns_valid_kpis(self, async_client: AsyncClient):
        _, token = await get_test_token("viewer")
        response = await async_client.get(
            "/api/v1/dashboard/summary?range=30d",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_scans" in data
        assert "compliance_rate" in data
        assert "avg_compliance_score" in data
        assert "pending_reviews" in data
        assert "critical_violations" in data
        assert isinstance(data["total_scans"], int)
        assert 0.0 <= data["compliance_rate"] <= 100.0

    async def test_dashboard_violations_by_rule(self, async_client: AsyncClient):
        _, token = await get_test_token("inspector")
        response = await async_client.get(
            "/api/v1/dashboard/violations/by-rule?range=90d&limit=5",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        items = response.json()
        assert isinstance(items, list)
        if items:
            first = items[0]
            assert "rule_code" in first
            assert "rule_title" in first
            assert "citation" in first
            assert "count" in first
            assert first["count"] >= 1

    async def test_dashboard_violations_by_severity(self, async_client: AsyncClient):
        _, token = await get_test_token("viewer")
        response = await async_client.get(
            "/api/v1/dashboard/violations/by-severity?range=90d",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        items = response.json()
        assert isinstance(items, list)
        severities = [item["severity"] for item in items]
        assert "critical" in severities
        assert "major" in severities

    async def test_dashboard_compliance_trend(self, async_client: AsyncClient):
        _, token = await get_test_token("viewer")
        response = await async_client.get(
            "/api/v1/dashboard/compliance/trend?range=30d&granularity=day",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        items = response.json()
        assert isinstance(items, list)
        if items:
            assert "date" in items[0]
            assert "total_scans" in items[0]
            assert "compliance_rate" in items[0]

    async def test_dashboard_districts_breakdown(self, async_client: AsyncClient):
        _, token = await get_test_token("viewer")
        response = await async_client.get(
            "/api/v1/dashboard/districts?range=90d",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        items = response.json()
        assert isinstance(items, list)
        if items:
            assert "district" in items[0]
            assert "state" in items[0]
            assert "compliance_rate" in items[0]


@pytest.mark.anyio
class TestProductsEndpoints:
    async def test_list_products_and_fts_search(self, async_client: AsyncClient):
        _, token = await get_test_token("inspector")
        # List all products
        response = await async_client.get(
            "/api/v1/products?limit=10",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] > 0
        assert len(data["items"]) > 0

        # FTS search for "Tea"
        search_res = await async_client.get(
            "/api/v1/products?q=Tea",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert search_res.status_code == 200
        s_data = search_res.json()
        assert any("Tea" in p["name"] for p in s_data["items"])

    async def test_product_detail_and_repeat_offender_recurrence(self, async_client: AsyncClient):
        _, token = await get_test_token("inspector")
        # Find Royal Herbal
        search_res = await async_client.get(
            "/api/v1/products?q=Royal+Herbal",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert search_res.status_code == 200
        items = search_res.json()["items"]
        assert len(items) > 0
        royal_prod = items[0]

        # Get scans timeline
        scans_res = await async_client.get(
            f"/api/v1/products/{royal_prod['id']}/scans",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert scans_res.status_code == 200
        scans_data = scans_res.json()
        assert scans_data["is_repeat_offender"] is True
        assert len(scans_data["recurrent_violations"]) >= 1
        assert len(scans_data["scans"]) >= 2


@pytest.mark.anyio
class TestViolationsEndpoints:
    async def test_list_violations_multi_filters(self, async_client: AsyncClient):
        _, token = await get_test_token("inspector")
        response = await async_client.get(
            "/api/v1/violations?severity=critical&limit=15",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "severity_summary" in data
        for v in data["items"]:
            assert v["severity"] == "critical"

    async def test_get_violation_by_id(self, async_client: AsyncClient):
        _, token = await get_test_token("inspector")
        list_res = await async_client.get(
            "/api/v1/violations?limit=1",
            headers={"Authorization": f"Bearer {token}"},
        )
        items = list_res.json()["items"]
        if items:
            v_id = items[0]["id"]
            single_res = await async_client.get(
                f"/api/v1/violations/{v_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert single_res.status_code == 200
            assert single_res.json()["id"] == v_id


@pytest.mark.anyio
class TestRulesAndReportsEndpoints:
    async def test_rule_recent_scans(self, async_client: AsyncClient):
        _, token = await get_test_token("viewer")
        response = await async_client.get(
            "/api/v1/rules/LMPC-R9-1/recent-scans?limit=5",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        items = response.json()
        assert isinstance(items, list)
        if items:
            assert "scan_id" in items[0]
            assert "violation_id" in items[0]

    async def test_reports_list_and_stub_create(self, async_client: AsyncClient):
        _, token = await get_test_token("inspector")
        # List reports
        list_res = await async_client.get(
            "/api/v1/reports?limit=10",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert list_res.status_code == 200
        assert "items" in list_res.json()

        # Create stub report for an existing scan
        scans_res = await async_client.get(
            "/api/v1/scans?limit=1",
            headers={"Authorization": f"Bearer {token}"},
        )
        scans = scans_res.json()["items"]
        if scans:
            scan_id = scans[0]["id"]
            create_res = await async_client.post(
                "/api/v1/reports",
                headers={"Authorization": f"Bearer {token}"},
                json={"scan_id": scan_id},
            )
            assert create_res.status_code == 201
            assert create_res.json()["scan_id"] == scan_id
