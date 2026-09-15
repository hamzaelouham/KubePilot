import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ResourceType = Literal[
    "pods", "deployments", "stateful-sets", "daemon-sets", "services", "nodes",
    "namespaces", "replica-sets", "replication-controllers", "jobs", "cron-jobs",
    "persistent-volumes", "persistent-volume-claims", "ingresses", "configmaps", "secrets",
]
Action = Literal["scale", "restart", "delete", "install", "upgrade", "rollback", "uninstall"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class InferenceMessage(StrictModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | list[dict[str, Any]] | None
    name: str | None = Field(default=None, max_length=128)
    tool_calls: list[dict[str, Any]] | None = Field(default=None, max_length=64)
    tool_call_id: str | None = Field(default=None, max_length=256)

    @model_validator(mode="after")
    def role_fields(self):
        if self.role == "tool" and not self.tool_call_id:
            raise ValueError("Tool messages require tool_call_id")
        if self.role != "assistant" and self.tool_calls is not None:
            raise ValueError("Only assistant messages may contain tool calls")
        return self

    @model_validator(mode="after")
    def bounded_content(self):
        if len(json.dumps(self.model_dump(), separators=(",", ":"))) > 64 * 1024:
            raise ValueError("Message content is too large")
        return self


class InferenceFunction(StrictModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=4096)
    parameters: dict[str, Any]
    strict: bool | None = None

    @model_validator(mode="after")
    def bounded_parameters(self):
        if len(json.dumps(self.parameters, separators=(",", ":"))) > 32 * 1024:
            raise ValueError("Tool parameters are too large")
        return self


class InferenceTool(StrictModel):
    type: Literal["function"]
    function: InferenceFunction


class ChatCompletionsRequest(StrictModel):
    model: Literal["default"]
    messages: list[InferenceMessage] = Field(min_length=1, max_length=60)
    stream: Literal[True]
    stream_options: dict[str, bool] | None = None
    tools: list[InferenceTool] | None = Field(default=None, max_length=32)
    tool_choice: Literal["auto", "none", "required"] | dict[str, Any] | None = None
    max_tokens: int | None = Field(default=None, ge=1, le=16_384)
    max_completion_tokens: int | None = Field(default=None, ge=1, le=16_384)
    temperature: float | None = Field(default=None, ge=0, le=2)
    top_p: float | None = Field(default=None, ge=0, le=1)
    frequency_penalty: float | None = Field(default=None, ge=-2, le=2)
    presence_penalty: float | None = Field(default=None, ge=-2, le=2)
    stop: str | list[str] | None = None
    seed: int | None = None
    response_format: dict[str, Any] | None = None
    parallel_tool_calls: bool | None = None

    @model_validator(mode="after")
    def bounded_optional_values(self):
        if isinstance(self.stop, str) and len(self.stop) > 1024:
            raise ValueError("Stop sequence is too large")
        if isinstance(self.stop, list) and (len(self.stop) > 8 or any(len(value) > 1024 for value in self.stop)):
            raise ValueError("Stop sequences are too large")
        for value in (self.tool_choice, self.response_format, self.stream_options):
            if value is not None and len(json.dumps(value, separators=(",", ":"))) > 16 * 1024:
                raise ValueError("Inference option is too large")
        return self


class Observation(StrictModel):
    cluster: str = Field(min_length=1, max_length=253)
    namespace: str | None = Field(default=None, max_length=63, pattern=r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
    resource_type: ResourceType = "pods"
    name: str | None = Field(default=None, max_length=253, pattern=r"^[a-z0-9]([-a-z0-9.]*[a-z0-9])?$")
    container: str | None = Field(default=None, max_length=63, pattern=r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
    previous: bool = False
    warnings_only: bool = False


class Proposal(StrictModel):
    action: Action
    cluster: str = Field(min_length=1, max_length=253)
    namespace: str = Field(min_length=1, max_length=63, pattern=r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
    name: str = Field(min_length=1, max_length=253, pattern=r"^[a-z0-9]([-a-z0-9.]*[a-z0-9])?$")
    resource_type: Literal["pods", "deployments", "stateful-sets", "daemon-sets", "services", "jobs", "cron-jobs"] = "deployments"
    replicas: int | None = Field(default=None, ge=0, le=10000)
    repository_id: str | None = Field(default=None, max_length=36)
    chart_name: str | None = Field(default=None, max_length=253)
    version: str | None = Field(default=None, max_length=64)
    package_id: str | None = Field(default=None, max_length=253)
    package_name: str | None = Field(default=None, max_length=253)
    repository_name: str | None = Field(default=None, max_length=63)

    @model_validator(mode="after")
    def action_fields(self):
        required = {
            "scale": {"replicas"}, "restart": set(), "delete": set(),
            "install": {"package_id", "package_name", "repository_name", "version"},
            "upgrade": {"repository_id", "chart_name", "version"},
            "rollback": set(), "uninstall": set(),
        }[self.action]
        optional_fields = {"replicas", "repository_id", "chart_name", "version", "package_id", "package_name", "repository_name"}
        present = {key for key in optional_fields if getattr(self, key) is not None}
        if present != required or any(getattr(self, key) == "" for key in required):
            raise ValueError("Supply exactly the required parameters for this action")
        if self.action in {"scale", "restart"} and self.resource_type != "deployments":
            raise ValueError("Scale and restart support Deployments")
        return self


class Decision(StrictModel):
    approved: bool
    confirm_name: str = Field(max_length=253)
    cluster: str = Field(min_length=1, max_length=253)


class ReadTool(StrictModel):
    tool: Literal["listClusters", "listNamespaces", "getResourceUsage", "listHelmReleases", "getHelmHistory", "listRepositories", "searchPackages", "getPackage", "getJobStatus"]
    cluster: str = Field(min_length=1, max_length=253)
    namespace: str | None = Field(default=None, max_length=63)
    name: str | None = Field(default=None, max_length=253)
    query: str | None = Field(default=None, max_length=120)
    repository_name: str | None = Field(default=None, max_length=63)
    package_name: str | None = Field(default=None, max_length=253)
