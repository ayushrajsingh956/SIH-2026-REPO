import pytest
from httpx import AsyncClient

from app.core.limiter import limiter


@pytest.mark.anyio
async def test_login_rate_limiting(async_client: AsyncClient):
    limiter.enabled = True
    try:
        # login is limited to 5/minute
        responses = []
        for _ in range(7):
            resp = await async_client.post(
                "/api/v1/auth/login",
                json={"email": "ratelimit_test@example.com", "password": "WrongPassword123!"},
            )
            responses.append(resp)

        # At least one response should be 429 Too Many Requests
        status_codes = [r.status_code for r in responses]
        assert 429 in status_codes, f"Expected 429 in {status_codes}"

        # Find the 429 response
        rate_limited_resp = next(r for r in responses if r.status_code == 429)
        assert rate_limited_resp.headers.get("Retry-After") is not None
        data = rate_limited_resp.json()
        assert data["status"] == 429
        assert data["type"] == "https://errors.legalmetro.gov.in/rate-limit-exceeded"
        assert "Rate limit exceeded" in data["detail"]
    finally:
        limiter.enabled = False
