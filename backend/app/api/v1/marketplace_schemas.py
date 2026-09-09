from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MarketplacePackageRepository(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    display_name: Optional[str] = None
    organization_name: Optional[str] = None
    organization_display_name: Optional[str] = None
    url: Optional[str] = None
    kind: Optional[int] = None


class MarketplacePackageSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_id: str
    name: str
    normalized_name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    app_version: Optional[str] = None
    logo_image_id: Optional[str] = None
    stars: Optional[int] = None
    deprecated: bool = False
    official: bool = False
    signed: bool = False
    license: Optional[str] = None
    repository: Optional[MarketplacePackageRepository] = None


class MarketplaceSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    packages: list[MarketplacePackageSummary]
    total: int


class MarketplaceVersionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_id: str
    name: str
    repository_name: str
    versions: list[str]


DNS_1123_LABEL_PATTERN = r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$"


class MarketplaceInstallRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_id: str = Field(min_length=1)
    package_name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    repository_name: str = Field(pattern=DNS_1123_LABEL_PATTERN, max_length=63)
    cluster: str = Field(min_length=1)
    namespace: str = Field(pattern=DNS_1123_LABEL_PATTERN, max_length=63)
    release_name: str = Field(pattern=DNS_1123_LABEL_PATTERN, max_length=63)


class MarketplaceInstallResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    status: Literal["queued"]


class MarketplaceInstallationStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    package_name: str
    cluster: str
    namespace: str
    release_name: str
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class MarketplaceInstallationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplaceInstallationStatus]
    total: int