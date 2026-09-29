from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


IntegrationStatus = Literal["not_connected", "authorizing", "connected", "error", "revoked", "not_supported"]


class IntegrationCatalogItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: str
    name: str
    supported: bool
    configured: bool
    manual_token_configured: bool
    status: IntegrationStatus
    external_account_label: str | None
    granted_scopes: list[str]
    last_tested_at: datetime | None
    last_error_code: str | None


class IntegrationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    integrations: list[IntegrationCatalogItem]


class IntegrationAuthorizeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: str
    authorization_url: str
    expires_at: datetime


class IntegrationActionResponse(IntegrationCatalogItem):
    message: str


class IntegrationCallbackResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: str
    status: IntegrationStatus
    connected: bool
    message: str
    error_code: str | None = None


DeliveryStatus = Literal["queued", "running", "succeeded", "failed", "outcome_unknown"]


class IntegrationDeliveryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    delivery_id: UUID
    provider_id: str
    event_type: str
    destination_hint: str
    status: DeliveryStatus
    attempt_count: int
    max_attempts: int
    next_attempt_at: datetime
    last_error_code: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class IntegrationDeliveryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[IntegrationDeliveryItem]
    total: int
    page: int
    limit: int


class IntegrationDeliveryRetryResponse(IntegrationDeliveryItem):
    message: str
