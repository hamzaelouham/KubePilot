from sqlalchemy import select

from app.assistant.sanitize import diagnostic_projection, safe_text, sanitize
from app.assistant.schemas import Observation
from app.kubernetes.resource_management import RESOURCE_KINDS, ResourceKind, ResourceManagementError, management_client, validate_name
from app.models.entities import ClusterConnection

READ_KINDS = {
    **RESOURCE_KINDS,
    "nodes": ResourceKind("v1", "Node", "core", "node", False),
    "persistent-volumes": ResourceKind("v1", "PersistentVolume", "core", "persistent_volume", False),
    "persistent-volume-claims": ResourceKind("v1", "PersistentVolumeClaim", "core", "persistent_volume_claim"),
    "configmaps": ResourceKind("v1", "ConfigMap", "core", "config_map"),
    "secrets": ResourceKind("v1", "Secret", "core", "secret"),
    "replica-sets": ResourceKind("apps/v1", "ReplicaSet", "apps", "replica_set"),
    "replication-controllers": ResourceKind("v1", "ReplicationController", "core", "replication_controller"),
    "ingresses": ResourceKind("networking.k8s.io/v1", "Ingress", "networking", "ingress"),
}


def active_cluster(database, name):
    cluster = database.scalar(select(ClusterConnection).where(ClusterConnection.name == name, ClusterConnection.status == "active"))
    if cluster is None:
        raise ResourceManagementError(404, "cluster_not_found", "Select an active registered cluster")
    return cluster


def observe(database, operation: str, body: Observation):
    cluster = active_cluster(database, body.cluster)
    kind = READ_KINDS[body.resource_type]
    namespace = body.namespace if kind.namespaced else None
    if body.name:
        validate_name(body.name)
    if operation in {"inspect", "logs"} and (not body.name or kind.namespaced and not namespace):
        raise ResourceManagementError(422, "invalid_scope", "Select a named resource and its namespace")
    if operation in {"logs", "events"} and not body.namespace:
        raise ResourceManagementError(422, "invalid_scope", "Select a namespace for logs or events")
    with management_client(cluster) as client:
        if operation == "list":
            items, more = client.bounded_resources(kind, namespace, limit=100)
            result = {"items": [diagnostic_projection(item.to_dict(), body.resource_type) for item in items], "truncated": more}
        elif operation == "inspect":
            result = diagnostic_projection(client.read(kind, namespace, body.name).to_dict(), body.resource_type)
        elif operation == "events":
            selectors = ([f"involvedObject.name={body.name}"] if body.name else []) + (["type=Warning"] if body.warnings_only else [])
            response = client._call(READ_KINDS["pods"], "list_namespaced_event", "read", namespace=body.namespace, field_selector=",".join(selectors), limit=100)
            result = {"items": [sanitize({"type": e.type, "reason": e.reason, "message": e.message, "name": e.involved_object.name, "kind": e.involved_object.kind, "last_timestamp": str(e.last_timestamp or e.event_time or "")}) for e in response.items], "truncated": bool(getattr(response.metadata, "_continue", None))}
        elif operation == "logs":
            if body.resource_type != "pods":
                raise ResourceManagementError(422, "invalid_resource_type", "Logs are available for Pods only")
            args = {"name": body.name, "namespace": namespace, "tail_lines": 100, "limit_bytes": 16000, "timestamps": True, "previous": body.previous}
            if body.container:
                args["container"] = body.container
            content = client._call(kind, "read_namespaced_pod_log", "read", **args)
            result = {"lines": safe_text(content, 16000).splitlines(), "truncated": True, "container": body.container, "previous": body.previous, "notice": "Bounded, credential-scrubbed log excerpt; arbitrary application text may be sensitive."}
        else:
            raise ResourceManagementError(422, "invalid_tool", "Unsupported observation")
    return {"cluster": cluster.name, "namespace": namespace, "resource_type": body.resource_type, "name": body.name, "result": result}
