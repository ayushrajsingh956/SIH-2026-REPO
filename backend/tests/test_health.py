from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_healthz_healthy(async_client: AsyncClient):
    with (
        patch("app.main.AsyncSessionLocal") as mock_session_local,
        patch("app.main.redis_from_url") as mock_redis_url,
        patch("app.main.check_minio_health", return_value=(True, None)),
    ):
        # Mock database session execute
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session_local.return_value.__aenter__.return_value = mock_session

        # Mock redis ping
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_redis.aclose = AsyncMock()
        mock_redis_url.return_value = mock_redis

        response = await async_client.get("/healthz")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "database" in data["dependencies"]
        assert "redis" in data["dependencies"]
        assert "storage" in data["dependencies"]
        assert data["dependencies"]["database"]["status"] == "ok"
        assert data["dependencies"]["redis"]["status"] == "ok"
        assert data["dependencies"]["storage"]["status"] == "ok"


@pytest.mark.asyncio
async def test_healthz_unhealthy(async_client: AsyncClient):
    with (
        patch("app.main.AsyncSessionLocal", side_effect=Exception("DB Down")),
        patch("app.main.redis_from_url", side_effect=Exception("Redis Down")),
        patch("app.main.check_minio_health", return_value=(False, "MinIO Down")),
    ):
        response = await async_client.get("/healthz")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["dependencies"]["database"]["status"] == "unhealthy"
        assert data["dependencies"]["redis"]["status"] == "unhealthy"
        assert data["dependencies"]["storage"]["status"] == "unhealthy"


@pytest.mark.asyncio
async def test_rfc7807_not_found(async_client: AsyncClient):
    response = await async_client.get("/api/v1/non-existent-endpoint")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    data = response.json()
    assert "status" in data
    assert data["status"] == 404
    assert "title" in data
    assert "detail" in data
    assert "instance" in data


@pytest.mark.asyncio
async def test_api_v1_status(async_client: AsyncClient):
    response = await async_client.get("/api/v1/status")
    assert response.status_code == 200
    assert response.json()["status"] == "online"
