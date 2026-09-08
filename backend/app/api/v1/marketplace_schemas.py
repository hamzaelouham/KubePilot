from typing import Optional

from pydantic import BaseModel, ConfigDict


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