from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

from app.api.v1.settings_schemas import ModelSummary


class AgentWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1)
    instructions: str = Field(min_length=1)
    model_id: UUID | None
    enabled: StrictBool

    @field_validator("name", "description", "instructions", mode="before")
    @classmethod
    def clean_text(cls, value):
        if not isinstance(value, str) or not value.strip() or "\x00" in value:
            raise ValueError("Nonblank text is required")
        return value.strip()


class AgentItem(AgentWrite):
    id: UUID
    model: ModelSummary | None
    created_by_id: UUID | None
    updated_by_id: UUID | None
    created_at: datetime
    updated_at: datetime


class AgentList(BaseModel):
    agents: list[AgentItem]


class AgentDeleted(BaseModel):
    id: UUID
