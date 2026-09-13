from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class HelmRepositoryCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=63)
    url: str = Field(min_length=1, max_length=2048)


class HelmRepositoryUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1, max_length=63)
    url: Optional[str] = Field(default=None, min_length=1, max_length=2048)


class HelmRepositorySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    name: str
    url: str
    created_by_id: Optional[UUID] = None
    updated_by_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


class HelmRepositoryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[HelmRepositorySummary]


class HelmRepositoryDeleteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    status: str
