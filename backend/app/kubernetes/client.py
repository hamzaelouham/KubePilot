from dataclasses import dataclass
from typing import Any, Callable

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

    def namespaces(self) -> list[tuple[str, str]]:
        try:
            return [(item.metadata.name, item.status.phase or "unknown") for item in self.core.list_namespace().items]
        except Exception as error:
            raise classify_kubernetes_error(error) from error

    def resources(self, resource_type: str, namespace: str | None) -> list[ResourceSummary]:
        methods: dict[str, tuple[Any, str, str]] = {
            "pods": (self.core, "list_pod_for_all_namespaces", "Pod"),
            "services": (self.core, "list_service_for_all_namespaces", "Service"),
            "endpoints": (self.core, "list_endpoints_for_all_namespaces", "Endpoints"),
            "deployments": (self.apps, "list_deployment_for_all_namespaces", "Deployment"),
        }
        try:
            if resource_type == "nodes":
                items = self.core.list_node().items
                return [ResourceSummary(self.cluster_name, None, "Node", item.metadata.name, item.status.conditions[-1].type if item.status.conditions else "Unknown") for item in items]
            api, all_namespace_method, kind = methods[resource_type]
            if namespace:
                namespaced_method = getattr(api, all_namespace_method.replace("_for_all_namespaces", "_for_namespace"))
                items = namespaced_method(namespace).items
            else:
                items = getattr(api, all_namespace_method)().items
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


def create_cluster_client(settings: Settings, loader: Callable[[], None] = config.load_incluster_config) -> ClusterClient:
    try:
        loader()
        return ClusterClient(settings.cluster_name, client.CoreV1Api(), client.AppsV1Api())
    except (config.ConfigException, HTTPError, OSError) as error:
        raise ClusterUnavailableError("Kubernetes ServiceAccount configuration is unavailable") from error


def classify_kubernetes_error(error: Exception) -> ClusterClientError:
    if isinstance(error, ApiException) and error.status == 403:
        return ClusterForbiddenError("Kubernetes RBAC denied the requested operation")
    if isinstance(error, (ApiException, HTTPError, TimeoutError, OSError)):
        return ClusterUnavailableError("Kubernetes cluster is unavailable")
    return ClusterClientError("Kubernetes request failed")
