from dataclasses import dataclass
from typing import Any, Callable, Literal
import re

import yaml

from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from urllib3.exceptions import HTTPError

from app.core.config import Settings


class ClusterClientError(RuntimeError):
    pass


class ClusterUnavailableError(ClusterClientError):
    pass


class ClusterForbiddenError(ClusterClientError):
    pass


class ClusterMetricsError(ClusterClientError):
    pass


class ResourceNotFoundError(ClusterClientError):
    pass


@dataclass(frozen=True)
class ResourceSummary:
    cluster: str
    namespace: str | None
    kind: str
    name: str
    status: str
    health: str


@dataclass(frozen=True)
class NodeMetric:
    name: str
    cpu_usage_millicores: float
    cpu_allocatable_millicores: float | None
    memory_usage_bytes: float
    memory_allocatable_bytes: float | None
    storage_capacity_bytes: float | None
    storage_allocatable_bytes: float | None


@dataclass(frozen=True)
class PodMetric:
    namespace: str
    name: str
    cpu_usage_millicores: float
    memory_usage_bytes: float


@dataclass(frozen=True)
class MetricsDataSet:
    nodes: list[NodeMetric]
    pods: list[PodMetric]


@dataclass(frozen=True)
class StorageMetricsItem:
    name: str
    kind: str
    capacity_bytes: float | None
    utilization: str | None


@dataclass(frozen=True)
class ClusterClient:
    cluster_name: str
    core: Any
    apps: Any
    batch: Any = None
    rbac: Any = None
    storage: Any = None
    metrics_api: Any = None

    def namespaces(self) -> list[tuple[str, str]]:
        try:
            return [(item.metadata.name, item.status.phase or "unknown") for item in self.core.list_namespace().items]
        except Exception as error:
            raise classify_kubernetes_error(error) from error

    def resources(self, resource_type: str, namespace: str | None) -> list[ResourceSummary]:
        namespaced_methods: dict[str, tuple[Any, str, str, str]] = {
            "pods": (self.core, "list_namespaced_pod", "list_pod_for_all_namespaces", "Pod"),
            "services": (self.core, "list_namespaced_service", "list_service_for_all_namespaces", "Service"),
            "endpoints": (self.core, "list_namespaced_endpoints", "list_endpoints_for_all_namespaces", "Endpoints"),
            "deployments": (self.apps, "list_namespaced_deployment", "list_deployment_for_all_namespaces", "Deployment"),
            "replica-sets": (self.apps, "list_namespaced_replica_set", "list_replica_set_for_all_namespaces", "ReplicaSet"),
            "daemon-sets": (self.apps, "list_namespaced_daemon_set", "list_daemon_set_for_all_namespaces", "DaemonSet"),
            "stateful-sets": (self.apps, "list_namespaced_stateful_set", "list_stateful_set_for_all_namespaces", "StatefulSet"),
            "jobs": (self.batch, "list_namespaced_job", "list_job_for_all_namespaces", "Job"),
            "cron-jobs": (self.batch, "list_namespaced_cron_job", "list_cron_job_for_all_namespaces", "CronJob"),
            "replication-controllers": (self.core, "list_namespaced_replication_controller", "list_replication_controller_for_all_namespaces", "ReplicationController"),
            "persistent-volume-claims": (self.core, "list_namespaced_persistent_volume_claim", "list_persistent_volume_claim_for_all_namespaces", "PersistentVolumeClaim"),
        }
        cluster_scoped_methods: dict[str, tuple[Any, str, str, str]] = {
            "nodes": (self.core, "list_node", "Node", "condition"),
            "persistent-volumes": (self.core, "list_persistent_volume", "PersistentVolume", "phase"),
            "cluster-roles": (self.rbac, "list_cluster_role", "ClusterRole", "none"),
            "storage-classes": (self.storage, "list_storage_class", "StorageClass", "none"),
        }
        try:
            if resource_type in cluster_scoped_methods:
                api, method_name, kind, status_kind = cluster_scoped_methods[resource_type]
                items = getattr(api, method_name)().items
                return [
                    ResourceSummary(self.cluster_name, None, kind, item.metadata.name, _summary_status(item, status_kind), _health_status(item, kind))
                    for item in items
                ]
            api, namespaced_method, all_namespace_method, kind = namespaced_methods[resource_type]
            items = getattr(api, namespaced_method)(namespace).items if namespace else getattr(api, all_namespace_method)().items
            return [
                ResourceSummary(
                    self.cluster_name,
                    item.metadata.namespace,
                    kind,
                    item.metadata.name,
                    str(getattr(item.status, "phase", None) or getattr(item.status, "available_replicas", None) or "Unknown"),
                    _health_status(item, kind),
                )
                for item in items
            ]
        except Exception as error:
            raise classify_kubernetes_error(error) from error

    def detail(self, resource_type: str, name: str, namespace: str | None) -> dict[str, Any]:
        methods: dict[str, tuple[Any, str, str]] = {
            "pods": (self.core, "read_namespaced_pod", "Pod"),
            "services": (self.core, "read_namespaced_service", "Service"),
            "deployments": (self.apps, "read_namespaced_deployment", "Deployment"),
            "replica-sets": (self.apps, "read_namespaced_replica_set", "ReplicaSet"),
            "daemon-sets": (self.apps, "read_namespaced_daemon_set", "DaemonSet"),
            "stateful-sets": (self.apps, "read_namespaced_stateful_set", "StatefulSet"),
            "jobs": (self.batch, "read_namespaced_job", "Job"),
            "cron-jobs": (self.batch, "read_namespaced_cron_job", "CronJob"),
            "replication-controllers": (self.core, "read_namespaced_replication_controller", "ReplicationController"),
            "nodes": (self.core, "read_node", "Node"),
        }
        try:
            api, method_name, kind = methods[resource_type]
            method = getattr(api, method_name)
            item = method(name) if resource_type == "nodes" else method(name, namespace)
            raw = item.to_dict() if hasattr(item, "to_dict") else item
            status = getattr(item.status, "phase", None) or getattr(item.status, "conditions", None) or "Unknown"
            if isinstance(status, list):
                status = status[-1].type if status else "Unknown"
            return {
                "cluster": self.cluster_name,
                "resource_type": resource_type,
                "name": item.metadata.name,
                "namespace": getattr(item.metadata, "namespace", None),
                "kind": kind,
                "status": str(status),
                "metadata": _safe_metadata(getattr(item.metadata, "labels", None), getattr(item.metadata, "annotations", None)),
                "raw": raw,
            }
        except ApiException as error:
            if error.status == 404:
                raise ResourceNotFoundError("Kubernetes resource was not found") from error
            raise classify_kubernetes_error(error) from error
        except Exception as error:
            raise classify_kubernetes_error(error) from error

    def yaml(self, resource_type: str, name: str, namespace: str | None) -> tuple[str, bool]:
        detail = self.detail(resource_type, name, namespace)
        content = yaml.safe_dump(_redact(detail["raw"]), sort_keys=True)
        return _bounded(content, 100_000)

    def logs(self, name: str, namespace: str | None) -> tuple[list[str], bool, str | None]:
        if namespace is None:
            raise ResourceNotFoundError("Pod logs require a namespace")
        try:
            content = self.core.read_namespaced_pod_log(name, namespace, timestamps=True, tail_lines=500)
            bounded_content, truncated = _bounded(content, 100_000)
            return bounded_content.splitlines(), truncated, None
        except ApiException as error:
            if error.status == 404:
                raise ResourceNotFoundError("Kubernetes resource was not found") from error
            raise classify_kubernetes_error(error) from error
        except Exception as error:
            raise classify_kubernetes_error(error) from error

    def events(self, name: str, namespace: str | None) -> tuple[list[dict[str, str | None]], bool]:
        if namespace is None:
            return [], False
        try:
            result = self.core.list_namespaced_event(namespace, field_selector=f"involvedObject.name={name}", limit=100)
            items = [
                {
                    "type": event.type or "Normal",
                    "reason": event.reason or "Unknown",
                    "message": event.message or "",
                    "source": getattr(event.source, "component", None) or "Unknown",
                    "created_at": str(event.last_timestamp or event.event_time or "") or None,
                }
                for event in result.items
            ]
            return items, len(items) >= 100
        except ApiException as error:
            raise classify_kubernetes_error(error) from error
        except Exception as error:
            raise classify_kubernetes_error(error) from error

    def metrics(self) -> MetricsDataSet:
        if self.metrics_api is None:
            raise ClusterMetricsError("Metrics API provider is not configured")
        try:
            return MetricsDataSet(
                nodes=self._node_metrics(),
                pods=self._pod_metrics(),
            )
        except ClusterMetricsError:
            raise
        except Exception as error:
            raise ClusterMetricsError("Metrics API data is unavailable") from error

    def _node_metrics(self) -> list[NodeMetric]:
        node_objects = {item.metadata.name: item for item in self.core.list_node().items or []}
        usage = self._list_metrics("nodes")
        metrics_by_name = {entry.get("metadata", {}).get("name"): _entry_usage(entry) for entry in usage}
        result: list[NodeMetric] = []
        names = list(metrics_by_name) if metrics_by_name else list(node_objects)
        for name in names:
            node = node_objects.get(name)
            usage_value = metrics_by_name.get(name) or {}
            result.append(
                NodeMetric(
                    name=name,
                    cpu_usage_millicores=usage_value.get("cpu", 0.0),
                    memory_usage_bytes=usage_value.get("memory", 0.0),
                    cpu_allocatable_millicores=_node_quantity(node, "allocatable", "cpu", 1000.0),
                    memory_allocatable_bytes=_node_quantity(node, "allocatable", "memory"),
                    storage_capacity_bytes=_node_quantity(node, "capacity", "ephemeral-storage"),
                    storage_allocatable_bytes=_node_quantity(node, "allocatable", "ephemeral-storage"),
                )
            )
        return result

    def _pod_metrics(self) -> list[PodMetric]:
        usage = self._list_metrics("pods")
        return [
            PodMetric(
                namespace=entry.get("metadata", {}).get("namespace") or "default",
                name=entry.get("metadata", {}).get("name") or "unknown",
                cpu_usage_millicores=_pod_usage(entry).get("cpu", 0.0),
                memory_usage_bytes=_pod_usage(entry).get("memory", 0.0),
            )
            for entry in usage
        ]

    def _list_metrics(self, plural: str) -> list[dict[str, Any]]:
        try:
            result = self.metrics_api.list_cluster_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                plural=plural,
            )
        except ApiException as error:
            if error.status in (401, 403, 404, 503):
                raise ClusterMetricsError("Metrics API provider is unavailable") from error
            raise ClusterMetricsError("Metrics API request failed") from error
        if isinstance(result, dict):
            return result.get("items") or []
        return getattr(result, "items", None) or []

    def storage_metrics(self) -> list[StorageMetricsItem]:
        try:
            pv_items = getattr(self.core.list_persistent_volume(), "items", None) or []
            pvc_items = getattr(self.core.list_persistent_volume_claim_for_all_namespaces(), "items", None) or []
        except Exception as error:
            raise classify_kubernetes_error(error) from error
        result: list[StorageMetricsItem] = []
        for pv in pv_items:
            capacity = _pv_quantity(pv, "capacity")
            result.append(StorageMetricsItem(name=pv.metadata.name, kind="PersistentVolume", capacity_bytes=capacity, utilization=None))
        for pvc in pvc_items:
            capacity = _pvc_quantity(pvc, "requests")
            result.append(StorageMetricsItem(name=pvc.metadata.name, kind="PersistentVolumeClaim", capacity_bytes=capacity, utilization=None))
        return result


def _pv_quantity(pv: Any, field: str) -> float | None:
    spec = getattr(pv, "spec", None)
    resources = getattr(spec, field, None) if spec is not None else None
    value = getattr(resources, "storage", None) if resources is not None else None
    if value is None:
        return None
    return round(_parse_quantity(str(value)))


def _pvc_quantity(pvc: Any, field: str) -> float | None:
    spec = getattr(pvc, "spec", None)
    resources = getattr(spec, "resources", None) if spec is not None else None
    values = getattr(resources, field, None) if resources is not None else None
    value = getattr(values, "storage", None) if values is not None else None
    if value is None:
        return None
    return round(_parse_quantity(str(value)))


def create_cluster_client(
    settings: Settings,
    loader: Callable[[], None] = config.load_incluster_config,
    kubeconfig_content: str | None = None,
    cluster_name: str | None = None,
) -> ClusterClient:
    try:
        if kubeconfig_content is not None:
            config.load_kube_config_from_dict(yaml.safe_load(kubeconfig_content))
        else:
            loader()
        return ClusterClient(
            cluster_name or settings.cluster_name,
            client.CoreV1Api(),
            client.AppsV1Api(),
            client.BatchV1Api(),
            client.RbacAuthorizationV1Api(),
            client.StorageV1Api(),
            metrics_api=client.CustomObjectsApi(),
        )
    except (config.ConfigException, yaml.YAMLError, HTTPError, OSError) as error:
        raise ClusterUnavailableError(
            f"Kubernetes ServiceAccount configuration is unavailable: {error}"
        ) from error


def _kubernetes_error_reason(error: Exception) -> str:
    if isinstance(error, ApiException):
        detail = error.reason or error.body or ""
        if isinstance(detail, bytes):
            detail = detail.decode("utf-8", errors="replace")
        detail = str(detail).strip()
        return f"HTTP {error.status}{': ' + detail if detail else ''}"
    reason = getattr(error, "reason", None)
    if reason:
        return str(reason)
    return str(error) or type(error).__name__


def classify_kubernetes_error(error: Exception) -> ClusterClientError:
    if isinstance(error, ApiException) and error.status == 403:
        return ClusterForbiddenError("Kubernetes RBAC denied the requested operation")
    if isinstance(error, (ApiException, HTTPError, TimeoutError, OSError)):
        return ClusterUnavailableError(
            f"Kubernetes cluster is unavailable: {_kubernetes_error_reason(error)}"
        )
    return ClusterClientError("Kubernetes request failed")


def _entry_usage(entry: dict[str, Any]) -> dict[str, float]:
    usage = entry.get("usage") or {}
    cpu = _cpu_millicores(str(usage.get("cpu", "")))
    memory = _memory_bytes(str(usage.get("memory", "")))
    return {"cpu": cpu, "memory": memory}


def _pod_usage(entry: dict[str, Any]) -> dict[str, float]:
    containers = entry.get("containers") or []
    cpu = sum(_cpu_millicores(str(container.get("usage", {}).get("cpu", ""))) for container in containers)
    memory = sum(_memory_bytes(str(container.get("usage", {}).get("memory", ""))) for container in containers)
    if not containers and entry.get("usage"):
        fallback = _entry_usage(entry)
        return {"cpu": fallback.get("cpu", 0.0), "memory": fallback.get("memory", 0.0)}
    return {"cpu": cpu, "memory": memory}


def _node_quantity(
    node: Any, resource_field: str, resource_key: str, multiplier: float = 1.0
) -> float | None:
    status = getattr(node, "status", None)
    resources = getattr(status, resource_field, None) if status is not None else None
    value = getattr(resources, resource_key, None) if resources is not None else None
    if value is None:
        return None
    return round(_parse_quantity(str(value)) * multiplier)


def _cpu_millicores(value: str) -> float:
    if not value:
        return 0.0
    return round(_parse_quantity(value) * 1000.0)


def _memory_bytes(value: str) -> float:
    if not value:
        return 0.0
    return round(_parse_quantity(value))


def _parse_quantity(value: str) -> float:
    match = re.match(r"^([-+]?[0-9]*\.?[0-9]+)([a-zA-Z]*)$", value.strip())
    if not match:
        return 0.0
    number = float(match.group(1))
    suffix = match.group(2)
    if suffix in {"m", "n", "u"}:
        divisors = {"m": 1e3, "n": 1e9, "u": 1e6}
        return number / divisors[suffix]
    if suffix in {"Ki", "Mi", "Gi", "Ti", "Pi", "Ei"}:
        multipliers = {"Ki": 2**10, "Mi": 2**20, "Gi": 2**30, "Ti": 2**40, "Pi": 2**50, "Ei": 2**60}
        return number * multipliers[suffix]
    if suffix in {"k", "K", "M", "G", "T", "P", "E"}:
        multipliers = {"k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9, "T": 1e12, "P": 1e15, "E": 1e18}
        return number * multipliers[suffix]
    return number


def _summary_status(item: Any, status_kind: str) -> str:
    status = getattr(item, "status", None)
    if status_kind == "condition" and status is not None and getattr(status, "conditions", None):
        return status.conditions[-1].type
    if status_kind == "phase" and status is not None and getattr(status, "phase", None):
        return status.phase
    return "Unknown"


_HEALTH = Literal["healthy", "warning", "error", "unknown"]


def _health_status(item: Any, kind: str) -> str:
    status = getattr(item, "status", None)
    if kind == "Pod":
        return _pod_health(status)
    if kind in {"Deployment", "ReplicaSet", "StatefulSet", "DaemonSet", "Job"}:
        return _replicas_health(getattr(item, "spec", None), status)
    if kind == "Node":
        return _node_health(status)
    if kind == "PersistentVolume":
        return _pv_health(status)
    return "unknown"


def _pod_health(status: Any) -> str:
    phase = getattr(status, "phase", None)
    if phase != "Running":
        return "error"
    containers = getattr(status, "container_statuses", None) or []
    if not containers:
        return "healthy"
    for container in containers:
        if not getattr(container, "ready", False):
            return "warning"
        state = getattr(container, "state", None)
        if state is not None and getattr(state, "waiting", None) is not None:
            reason = (getattr(state.waiting, "reason", None) or "").lower()
            if reason in {"crashloopbackoff", "imagepullbackoff", "createcontainererror", "invalidimagename"}:
                return "error"
            return "warning"
    return "healthy"



def _replicas_health(spec: Any, status: Any) -> str:
    desired = getattr(spec, "replicas", None) if spec is not None else None
    if desired is None or desired <= 0:
        return "unknown"
    ready = getattr(status, "ready_replicas", 0) or 0
    available = getattr(status, "available_replicas", None)
    unavailable = getattr(status, "unavailable_replicas", 0) or 0
    all_ready = ready >= desired and (available is None or available == desired) and unavailable == 0
    if all_ready:
        return "healthy"
    if ready > 0:
        return "warning"
    return "error"


def _node_health(status: Any) -> str:
    conditions = getattr(status, "conditions", None) or []
    for condition in reversed(conditions):
        if getattr(condition, "type", None) == "Ready":
            ready = getattr(condition, "status", "")
            if ready == "True":
                return "healthy"
            if ready == "False":
                return "error"
            if ready == "Unknown":
                return "warning"
    return "unknown"


def _pv_health(status: Any) -> str:
    phase = getattr(status, "phase", None)
    if phase in {"Bound", "Available"}:
        return "healthy"
    if phase in {"Released", "Failed"}:
        return "error"
    if phase == "Pending":
        return "warning"
    return "unknown"


def _safe_metadata(labels: dict[str, str] | None, annotations: dict[str, str] | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in {**(labels or {}), **(annotations or {})}.items():
        if re.search(r"token|secret|password|credential|kubeconfig|authorization", key, re.I):
            result[key] = "[REDACTED]"
        else:
            result[key] = value
    return result


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if re.search(r"token|secret|password|credential|kubeconfig|authorization", key, re.I) else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _bounded(content: str, limit: int) -> tuple[str, bool]:
    return content[:limit], len(content) > limit
