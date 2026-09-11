"""Live resource management, separate from the existing read-only discovery APIs."""

import logging
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.v1.resource_management_schemas import (
    CreateResourceRequest, CreatedResource, DeleteResourceRequest, DeletionRequested,
    ManagedResource, ManagedResourceList,
)
from app.core.audit import AuditEvent, record_audit
from app.core.config import Settings
from app.core.dependencies import AuthenticatedActor, get_database_session, get_settings
from app.core.rbac import Permission, has_permission, require_permission
from app.kubernetes.client import _health_status
from app.kubernetes.resource_management import (
    ResourceManagementError, ensure_unprotected, management_client, parse_manifest,
    protection_reason, resource_kind, validate_name, validate_scope,
)
from app.models.entities import ClusterConnection

router = APIRouter(prefix="/cluster/manage-resources", tags=["resource-management"])
logger = logging.getLogger(__name__)
Database = Annotated[Session, Depends(get_database_session)]
Configuration = Annotated[Settings, Depends(get_settings)]


def _target(request: Request, database: Session, resource_type: str, *, mutation: bool):
    kind = resource_kind(resource_type)
    names = request.query_params.getlist("cluster")
    if len(names) != 1 or not names[0].strip() or names[0] != names[0].strip():
        raise ResourceManagementError(422, "invalid_resource_identity", "Select one explicit registered cluster")
    namespaces = request.query_params.getlist("namespace")
    if len(namespaces) > 1:
        raise ResourceManagementError(422, "invalid_namespace_scope", "Select one namespace")
    namespace = namespaces[0] if namespaces else None
    validate_scope(kind, namespace, mutation=mutation)
    cluster = database.scalar(select(ClusterConnection).where(ClusterConnection.name == names[0]))
    if cluster is None or cluster.status != "active":
        raise ResourceManagementError(404, "cluster_not_found", "Cluster was not found")
    return cluster, kind, namespace


def _summary(item, cluster, resource_type: str, actor: AuthenticatedActor, settings: Settings) -> ManagedResource:
    kind = resource_kind(resource_type)
    metadata = item.metadata
    namespace = metadata.namespace if kind.namespaced else None
    status = getattr(item, "status", None)
    deleting = getattr(metadata, "deletion_timestamp", None)
    phase = getattr(status, "phase", None)
    available = getattr(status, "available_replicas", None)
    display = "Terminating" if deleting else str(phase or (f"{available} available" if available is not None else "Unknown"))
    reason = protection_reason(kind, namespace, metadata.name, settings.host_namespace, deleting=True)
    if not has_permission(actor.role, Permission.RESOURCES_DELETE):
        reason = "Your role has read-only resource access."
    elif deleting:
        reason = "Deletion has already been requested."
    return ManagedResource(
        cluster=cluster.name, cluster_id=cluster.id, resource_type=resource_type,
        api_version=kind.api_version, kind=kind.kind, name=metadata.name,
        namespace=namespace, uid=metadata.uid, status=display,
        health=_health_status(item, kind.kind) if status is not None else "unknown",
        deletion_timestamp=deleting, delete_blocked_reason=reason,
    )


@router.get("/{resource_type}", response_model=ManagedResourceList)
def list_resources(
    resource_type: str, request: Request,
    actor: Annotated[AuthenticatedActor, Depends(require_permission(Permission.RESOURCES_READ))],
    database: Database, settings: Configuration,
) -> ManagedResourceList:
    cluster, kind, namespace = _target(request, database, resource_type, mutation=False)
    with management_client(cluster) as kubernetes:
        items = kubernetes.resources(kind, namespace)
    return ManagedResourceList(items=[_summary(item, cluster, resource_type, actor, settings) for item in items])


def _rollback_audit(database: Session) -> None:
    try:
        database.rollback()
    except SQLAlchemyError:
        pass


def _mutate(database, actor, cluster, resource_type, namespace, name, uid, action, invoke):
    operation_id = str(uuid4())
    context = {
        "operation_id": operation_id, "cluster_id": str(cluster.id), "cluster": cluster.name,
        "resource_type": resource_type, "namespace": namespace, "name": name, "uid": uid,
    }
    requested, completed = {
        "create": (AuditEvent.RESOURCE_CREATE_REQUESTED, AuditEvent.RESOURCE_CREATE_RESULT),
        "delete": (AuditEvent.RESOURCE_DELETE_REQUESTED, AuditEvent.RESOURCE_DELETE_RESULT),
    }[action]
    actor_id = actor.user_id
    try:
        record_audit(database, requested, actor_id, resource_type, name, result="requested", context=context)
        database.commit()
    except SQLAlchemyError:
        _rollback_audit(database)
        raise ResourceManagementError(503, "audit_unavailable", "The audit record could not be saved. No resource change was sent.") from None

    def record_result(result, code=None, returned_uid=uid):
        try:
            record_audit(
                database, completed, actor_id, resource_type, name, result=result,
                context={**context, "uid": returned_uid, "error_code": code},
            )
            database.commit()
        except SQLAlchemyError:
            _rollback_audit(database)
            logger.error("Could not record result for resource operation %s", operation_id)

    try:
        response = invoke()
    except ResourceManagementError as error:
        record_result("unknown" if error.code == "operation_outcome_unknown" else "failure", error.code)
        raise
    except Exception:
        record_result("unknown", "internal_error")
        raise
    returned_uid = response.resource.uid if isinstance(response, CreatedResource) else response.uid
    record_result("success", returned_uid=returned_uid)
    return response


@router.post("/{resource_type}", response_model=CreatedResource, status_code=201)
def create_resource(
    resource_type: str, request: Request, body: CreateResourceRequest,
    actor: Annotated[AuthenticatedActor, Depends(require_permission(Permission.RESOURCES_CREATE))],
    database: Database, settings: Configuration,
) -> CreatedResource:
    cluster, kind, namespace = _target(request, database, resource_type, mutation=True)
    manifest = parse_manifest(body.yaml, kind, namespace)
    name = manifest["metadata"]["name"]
    ensure_unprotected(kind, namespace, name, settings.host_namespace, deleting=False)
    with management_client(cluster) as kubernetes:
        def invoke():
            item = kubernetes.create(kind, namespace, manifest)
            return CreatedResource(resource=_summary(item, cluster, resource_type, actor, settings))
        return _mutate(database, actor, cluster, resource_type, namespace, name, None, "create", invoke)


@router.delete("/{resource_type}/{name}", response_model=DeletionRequested, status_code=202)
def delete_resource(
    resource_type: str, name: str, request: Request, body: DeleteResourceRequest,
    actor: Annotated[AuthenticatedActor, Depends(require_permission(Permission.RESOURCES_DELETE))],
    database: Database, settings: Configuration,
) -> DeletionRequested:
    cluster, kind, namespace = _target(request, database, resource_type, mutation=True)
    validate_name(name, label=kind.kind in {"Namespace", "Service"})
    if body.confirm_name != name:
        raise ResourceManagementError(422, "confirmation_required", "Type the exact resource name to confirm deletion")
    if not body.uid.strip():
        raise ResourceManagementError(422, "invalid_resource_identity", "A resource UID is required")
    ensure_unprotected(kind, namespace, name, settings.host_namespace, deleting=True)
    with management_client(cluster) as kubernetes:
        current = kubernetes.read(kind, namespace, name)
        if current.metadata.uid != body.uid:
            raise ResourceManagementError(409, "resource_conflict", "This resource has been replaced. Refresh and review the new object.")
        response = DeletionRequested(
            cluster=cluster.name, cluster_id=cluster.id, resource_type=resource_type,
            namespace=namespace, name=name, uid=body.uid,
        )
        def invoke():
            if not getattr(current.metadata, "deletion_timestamp", None):
                kubernetes.delete(kind, namespace, name, body.uid)
            return response
        return _mutate(database, actor, cluster, resource_type, namespace, name, body.uid, "delete", invoke)
