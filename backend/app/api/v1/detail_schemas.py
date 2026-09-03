from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


DetailResourceType = Literal["pods", "deployments", "services", "nodes"]


class DetailIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cluster: str
    resource_type: DetailResourceType
    name: str = Field(min_length=1, max_length=253, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    namespace: str | None = Field(default=None, max_length=253, pattern=r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$|^$^")


class ResourceDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cluster: str
    resource_type: DetailResourceType
    name: str
    namespace: str | None
    kind: str
    status: str
    metadata: dict[str, str]
    source: Literal["kubernetes"]


class YamlResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str
    truncated: bool


class LogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lines: list[str]
    container: str | None
    truncated: bool


class EventItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    reason: str
    message: str
    source: str
    created_at: str | None


class EventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[EventItem]
    truncated: bool
