from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
