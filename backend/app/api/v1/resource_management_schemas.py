from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictStr

from app.api.v1.discovery_schemas import Health

ManagementResourceType = Literal[
    "pods", "deployments", "namespaces", "services",
    "stateful-sets", "daemon-sets", "jobs", "cron-jobs",
]


class ManagementSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ManagedResource(ManagementSchema):
    cluster: str
    cluster_id: UUID
    resource_type: ManagementResourceType
    api_version: str
    kind: str
    name: str
    namespace: str | None
    uid: str = Field(min_length=1)
    status: str
    health: Health
    deletion_timestamp: datetime | None
    delete_blocked_reason: str | None


class ManagedResourceList(ManagementSchema):
    items: list[ManagedResource]


class CreateResourceRequest(ManagementSchema):
    yaml: StrictStr = Field(min_length=1)


class CreatedResource(ManagementSchema):
    status: Literal["created"] = "created"
    resource: ManagedResource


class DeleteResourceRequest(ManagementSchema):
    uid: StrictStr = Field(min_length=1)
    confirm_name: StrictStr


class DeletionRequested(ManagementSchema):
    status: Literal["deletion_requested"] = "deletion_requested"
    cluster: str
    cluster_id: UUID
    resource_type: ManagementResourceType
    namespace: str | None
    name: str
    uid: str
