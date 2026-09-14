from typing import Literal

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
