from datetime import datetime
from typing import Literal
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
    skill_ids: list[UUID] = Field(default_factory=list, max_length=64)
    tool_ids: list[str] = Field(default_factory=list, max_length=64)

    @field_validator("name", "description", "instructions", mode="before")
    @classmethod
    def clean_text(cls, value):
        if not isinstance(value, str) or not value.strip() or "\x00" in value:
            raise ValueError("Nonblank text is required")
        return value.strip()

    @field_validator("skill_ids")
    @classmethod
    def unique_ids(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("Assignments must not contain duplicates")
        return value

    @field_validator("tool_ids")
    @classmethod
    def unique_tool_ids(cls, value):
        if len(value) != len(set(value)) or any(not item.strip() or "\x00" in item for item in value):
            raise ValueError("Assignment identifiers must be nonblank and unique")
        return value


class AgentSkillReference(BaseModel):
    id: UUID
    name: str
    description: str
    instructions: str


class AgentCapability(BaseModel):
    id: str
    label: str
    description: str
    kind: str
    required_permission: str
    configured: bool
    model_supported: bool
    actor_permitted: bool
    status: str


class AgentItem(AgentWrite):
    id: UUID
    model: ModelSummary | None
    created_by_id: UUID | None
    updated_by_id: UUID | None
    created_at: datetime
    updated_at: datetime
    skills: list[AgentSkillReference]
    capabilities: list[AgentCapability]


class AgentNotificationDestinationWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: Literal["slack", "gmail", "outlook"]
    label: str = Field(min_length=1, max_length=128)
    destination: str = Field(min_length=1, max_length=512)
    enabled: StrictBool = True

    @field_validator("label", "destination", mode="before")
    @classmethod
    def clean_destination_text(cls, value):
        if not isinstance(value, str) or not value.strip() or "\x00" in value:
            raise ValueError("Nonblank destination text is required")
        return value.strip()


class AgentNotificationDestinationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    provider_id: Literal["slack", "gmail", "outlook"]
    label: str
    destination_hint: str
    enabled: bool
    connection_status: str
    updated_at: datetime


class AgentNotificationDestinationList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destinations: list[AgentNotificationDestinationItem]


class AgentList(BaseModel):
    agents: list[AgentItem]


class AgentDeleted(BaseModel):
    id: UUID


class AgentSkillWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1)
    instructions: str = Field(min_length=1)

    @field_validator("name", "description", "instructions", mode="before")
    @classmethod
    def clean_text(cls, value):
        if not isinstance(value, str) or not value.strip() or "\x00" in value:
            raise ValueError("Nonblank text is required")
        return value.strip()


class AgentSkillItem(AgentSkillWrite):
    id: UUID
    created_by_id: UUID | None
    updated_by_id: UUID | None
    created_at: datetime
    updated_at: datetime
    assigned_agent_count: int = Field(ge=0)


class AgentSkillList(BaseModel):
    skills: list[AgentSkillItem]


class AgentSkillDeleted(BaseModel):
    id: UUID


class AgentToolDefinition(BaseModel):
    id: str
    label: str
    description: str
    kind: str
    required_permission: str


class AgentToolList(BaseModel):
    tools: list[AgentToolDefinition]


class AgentTemplate(BaseModel):
    id: str
    name: str
    description: str
    instructions: str
    tool_ids: list[str]


class AgentTemplateList(BaseModel):
    templates: list[AgentTemplate]
