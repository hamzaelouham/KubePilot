from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class HelmReleaseSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    namespace: str
    status: str | None = None
    revision: int | None = None
    chart: str | None = None
    app_version: str | None = None
    updated: str | None = None
    description: str | None = None


class HelmReleaseListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[HelmReleaseSummary]


class HelmReleaseRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision: int
    updated: str | None = None
    status: str | None = None
    chart: str | None = None
    app_version: str | None = None
    description: str | None = None


class HelmReleaseHistoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    release_name: str
    namespace: str
    revisions: list[HelmReleaseRevision]


class HelmReleaseActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm_name: str = Field(min_length=1, max_length=253)


class HelmReleaseUpgradeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository_id: UUID
    chart_name: str = Field(min_length=1, max_length=253)
    version: str = Field(min_length=1, max_length=64)
    confirm_name: str = Field(min_length=1, max_length=253)


class HelmReleaseActionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    status: Literal["queued"]
