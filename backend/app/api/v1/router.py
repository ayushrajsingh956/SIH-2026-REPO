from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.products import router as products_router
from app.api.v1.reports import router as reports_router
from app.api.v1.rules import admin_router as rules_admin_router
from app.api.v1.rules import router as rules_router
from app.api.v1.scans import router as scans_router
from app.api.v1.violations import router as violations_router

api_router = APIRouter()

# Mount feature modules
api_router.include_router(auth_router)
api_router.include_router(admin_router)
api_router.include_router(scans_router)
api_router.include_router(dashboard_router)
api_router.include_router(products_router)
api_router.include_router(violations_router)
api_router.include_router(reports_router)
api_router.include_router(rules_router, prefix="/rules")
api_router.include_router(rules_admin_router, prefix="/admin/rules")


@api_router.get("/status", tags=["Status"])
async def api_status() -> dict:
    return {
        "status": "online",
        "api_version": "v1",
        "service": "LegalMetro Shield API",
    }
