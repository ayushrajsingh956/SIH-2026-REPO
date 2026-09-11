from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.limiter import limiter
from app.main import app

# Disable rate limiter for functional test suites so tests aren't blocked
limiter.enabled = False
# Default test settings so pipeline tests execute clean mocks without real API leakage
settings.OCR_PROVIDER = "gemini"
settings.GROQ_MODEL = "groq/compound"
settings.GROQ_API_KEY = ""
settings.GEMINI_API_KEY = ""


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
