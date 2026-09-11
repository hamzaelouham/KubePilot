"""Allowlisted resource operations. Cluster credentials never come from manifests."""

from dataclasses import dataclass
from contextlib import contextmanager
import json
import re
from typing import Any

import yaml
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from urllib3.exceptions import HTTPError


class ResourceManagementError(RuntimeError):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ResourceKind:
    api_version: str
    kind: str
    api: str
    singular: str
    namespaced: bool = True


RESOURCE_KINDS = {
    "pods": ResourceKind("v1", "Pod", "core", "pod"),
    "deployments": ResourceKind("apps/v1", "Deployment", "apps", "deployment"),
    "namespaces": ResourceKind("v1", "Namespace", "core", "namespace", False),
    "services": ResourceKind("v1", "Service", "core", "service"),
    "stateful-sets": ResourceKind("apps/v1", "StatefulSet", "apps", "stateful_set"),
    "daemon-sets": ResourceKind("apps/v1", "DaemonSet", "apps", "daemon_set"),
    "jobs": ResourceKind("batch/v1", "Job", "batch", "job"),
    "cron-jobs": ResourceKind("batch/v1", "CronJob", "batch", "cron_job"),
}
_LABEL = r"[a-z0-9](?:[-a-z0-9]*[a-z0-9])?"
_SUBDOMAIN = rf"{_LABEL}(?:\.{_LABEL})*"
_SERVER_METADATA = {
    "uid", "resourceVersion", "creationTimestamp", "deletionTimestamp", "managedFields",
}


def resource_kind(resource_type: str) -> ResourceKind:
    kind = RESOURCE_KINDS.get(resource_type)
    if kind is None:
        raise ResourceManagementError(422, "invalid_resource_type", "Unsupported resource type")
    return kind


def validate_name(name: Any, *, label: bool = False) -> str:
    if (
        not isinstance(name, str)
        or len(name) > (63 if label else 253)
        or not re.fullmatch(_LABEL if label else _SUBDOMAIN, name)
    ):
        raise ResourceManagementError(422, "invalid_resource_identity", "A valid Kubernetes name is required")
    return name


def validate_scope(kind: ResourceKind, namespace: str | None, *, mutation: bool) -> None:
    if not kind.namespaced:
        if namespace is not None:
            raise ResourceManagementError(422, "invalid_namespace_scope", "Namespaces are cluster-scoped")
    elif namespace is not None:
        validate_name(namespace, label=True)
    elif mutation:
        raise ResourceManagementError(422, "invalid_namespace_scope", "Select a namespace for this operation")


def protection_reason(
    kind: ResourceKind, namespace: str | None, name: str, host_namespace: str, *, deleting: bool,
) -> str | None:
    target = namespace if kind.namespaced else name
    if target in {"kube-system", "kube-public", "kube-node-lease", host_namespace}:
        return "This namespace is protected. Resource changes are not allowed."
    if deleting and not kind.namespaced and name == "default":
        return "The default namespace cannot be deleted."
    return None


def ensure_unprotected(
    kind: ResourceKind, namespace: str | None, name: str, host_namespace: str, *, deleting: bool,
) -> None:
    reason = protection_reason(kind, namespace, name, host_namespace, deleting=deleting)
    if reason:
        raise ResourceManagementError(422, "namespace_protected", reason)


class _ManifestLoader(yaml.SafeLoader):
    def compose_node(self, parent, index):
        if self.check_event(yaml.AliasEvent):
            raise yaml.YAMLError("Aliases are not supported")
        return super().compose_node(parent, index)

    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise yaml.YAMLError("Mapping keys must be unique strings")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def parse_manifest(content: str, kind: ResourceKind, namespace: str | None) -> dict[str, Any]:
    validate_scope(kind, namespace, mutation=True)
    try:
        manifest = yaml.load(content, Loader=_ManifestLoader)
        json.dumps(manifest, allow_nan=False)
    except (yaml.YAMLError, TypeError, ValueError, RecursionError) as error:
        mark = getattr(error, "problem_mark", None)
        location = f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
        raise ResourceManagementError(
            422, "invalid_manifest",
            f"Invalid YAML{location}. Use one object with unique string keys and no aliases or custom tags.",
        ) from None
    if not isinstance(manifest, dict):
        raise ResourceManagementError(422, "invalid_manifest", "YAML must contain one resource object")
    if manifest.get("kind") != kind.kind or manifest.get("apiVersion") != kind.api_version:
        raise ResourceManagementError(422, "invalid_manifest", "YAML kind and apiVersion must match the selected resource type")
    metadata = manifest.get("metadata")
    if not isinstance(metadata, dict):
        raise ResourceManagementError(422, "invalid_manifest", "metadata must be an object with an explicit name")
    validate_name(metadata.get("name"), label=kind.kind in {"Namespace", "Service"})
    if "generateName" in metadata or _SERVER_METADATA.intersection(metadata) or "status" in manifest:
        raise ResourceManagementError(422, "invalid_manifest", "Remove server-managed fields, status, and generateName before creating a resource")
    if kind.namespaced:
        if "namespace" in metadata and metadata["namespace"] != namespace:
            raise ResourceManagementError(422, "invalid_namespace_scope", "YAML namespace must match the selected namespace")
        metadata["namespace"] = namespace
    elif "namespace" in metadata:
        raise ResourceManagementError(422, "invalid_namespace_scope", "Namespace objects must not have metadata.namespace")
    return manifest


def _translate_error(error: Exception, operation: str) -> ResourceManagementError:
    if isinstance(error, ApiException) and error.status:
        if error.status in (401, 403):
            return ResourceManagementError(403, "cluster_forbidden", "Kubernetes RBAC denied this operation")
        if error.status == 404:
            if operation == "create":
                return ResourceManagementError(422, "invalid_namespace_scope", "The target namespace or resource API was not found")
            return ResourceManagementError(404, "resource_not_found", "The resource was not found. Refresh the inventory.")
        if error.status == 409:
            return ResourceManagementError(409, "resource_conflict", "The resource already exists or has been replaced. Refresh and review it again.")
        if error.status in (400, 422):
            return ResourceManagementError(422, "invalid_manifest", "Kubernetes rejected this resource. Check the manifest, resource fields, and namespace.")
        if error.status < 500:
            return ResourceManagementError(502, "cluster_error", "Kubernetes could not complete the request")
    if operation != "read":
        return ResourceManagementError(504, "operation_outcome_unknown", "The operation outcome is unknown. Refresh the inventory before trying again.")
    return ResourceManagementError(503, "cluster_unavailable", "The selected cluster is unavailable")


class ManagementClient:
    """One explicit ApiClient for all API groups in an operation; no global defaults."""

    def __init__(self, api_client: client.ApiClient):
        self.apis = {
            "core": client.CoreV1Api(api_client),
            "apps": client.AppsV1Api(api_client),
            "batch": client.BatchV1Api(api_client),
        }

    def _call(self, kind: ResourceKind, method: str, operation: str, **kwargs):
        try:
            return getattr(self.apis[kind.api], method)(_request_timeout=(5, 30), **kwargs)
        except (ApiException, HTTPError, OSError, TimeoutError) as error:
            raise _translate_error(error, operation) from None

    def resources(self, kind: ResourceKind, namespace: str | None) -> list[Any]:
        if kind.namespaced and namespace is not None:
            method = f"list_namespaced_{kind.singular}"
            arguments = {"namespace": namespace}
        else:
            method = f"list_{kind.singular}" + ("_for_all_namespaces" if kind.namespaced else "")
            arguments = {}
        items = []
        seen_tokens = set()
        while True:
            response = self._call(kind, method, "read", **arguments)
            items.extend(response.items)
            token = getattr(getattr(response, "metadata", None), "_continue", None)
            if not token:
                return items
            if token in seen_tokens:
                raise ResourceManagementError(502, "cluster_error", "Kubernetes returned an invalid inventory continuation")
            seen_tokens.add(token)
            arguments["_continue"] = token

    def read(self, kind: ResourceKind, namespace: str | None, name: str):
        arguments = {"name": name}
        if kind.namespaced:
            arguments["namespace"] = namespace
        return self._call(kind, f"read_{'namespaced_' if kind.namespaced else ''}{kind.singular}", "read", **arguments)

    def create(self, kind: ResourceKind, namespace: str | None, manifest: dict[str, Any]):
        arguments = {"body": manifest, "field_validation": "Strict"}
        if kind.namespaced:
            arguments["namespace"] = namespace
        return self._call(kind, f"create_{'namespaced_' if kind.namespaced else ''}{kind.singular}", "create", **arguments)

    def delete(self, kind: ResourceKind, namespace: str | None, name: str, uid: str):
        arguments = {
            "name": name,
            "body": client.V1DeleteOptions(preconditions=client.V1Preconditions(uid=uid)),
        }
        if kind.namespaced:
            arguments["namespace"] = namespace
        return self._call(kind, f"delete_{'namespaced_' if kind.namespaced else ''}{kind.singular}", "delete", **arguments)


@contextmanager
def management_client(cluster):
    configuration = client.Configuration()
    try:
        if cluster.kubeconfig_content is not None:
            config.load_kube_config_from_dict(
                yaml.safe_load(cluster.kubeconfig_content),
                client_configuration=configuration,
                persist_config=False,
            )
        elif cluster.endpoint == "in-cluster":
            config.load_incluster_config(client_configuration=configuration)
        else:
            raise ResourceManagementError(503, "cluster_unavailable", "The selected cluster has no Kubernetes credentials")
    except (config.ConfigException, yaml.YAMLError, HTTPError, OSError, ValueError, TypeError):
        raise ResourceManagementError(503, "cluster_unavailable", "The selected cluster configuration is unavailable") from None
    # In particular, never replay a POST/DELETE after a transport error.
    configuration.retries = 0
    with client.ApiClient(configuration=configuration) as api_client:
        yield ManagementClient(api_client)
