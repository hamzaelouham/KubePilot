from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ClusterSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    name: str
    endpoint: str
    status: str
    connection_status: Literal["connected", "unavailable", "forbidden", "inactive", "unknown"] = "unknown"
    created_at: datetime


class ClusterListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ClusterSummary]


class ClusterCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    kubeconfig_content: str | None = None


class ClusterUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    kubeconfig_content: str | None = None
    status: str | None = None
