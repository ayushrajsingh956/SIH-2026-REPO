import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit_event
from app.core.database import get_db
from app.core.deps import require_role
from app.core.exceptions import ProblemDetailException
from app.core.security import get_password_hash
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.admin import (
    AuditLogListResponse,
    AuditLogResponse,
    UserListResponse,
)
from app.schemas.auth import UserRegister, UserResponse, UserUpdate

router = APIRouter(
    prefix="/admin",
    tags=["Administration"],
    dependencies=[Depends(require_role("admin"))],
)


@router.get(
    "/users",
    response_model=UserListResponse,
    summary="List all users with filtering (Admin only)",
)
async def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    role: Literal["admin", "inspector", "viewer"] | None = None,
    is_active: bool | None = None,
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> UserListResponse:
    query = select(User)
    count_query = select(func.count(User.id))

    if role:
        query = query.where(User.role == role)
        count_query = count_query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
        count_query = count_query.where(User.is_active == is_active)
    if q:
        search_filter = User.name.ilike(f"%{q}%") | User.email.ilike(f"%{q}%")
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    total_res = await db.execute(count_query)
    total = total_res.scalar() or 0

    offset = (page - 1) * limit
    users_res = await db.execute(query.order_by(User.created_at.desc()).offset(offset).limit(limit))
    users = users_res.scalars().all()

    return UserListResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        limit=limit,
    )


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user with any role (Admin only)",
)
async def create_user(
    user_in: UserRegister,
    admin_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> User:
    existing = await db.execute(select(User).where(User.email == user_in.email))
    if existing.scalar_one_or_none():
        raise ProblemDetailException(
            status_code=status.HTTP_409_CONFLICT,
            title="Email Conflict",
            detail="A user with this email address already exists",
        )

    user = User(
        name=user_in.name,
        email=user_in.email,
        password_hash=get_password_hash(user_in.password),
        role=user_in.role or "viewer",
        district=user_in.district,
        state=user_in.state,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    await record_audit_event(
        db=db,
        user_id=admin_user.id,
        action="ADMIN_CREATE_USER",
        entity_type="user",
        entity_id=user.id,
        detail={"email": user.email, "role": user.role},
    )

    return user


@router.patch(
    "/users/{user_id}",
    response_model=UserResponse,
    summary="Update user role or active status (Admin only)",
)
async def update_user(
    user_id: uuid.UUID,
    update_in: UserUpdate,
    admin_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise ProblemDetailException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Not Found",
            detail=f"User {user_id} not found",
        )

    changes = {}
    if update_in.name is not None:
        user.name = update_in.name
        changes["name"] = update_in.name
    if update_in.role is not None:
        user.role = update_in.role
        changes["role"] = update_in.role
    if update_in.is_active is not None:
        user.is_active = update_in.is_active
        changes["is_active"] = update_in.is_active
    if update_in.district is not None:
        user.district = update_in.district
        changes["district"] = update_in.district
    if update_in.state is not None:
        user.state = update_in.state
        changes["state"] = update_in.state

    await record_audit_event(
        db=db,
        user_id=admin_user.id,
        action="ADMIN_UPDATE_USER",
        entity_type="user",
        entity_id=user.id,
        detail=changes,
    )

    return user


@router.get(
    "/audit-log",
    response_model=AuditLogListResponse,
    summary="Get paginated audit trail (Admin only)",
)
async def get_audit_log(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    action: str | None = None,
    user_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    query = select(AuditLog)
    count_query = select(func.count(AuditLog.id))

    if action:
        query = query.where(AuditLog.action == action)
        count_query = count_query.where(AuditLog.action == action)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
        count_query = count_query.where(AuditLog.user_id == user_id)

    total_res = await db.execute(count_query)
    total = total_res.scalar() or 0

    offset = (page - 1) * limit
    logs_res = await db.execute(
        query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    )
    logs = logs_res.scalars().all()

    return AuditLogListResponse(
        items=[AuditLogResponse.model_validate(log) for log in logs],
        total=total,
        page=page,
        limit=limit,
    )
