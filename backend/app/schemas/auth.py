import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegister(BaseModel):
    """Public self-registration. Role/activation are always server-assigned."""

    name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    district: str | None = None
    state: str | None = None


class AdminUserCreate(UserRegister):
    """Admin-initiated user creation: arbitrary role, created active."""

    role: Literal["admin", "inspector", "viewer"] = "viewer"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str
    role: str
    district: str | None = None
    state: str | None = None
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserUpdate(BaseModel):
    name: str | None = None
    role: Literal["admin", "inspector", "viewer"] | None = None
    is_active: bool | None = None
    district: str | None = None
    state: str | None = None
