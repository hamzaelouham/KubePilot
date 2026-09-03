from dataclasses import dataclass
from typing import Any, Callable
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


class ResourceNotFoundError(ClusterClientError):
    pass


@dataclass(frozen=True)
class ResourceSummary:
    cluster: str
    namespace: str | None
    kind: str
    name: str
    status: str


@dataclass(frozen=True)
class ClusterClient:
    cluster_name: str
    core: Any
    apps: Any
    batch: Any = None
    rbac: Any = None
    storage: Any = None

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
                    ResourceSummary(self.cluster_name, None, kind, item.metadata.name, _summary_status(item, status_kind))
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


def create_cluster_client(settings: Settings, loader: Callable[[], None] = config.load_incluster_config) -> ClusterClient:
    try:
        loader()
        return ClusterClient(
            settings.cluster_name,
            client.CoreV1Api(),
            client.AppsV1Api(),
            client.BatchV1Api(),
            client.RbacAuthorizationV1Api(),
            client.StorageV1Api(),
        )
    except (config.ConfigException, HTTPError, OSError) as error:
        raise ClusterUnavailableError("Kubernetes ServiceAccount configuration is unavailable") from error


def classify_kubernetes_error(error: Exception) -> ClusterClientError:
    if isinstance(error, ApiException) and error.status == 403:
        return ClusterForbiddenError("Kubernetes RBAC denied the requested operation")
    if isinstance(error, (ApiException, HTTPError, TimeoutError, OSError)):
        return ClusterUnavailableError("Kubernetes cluster is unavailable")
    return ClusterClientError("Kubernetes request failed")


def _summary_status(item: Any, status_kind: str) -> str:
    status = getattr(item, "status", None)
    if status_kind == "condition" and status is not None and getattr(status, "conditions", None):
        return status.conditions[-1].type
    if status_kind == "phase" and status is not None and getattr(status, "phase", None):
        return status.phase
    return "Unknown"


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
