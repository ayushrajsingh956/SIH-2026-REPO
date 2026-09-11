from fastapi import APIRouter

api_router = APIRouter()


@api_router.get("/status", tags=["Status"])
async def api_status() -> dict:
    return {
        "status": "online",
        "api_version": "v1",
        "service": "LegalMetro Shield API",
    }
