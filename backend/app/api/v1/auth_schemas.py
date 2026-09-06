from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    password: str


class LoginResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cookie: str
    expires_at: int
    change_required: bool = False


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str
    new_password: str


class MeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    email: str
    role: str
    is_active: bool
    must_change_password: bool
    password_expires_at: datetime | None
    password_expired: bool
    last_login_at: datetime | None
    created_at: datetime