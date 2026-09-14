from pydantic import BaseModel, ConfigDict


class SettingsAccessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed: bool
