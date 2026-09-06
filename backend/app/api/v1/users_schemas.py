from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    email: str
    role: str
    is_active: bool
    password_expires_at: datetime | None
    password_expired: bool
    must_change_password: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class UserListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[UserSummary]


class UserCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    password: str
    role: str = "viewer"
    password_expires_in_days: int | None = None


class UserUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str | None = None
    is_active: bool | None = None
    force_password_change: bool | None = None
    password_expires_in_days: int | None = None


class PasswordResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_password: str