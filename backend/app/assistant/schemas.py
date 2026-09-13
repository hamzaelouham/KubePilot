from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ResourceType = Literal[
    "pods", "deployments", "stateful-sets", "daemon-sets", "services", "nodes",
    "namespaces", "replica-sets", "replication-controllers", "jobs", "cron-jobs",
    "persistent-volumes", "persistent-volume-claims", "ingresses", "configmaps", "secrets",
]
Action = Literal["scale", "restart", "delete", "install", "upgrade", "rollback", "uninstall"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


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
