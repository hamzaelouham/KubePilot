from typing import Literal

from pydantic import BaseModel, ConfigDict


ClusterStatus = Literal["connected", "unavailable", "forbidden"]
ResourceType = Literal[
    "pods",
    "deployments",
    "services",
    "nodes",
    "endpoints",
    "replica-sets",
    "daemon-sets",
    "stateful-sets",
    "jobs",
    "cron-jobs",
    "replication-controllers",
    "persistent-volumes",
    "persistent-volume-claims",
    "cluster-roles",
    "storage-classes",
]

Health = Literal["healthy", "warning", "error", "unknown"]


class ClusterStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ClusterStatus
    cluster: str


class NamespaceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    status: str


class NamespaceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[NamespaceItem]


class ResourceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cluster: str
    namespace: str | None
    kind: str
    name: str
    status: str
    health: Health


class ResourceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ResourceItem]
