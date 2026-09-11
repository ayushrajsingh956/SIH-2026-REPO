import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.schemas.auth import UserResponse


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    limit: int


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None = None
    action: str
    entity_type: str
    entity_id: uuid.UUID | None = None
    detail: dict[str, Any] | None = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    limit: int
