import io
import uuid
from unittest.mock import patch

import httpx
import respx
from httpx import AsyncClient

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, get_password_hash
from app.models.scan import Scan
from app.models.user import User

# Valid 1x1 PNG bytes for testing
TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


async def create_test_user(role: str) -> tuple[User, str]:
    async with AsyncSessionLocal() as session:
        user = User(
            name=f"User {role}",
            email=f"{role}_{uuid.uuid4().hex[:8]}@example.com",
            password_hash=get_password_hash("ValidPassword123!"),
            role=role,
            is_active=True,
            district="District A",
            state="State B",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    token = create_access_token(user_id=user.id, role=role)
    return user, token


class TestScansMultipartUpload:
    async def test_upload_single_image_success(self, async_client: AsyncClient):
        _, token = await create_test_user("inspector")

        files = [
            ("images", ("label.png", io.BytesIO(TINY_PNG), "image/png")),
        ]
        data = {
            "mode": "retail",
            "font_check_mode": "relative",
        }

        with (
            patch("app.api.v1.scans.put_object_bytes", return_value="mock_key"),
            patch("app.api.v1.scans.scan_pipeline_task.delay") as mock_delay,
        ):
            response = await async_client.post(
                "/api/v1/scans",
                headers={"Authorization": f"Bearer {token}"},
                data=data,
                files=files,
            )

            assert response.status_code == 202
            res_json = response.json()
            assert "scan_id" in res_json
            assert res_json["status"] == "queued"
            assert res_json["images_count"] == 1
            mock_delay.assert_called_once()

    async def test_upload_multiple_images_up_to_limit(self, async_client: AsyncClient):
        _, token = await create_test_user("admin")

        files = [
            ("images", (f"label_{i}.png", io.BytesIO(TINY_PNG), "image/png")) for i in range(4)
        ]

        with (
            patch("app.api.v1.scans.put_object_bytes", return_value="mock_key"),
            patch("app.api.v1.scans.scan_pipeline_task.delay") as mock_delay,
        ):
            response = await async_client.post(
                "/api/v1/scans",
                headers={"Authorization": f"Bearer {token}"},
                files=files,
            )

            assert response.status_code == 202
            assert response.json()["images_count"] == 4
            mock_delay.assert_called_once()

    async def test_exceeding_max_images_returns_400(self, async_client: AsyncClient):
        _, token = await create_test_user("inspector")

        # 7 images exceeds MAX_IMAGES_PER_SCAN (6)
        files = [
            ("images", (f"label_{i}.png", io.BytesIO(TINY_PNG), "image/png")) for i in range(7)
        ]

        response = await async_client.post(
            "/api/v1/scans",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
        )
        assert response.status_code == 400
        assert "Images count must be between 1 and 6" in response.json()["detail"]

    async def test_spoofed_file_type_returns_415(self, async_client: AsyncClient):
        _, token = await create_test_user("inspector")

        # Bash script disguised with .png filename
        fake_png = b"#!/bin/bash\necho malicious\n"
        files = [
            ("images", ("exploit.png", io.BytesIO(fake_png), "image/png")),
        ]

        response = await async_client.post(
            "/api/v1/scans",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
        )
        assert response.status_code == 415

    async def test_rbac_viewer_rejected_from_creating_scan(self, async_client: AsyncClient):
        _, token = await create_test_user("viewer")

        files = [
            ("images", ("label.png", io.BytesIO(TINY_PNG), "image/png")),
        ]
        response = await async_client.post(
            "/api/v1/scans",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
        )
        assert response.status_code == 403


class TestScansEcommerceUrl:
    async def test_ssrf_prohibited_urls_rejected(self, async_client: AsyncClient):
        _, token = await create_test_user("inspector")

        response = await async_client.post(
            "/api/v1/scans/url",
            headers={"Authorization": f"Bearer {token}"},
            json={"url": "http://127.0.0.1:8000/scans"},
        )
        assert response.status_code == 400
        assert "Invalid or prohibited URL" in response.json()["detail"]

    @respx.mock
    async def test_valid_ecommerce_url_scraped_and_queued(self, async_client: AsyncClient):
        _, token = await create_test_user("inspector")

        product_url = "https://www.example.com/products/shampoo-bottle"
        image_url = "https://www.example.com/images/shampoo.png"

        html_body = f"""
        <html>
          <head>
            <title>Premium Shampoo 500ml</title>
            <meta property="og:title" content="Premium Shampoo 500ml" />
            <meta property="og:image" content="{image_url}" />
          </head>
          <body><h1>Product Description</h1></body>
        </html>
        """

        respx.get(product_url).mock(return_value=httpx.Response(200, text=html_body))
        respx.get(image_url).mock(return_value=httpx.Response(200, content=TINY_PNG))

        with (
            patch("app.api.v1.scans.put_object_bytes", return_value="mock_key"),
            patch("app.api.v1.scans.scan_pipeline_task.delay") as mock_delay,
        ):
            response = await async_client.post(
                "/api/v1/scans/url",
                headers={"Authorization": f"Bearer {token}"},
                json={"url": product_url},
            )

            assert response.status_code == 202
            res_json = response.json()
            assert res_json["status"] == "queued"
            mock_delay.assert_called_once()


class TestScanDetailPolling:
    async def test_get_scan_detail_polling(self, async_client: AsyncClient):
        user, token = await create_test_user("viewer")

        scan_id = uuid.uuid4()
        async with AsyncSessionLocal() as session:
            scan = Scan(
                id=scan_id,
                scanned_by=user.id,
                mode="retail",
                image_urls=["scans/mock/image.png"],
                status="completed",
                font_check_mode="relative",
                pipeline_meta={"model": "gemini-2.5-flash"},
            )
            session.add(scan)
            await session.commit()

        with patch(
            "app.api.v1.scans.presign_get_url", return_value="https://minio.local/presigned.png"
        ):
            response = await async_client.get(
                f"/api/v1/scans/{scan_id}",
                headers={"Authorization": f"Bearer {token}"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == str(scan_id)
            assert data["status"] == "completed"
            assert len(data["presigned_image_urls"]) == 1

    async def test_get_nonexistent_scan_returns_404(self, async_client: AsyncClient):
        _, token = await create_test_user("viewer")
        random_id = uuid.uuid4()
        response = await async_client.get(
            f"/api/v1/scans/{random_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404


class TestScanEventsWebSocket:
    async def test_websocket_initial_event_terminal(self):
        from starlette.testclient import TestClient

        from app.main import app

        user, token = await create_test_user("inspector")
        scan_id = uuid.uuid4()
        async with AsyncSessionLocal() as session:
            scan = Scan(
                id=scan_id,
                scanned_by=user.id,
                mode="retail",
                image_urls=["scans/mock/image.png"],
                status="completed",
                pipeline_meta={"model": "gemini-2.5-flash"},
            )
            session.add(scan)
            await session.commit()

        client = TestClient(app)
        with client.websocket_connect(f"/api/v1/scans/{scan_id}/events?token={token}") as websocket:
            data = websocket.receive_json()
            assert data["scan_id"] == str(scan_id)
            assert data["status"] == "completed"

    async def test_websocket_unauthenticated_rejected(self):
        import pytest
        from starlette.testclient import TestClient
        from starlette.websockets import WebSocketDisconnect

        from app.main import app

        user, _ = await create_test_user("inspector")
        scan_id = uuid.uuid4()
        async with AsyncSessionLocal() as session:
            scan = Scan(
                id=scan_id,
                scanned_by=user.id,
                mode="retail",
                image_urls=["scans/mock/image.png"],
                status="completed",
                pipeline_meta={"model": "gemini-2.5-flash"},
            )
            session.add(scan)
            await session.commit()

        client = TestClient(app)
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/api/v1/scans/{scan_id}/events"):
                pass
        assert exc_info.value.code == 1008
