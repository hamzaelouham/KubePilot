from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ClusterSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    name: str
    endpoint: str
    status: str
    created_at: datetime


class ClusterListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ClusterSummary]


class ClusterCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    kubeconfig_content: str | None = None


class ClusterStatusUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str