import uuid

import pytest
from httpx import AsyncClient

from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.user import User


async def create_user_helper(
    email: str,
    role: str = "viewer",
    is_active: bool = True,
    password: str = "SecurePass123!",
) -> User:
    async with AsyncSessionLocal() as session:
        user = User(
            name=f"User {role}",
            email=email,
            password_hash=get_password_hash(password),
            role=role,
            is_active=is_active,
            district="Test District",
            state="Test State",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


@pytest.mark.asyncio
async def test_public_self_registration_creates_pending_viewer(
    async_client: AsyncClient,
):
    unique_email = f"public_{uuid.uuid4().hex[:8]}@example.com"
    response = await async_client.post(
        "/api/v1/auth/register",
        json={
            "name": "Public Citizen",
            "email": unique_email,
            "password": "ValidPassword123!",
            "role": "admin",  # Attacker tries to register as admin
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == unique_email
    # Must be forced to viewer and inactive
    assert data["role"] == "viewer"
    assert data["is_active"] is False


@pytest.mark.asyncio
async def test_duplicate_registration_returns_409(
    async_client: AsyncClient,
):
    unique_email = f"dup_{uuid.uuid4().hex[:8]}@example.com"
    await create_user_helper(unique_email)

    response = await async_client.post(
        "/api/v1/auth/register",
        json={
            "name": "Duplicate User",
            "email": unique_email,
            "password": "ValidPassword123!",
        },
    )
    assert response.status_code == 409
    assert response.headers["content-type"] == "application/problem+json"


@pytest.mark.asyncio
async def test_login_and_token_issuance(
    async_client: AsyncClient,
):
    email = f"active_{uuid.uuid4().hex[:8]}@example.com"
    await create_user_helper(email, role="inspector", password="CorrectPass123!")

    # 1. Failed login: wrong password
    bad_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "WrongPassword!"},
    )
    assert bad_res.status_code == 401

    # 2. Successful login
    good_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "CorrectPass123!"},
    )
    assert good_res.status_code == 200
    tokens = good_res.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["token_type"] == "bearer"
    assert tokens["user"]["role"] == "inspector"


@pytest.mark.asyncio
async def test_inactive_user_login_returns_403_rfc7807(
    async_client: AsyncClient,
):
    email = f"pending_{uuid.uuid4().hex[:8]}@example.com"
    await create_user_helper(email, is_active=False, password="Password123!")

    res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert res.status_code == 403
    assert res.headers["content-type"] == "application/problem+json"
    data = res.json()
    assert "Pending Approval" in data["title"]


@pytest.mark.asyncio
async def test_token_rotation_and_replay_family_revocation(
    async_client: AsyncClient,
):
    email = f"rotate_{uuid.uuid4().hex[:8]}@example.com"
    await create_user_helper(email, role="inspector", password="Pass1234!")

    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Pass1234!"},
    )
    initial_refresh = login_res.json()["refresh_token"]

    # 1. First refresh (Rotation): Should succeed and issue new tokens
    refresh_res_1 = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": initial_refresh},
    )
    assert refresh_res_1.status_code == 200
    new_refresh = refresh_res_1.json()["refresh_token"]
    assert new_refresh != initial_refresh

    # 2. Replay attack: Attacker re-uses the old `initial_refresh` token
    replay_res = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": initial_refresh},
    )
    assert replay_res.status_code == 401
    assert replay_res.headers["content-type"] == "application/problem+json"
    assert "Token Reuse Detected" in replay_res.json()["title"]

    # 3. Family revocation verification:
    # Even the legit user's `new_refresh` token should now be REVOKED because the family was compromised!
    compromised_res = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": new_refresh},
    )
    assert compromised_res.status_code == 401


@pytest.mark.asyncio
async def test_rbac_permission_matrix(
    async_client: AsyncClient,
):
    admin_email = f"admin_{uuid.uuid4().hex[:8]}@example.com"
    inspector_email = f"inspector_{uuid.uuid4().hex[:8]}@example.com"
    viewer_email = f"viewer_{uuid.uuid4().hex[:8]}@example.com"

    await create_user_helper(admin_email, role="admin", password="Password123!")
    await create_user_helper(inspector_email, role="inspector", password="Password123!")
    await create_user_helper(viewer_email, role="viewer", password="Password123!")

    # Login all three
    admin_token = (
        await async_client.post(
            "/api/v1/auth/login",
            json={"email": admin_email, "password": "Password123!"},
        )
    ).json()["access_token"]
    inspector_token = (
        await async_client.post(
            "/api/v1/auth/login",
            json={"email": inspector_email, "password": "Password123!"},
        )
    ).json()["access_token"]
    viewer_token = (
        await async_client.post(
            "/api/v1/auth/login",
            json={"email": viewer_email, "password": "Password123!"},
        )
    ).json()["access_token"]

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    inspector_headers = {"Authorization": f"Bearer {inspector_token}"}
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    # A. /admin/users (Admin only)
    assert (await async_client.get("/api/v1/admin/users", headers=admin_headers)).status_code == 200
    assert (
        await async_client.get("/api/v1/admin/users", headers=inspector_headers)
    ).status_code == 403
    assert (
        await async_client.get("/api/v1/admin/users", headers=viewer_headers)
    ).status_code == 403

    # B. Scans write (Inspector & Admin only)
    assert (await async_client.post("/api/v1/scans", headers=admin_headers)).status_code == 200
    assert (await async_client.post("/api/v1/scans", headers=inspector_headers)).status_code == 200
    assert (await async_client.post("/api/v1/scans", headers=viewer_headers)).status_code == 403

    # C. Scans read (All authenticated roles)
    assert (await async_client.get("/api/v1/scans", headers=admin_headers)).status_code == 200
    assert (await async_client.get("/api/v1/scans", headers=inspector_headers)).status_code == 200
    assert (await async_client.get("/api/v1/scans", headers=viewer_headers)).status_code == 200
    assert (await async_client.get("/api/v1/scans")).status_code == 401


@pytest.mark.asyncio
async def test_admin_user_crud_and_audit_log(
    async_client: AsyncClient,
):
    admin_email = f"admin_crud_{uuid.uuid4().hex[:8]}@example.com"
    await create_user_helper(admin_email, role="admin", password="AdminPassword123!")

    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": admin_email, "password": "AdminPassword123!"},
    )
    admin_headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    # 1. Admin creates an inspector
    new_inspector_email = f"created_insp_{uuid.uuid4().hex[:8]}@example.com"
    create_res = await async_client.post(
        "/api/v1/admin/users",
        headers=admin_headers,
        json={
            "name": "Field Inspector Roy",
            "email": new_inspector_email,
            "password": "InspectorPass123!",
            "role": "inspector",
            "district": "Central Delhi",
            "state": "Delhi",
        },
    )
    assert create_res.status_code == 201
    created_user = create_res.json()
    assert created_user["role"] == "inspector"
    assert created_user["is_active"] is True

    # 2. Admin patches the user (e.g. promotes to admin)
    patch_res = await async_client.patch(
        f"/api/v1/admin/users/{created_user['id']}",
        headers=admin_headers,
        json={"role": "admin"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["role"] == "admin"

    # 3. Verify audit log captures these mutative events
    audit_res = await async_client.get(
        "/api/v1/admin/audit-log",
        headers=admin_headers,
    )
    assert audit_res.status_code == 200
    audit_items = audit_res.json()["items"]
    actions = [item["action"] for item in audit_items]
    assert "ADMIN_CREATE_USER" in actions
    assert "ADMIN_UPDATE_USER" in actions
