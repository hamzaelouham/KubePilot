from pydantic import BaseModel, ConfigDict


class NodeMetricItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    cpu_usage_millicores: float
    cpu_allocatable_millicores: float | None = None
    memory_usage_bytes: float
    memory_allocatable_bytes: float | None = None
    storage_capacity_bytes: float | None = None
    storage_allocatable_bytes: float | None = None


class WorkloadMetricItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    namespace: str
    name: str
    kind: str
    cpu_usage_millicores: float
    memory_usage_bytes: float


class NamespaceMetricSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    namespace: str
    cpu_usage_millicores: float
    memory_usage_bytes: float
    pod_count: int


class NodesMetricsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available: bool
    reason: str | None = None
    items: list[NodeMetricItem]


class NamespaceMetricsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available: bool
    reason: str | None = None
    workloads: list[WorkloadMetricItem]
    summary: NamespaceMetricSummary | None = None


class MetricsSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available: bool
    reason: str | None = None
    namespaces: list[NamespaceMetricSummary]


class StorageMetricsItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    kind: str
    capacity_bytes: float | None = None
    utilization: str | None = None


class StorageMetricsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available: bool
    reason: str | None = None
    items: list[StorageMetricsItem]
