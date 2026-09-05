from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserRole(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["admin", "operator", "viewer"]


class UserItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    email: str
    role: Literal["admin", "operator", "viewer"]
    isActive: bool
    createdAt: datetime


class UserListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[UserItem]


class DeactivatedUserResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    isActive: bool


class CreateUserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    password: str = Field(min_length=1)
    role: Literal["admin", "operator", "viewer"]