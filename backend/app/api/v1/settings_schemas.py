from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ThemePreference = Literal["system", "light", "dark"]


class SettingsAccessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed: bool


class SettingsPreferencesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_namespace: str | None
    theme: ThemePreference


class SettingsPreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_namespace: str | None = Field(default=None, max_length=63, pattern=r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
    theme: ThemePreference | None = None


class ApplicationSettingItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    value: Any
    updated_at: datetime | None


class ApplicationSettingsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    settings: list[ApplicationSettingItem]


class ApplicationSettingValueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: Any


class CredentialMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    credential_key: str
    configured: bool
    updated_at: datetime | None


class CredentialsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    credentials: list[CredentialMetadata]


class CredentialValueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str = Field(min_length=1, max_length=100_000)


ProviderId = Literal["openai", "openrouter", "ollama"]
ProviderStatus = Literal["configured", "not_configured"]
ConnectionTestStatus = Literal["connected", "not_configured", "blocked", "failed"]


class ProviderSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: ProviderId
    name: str
    base_url: str | None
    credential_required: bool
    api_key_configured: bool
    status: ProviderStatus
    updated_at: datetime | None


class ProvidersResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    providers: list[ProviderSummary]


class ProviderSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_url: str = Field(min_length=1, max_length=2048)
    api_key_action: Literal["unchanged", "replace", "clear"] = "unchanged"
    api_key: str | None = Field(default=None, min_length=1, max_length=100_000)

    @model_validator(mode="after")
    def validate_api_key_action(self) -> "ProviderSaveRequest":
        if self.api_key_action == "replace" and self.api_key is None:
            raise ValueError("api_key is required when api_key_action is replace")
        if self.api_key_action != "replace" and self.api_key is not None:
            raise ValueError("api_key is only accepted when api_key_action is replace")
        return self


class ProviderTestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: ProviderId
    status: ConnectionTestStatus
    message: str


ModelAvailability = Literal["unknown", "available", "unavailable"]


class ModelCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    streaming: bool
    tools: bool
    reasoning: bool
    vision: bool
    large_context: bool


class ModelWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: ProviderId
    external_model_id: str = Field(min_length=1, max_length=255)
    friendly_name: str = Field(min_length=1, max_length=128)
    enabled: bool = False
    capabilities: ModelCapabilities

    @field_validator("external_model_id", "friendly_name")
    @classmethod
    def reject_blank_values(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("Value must not be blank")
        return clean


class ModelSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    provider_id: ProviderId
    provider_name: str
    external_model_id: str
    friendly_name: str
    enabled: bool
    is_default: bool
    capabilities: ModelCapabilities
    availability: ModelAvailability
    availability_message: str | None
    availability_checked_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ModelsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    models: list[ModelSummary]


AuditLogCategory = Literal["admin", "resource", "helm", "ai", "other"]


class AuditLogActor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    email: str


class AuditLogItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    created_at: datetime
    actor: AuditLogActor | None
    action: str
    category: AuditLogCategory
    resource_type: str
    resource_id: str
    target_user: AuditLogActor | None
    result: str
    context: Any


class AuditLogsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    logs: list[AuditLogItem]
    page: int
    limit: int
    total: int
    total_pages: int


class EligibleModelSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    provider_id: ProviderId
    provider_name: str
    external_model_id: str
    friendly_name: str
    capabilities: ModelCapabilities
    is_default: bool


class EligibleModelsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    models: list[EligibleModelSummary]
