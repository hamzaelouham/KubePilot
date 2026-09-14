from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


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
