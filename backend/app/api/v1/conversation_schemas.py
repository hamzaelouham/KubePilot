import json
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.assistant.schemas import StrictModel


ConversationMode = Literal["direct", "agent"]


class ConversationContext(StrictModel):
    cluster: str = Field(min_length=1, max_length=253)
    namespace: str | None = Field(default=None, max_length=253)
    resource: str | None = Field(default=None, max_length=64)
    name: str | None = Field(default=None, max_length=253)
    release: str | None = Field(default=None, max_length=253)


class ConversationSelection(StrictModel):
    mode: ConversationMode = "direct"
    model_id: UUID | None = None
    agent_id: UUID | None = None

    @field_validator("model_id", "agent_id", mode="before")
    @classmethod
    def parse_json_uuid(cls, value: UUID | str | None) -> UUID | str | None:
        # FastAPI passes decoded JSON to Pydantic's strict Python validator;
        # UUIDs therefore arrive as strings even though they are typed IDs.
        return UUID(value) if isinstance(value, str) else value

    @model_validator(mode="after")
    def exclusive_selection(self):
        if self.mode == "direct" and self.agent_id is not None:
            raise ValueError("Direct conversations cannot select an agent")
        if self.mode == "agent" and self.model_id is not None:
            raise ValueError("Agent conversations choose their persisted model")
        return self


class ConversationCreateRequest(ConversationSelection):
    title: str | None = Field(default=None, max_length=160)
    context: ConversationContext


class ConversationRenameRequest(StrictModel):
    title: str = Field(min_length=1, max_length=160)


class ConversationMessage(StrictModel):
    id: str = Field(min_length=1, max_length=100)
    role: Literal["user", "assistant"]
    parts: list[dict[str, Any]] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def bounded_parts(self):
        if len(json.dumps(self.model_dump(), separators=(",", ":"), default=str)) > 64 * 1024:
            raise ValueError("Conversation message is too large")
        return self


class ConversationSaveRequest(ConversationSelection):
    context: ConversationContext
    messages: list[ConversationMessage] = Field(min_length=1, max_length=60)

    @model_validator(mode="after")
    def bounded_transcript(self):
        if len(json.dumps(self.model_dump(), separators=(",", ":"), default=str)) > 256 * 1024:
            raise ValueError("Conversation is too large")
        return self


class ConversationOwner(StrictModel):
    id: UUID
    email: str


class ConversationSummary(StrictModel):
    id: UUID
    title: str
    mode: ConversationMode
    model_id: UUID | None
    agent_id: UUID | None
    cluster: str
    namespace: str | None
    created_at: datetime
    updated_at: datetime
    owner: ConversationOwner | None = None


class ConversationPartItem(StrictModel):
    id: UUID
    sequence: int
    role: Literal["user", "assistant"]
    part_type: str
    payload: dict[str, Any]
    proposal_id: UUID | None
    created_at: datetime


class ConversationDetail(ConversationSummary):
    resource: str | None
    name: str | None
    release: str | None
    parts: list[ConversationPartItem]


class ConversationListResponse(StrictModel):
    conversations: list[ConversationSummary]
    total: int


class ConversationRetentionResponse(StrictModel):
    retention_days: int


class ConversationPurgeResponse(StrictModel):
    deleted: int
    cutoff: datetime
    retention_days: int
