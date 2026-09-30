from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator

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


class AgentAutomationTriggerWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trigger_type: Literal["schedule", "kubernetes_event"]
    cluster_id: UUID
    namespace: str | None = Field(default=None, max_length=253)
    cron_expression: str | None = Field(default=None, max_length=128)
    timezone: str = Field(default="UTC", min_length=1, max_length=64)
    event_kind: str | None = Field(default=None, max_length=64)
    event_name: str | None = Field(default=None, max_length=253)
    event_type: str | None = Field(default=None, max_length=32)
    event_reason: str | None = Field(default=None, max_length=128)
    owner_id: UUID
    notification_destination_ids: list[UUID] = Field(default_factory=list, max_length=20)
    enabled: StrictBool = False

    @field_validator("namespace", "cron_expression", "timezone", "event_kind", "event_name", "event_type", "event_reason", mode="before")
    @classmethod
    def clean_optional_text(cls, value):
        if value is None:
            return value
        if not isinstance(value, str) or not value.strip() or "\x00" in value:
            raise ValueError("Text values must be nonblank")
        return value.strip()

    @field_validator("notification_destination_ids")
    @classmethod
    def unique_destinations(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("Notification destinations must not be duplicated")
        return value


class AgentAutomationTriggerItem(AgentAutomationTriggerWrite):
    id: UUID
    last_evaluated_at: datetime | None
    created_by_id: UUID | None
    updated_by_id: UUID | None
    created_at: datetime
    updated_at: datetime


class AgentAutomationTriggerList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    triggers: list[AgentAutomationTriggerItem]


class AgentRunItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    trigger_id: UUID | None
    agent_id: UUID
    owner_id: UUID
    cluster_id: UUID
    namespace: str | None
    trigger_type: Literal["schedule", "kubernetes_event"]
    scheduled_for: datetime | None
    event_id: UUID | None
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    attempt_count: int
    result_code: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class AgentRunList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runs: list[AgentRunItem]
    total: int


class AgentRunLogs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    log_output: str | None


class AgentRetention(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retention_days: StrictInt = Field(ge=1, le=365)


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
