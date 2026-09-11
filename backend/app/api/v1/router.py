from fastapi import APIRouter, Depends

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.core.deps import require_role
from app.models.user import User

api_router = APIRouter()

# Mount authentication and admin modules
api_router.include_router(auth_router)
api_router.include_router(admin_router)


@api_router.get("/status", tags=["Status"])
async def api_status() -> dict:
    return {
        "status": "online",
        "api_version": "v1",
        "service": "LegalMetro Shield API",
    }


# Route-level RBAC test endpoints matching Spec §5 & §11
@api_router.post(
    "/scans",
    tags=["Scans"],
    summary="Create a new label scan (Inspector & Admin only)",
)
async def create_scan_stub(
    current_user: User = Depends(require_role("admin", "inspector")),
) -> dict:
    return {
        "status": "queued",
        "message": "Scan initiated",
        "scanned_by": str(current_user.id),
    }


@api_router.get(
    "/scans",
    tags=["Scans"],
    summary="List scans (All authenticated roles: Admin, Inspector, Viewer)",
)
async def list_scans_stub(
    current_user: User = Depends(require_role("admin", "inspector", "viewer")),
) -> dict:
    return {
        "items": [],
        "total": 0,
        "caller": current_user.email,
    }
