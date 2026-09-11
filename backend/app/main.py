import asyncio
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import from_url as redis_from_url
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.exceptions import register_exception_handlers
from app.core.limiter import limiter
from app.schemas.health import HealthResponse
from app.services.rules import load_rules
from app.services.storage.minio_client import check_minio_health


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Lifespan startup hooks: validate and load rules fail-fast
    load_rules()
    yield
    # Lifespan shutdown hooks can go here


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="0.1.0",
        description="Software System to check compliance under Legal Metrology (Packaged Commodities) Rules, 2011",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Register RFC7807 problem details handlers
    register_exception_handlers(app)

    # Rate limiter
    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "type": "https://errors.legalmetro.gov.in/rate-limit-exceeded",
                "title": "Too Many Requests",
                "status": 429,
                "detail": f"Rate limit exceeded: {exc.detail}",
                "instance": str(request.url.path),
            },
            headers={"Retry-After": "60"},
        )

    # CORS Middleware with explicit list and regex for all localhost development ports
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount /api/v1
    app.include_router(api_router, prefix=settings.API_V1_STR)

    @app.get(
        "/healthz",
        response_model=HealthResponse,
        tags=["Health"],
        summary="Service Health Check",
    )
    async def health_check(response: Response) -> HealthResponse:
        overall_ok = True
        deps = {}

        # 1. Database Check
        t0 = time.perf_counter()
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))
            db_latency = round((time.perf_counter() - t0) * 1000, 2)
            deps["database"] = {"status": "ok", "latency_ms": db_latency}
        except Exception as exc:
            overall_ok = False
            deps["database"] = {"status": "unhealthy", "error": str(exc)}

        # 2. Redis Check
        t0 = time.perf_counter()
        try:
            r = redis_from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
            await r.ping()
            await r.aclose()
            redis_latency = round((time.perf_counter() - t0) * 1000, 2)
            deps["redis"] = {"status": "ok", "latency_ms": redis_latency}
        except Exception as exc:
            overall_ok = False
            deps["redis"] = {"status": "unhealthy", "error": str(exc)}

        # 3. MinIO Check
        t0 = time.perf_counter()
        try:
            loop = asyncio.get_running_loop()
            minio_ok, minio_err = await loop.run_in_executor(None, check_minio_health)
            minio_latency = round((time.perf_counter() - t0) * 1000, 2)
            if minio_ok:
                deps["storage"] = {
                    "status": "ok",
                    "bucket": settings.MINIO_BUCKET,
                    "latency_ms": minio_latency,
                }
            else:
                overall_ok = False
                deps["storage"] = {"status": "unhealthy", "error": minio_err}
        except Exception as exc:
            overall_ok = False
            deps["storage"] = {"status": "unhealthy", "error": str(exc)}

        if not overall_ok:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

        return HealthResponse(
            status="ok" if overall_ok else "unhealthy",
            dependencies=deps,
        )

    return app


app = create_app()
