import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as SQLAlchemySession
import yaml

from app.core.dependencies import (
    AuthenticatedActor,
    get_cluster_client,
    get_current_actor,
    get_database_session,
    get_settings,
)
from app.core.rbac import Permission, require_permission
from app.core.config import Settings
from app.core.audit import AuditEvent, record_audit
from app.core.passwords import hash_password, password_matches, validate_password_policy
from app.core.timeutils import is_expired, now
from app.models.entities import Session, UserAccount, ClusterConnection

from .schemas import ActorResponse, HealthResponse
from .discovery_schemas import (
    ClusterStatusResponse,
    NamespaceItem,
    NamespaceResponse,
    ResourceItem,
    ResourceResponse,
    ResourceType,
)
from .auth_schemas import ChangePasswordRequest, LoginRequest, LoginResponse, MeResponse
from .cluster_schemas import (
    ClusterCreateRequest,
    ClusterListResponse,
    ClusterStatusUpdateRequest,
    ClusterSummary,
)
from .detail_schemas import DetailResourceType, EventResponse, LogResponse, ResourceDetailResponse, YamlResponse
from .metrics_schemas import (
    MetricsSummaryResponse,
    NamespaceMetricSummary,
    NamespaceMetricsResponse,
    NodeMetricItem,
    NodesMetricsResponse,
    StorageMetricsItem,
    StorageMetricsResponse,
    WorkloadMetricItem,
)
from app.kubernetes.client import ClusterClient, ClusterMetricsError

router = APIRouter()


def _signed_cookie(email: str, expires_at: int, secret: str) -> tuple[str, str]:
    payload = base64.urlsafe_b64encode(
        json.dumps({"email": email, "expiresAt": expires_at}, separators=(",", ":")).encode()
    ).decode().rstrip("=")
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
    signature_text = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    return f"{payload}.{signature_text}", hashlib.sha256(payload.encode()).hexdigest()


@router.get("/health", response_model=HealthResponse)
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    return HealthResponse(status="ok", service=settings.service_name)


@router.get("/auth/context", response_model=ActorResponse)
async def auth_context(
    actor: Annotated[AuthenticatedActor, Depends(get_current_actor)],
    _database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> ActorResponse:
    return ActorResponse(identifier=actor.identifier, role=actor.role)


@router.post("/auth/login", response_model=LoginResponse)
def login(
    credentials: LoginRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> LoginResponse:
    email = credentials.email.strip().lower()
    user = database.scalar(select(UserAccount).where(UserAccount.email == email))

    if user is None and email == settings.admin_email and credentials.password == settings.admin_password:
        user = UserAccount(
            email=settings.admin_email,
            password_hash=hash_password(credentials.password),
            role="admin",
            is_active=True,
            must_change_password=False,
            updated_at=now(),
        )
        database.add(user)
        database.flush()
        record_audit(
            database,
            AuditEvent.USER_CREATED,
            actor_id=user.id,
            resource_type="user",
            resource_id=str(user.id),
            target_user_id=user.id,
            result="success",
            context={"email": email, "role": "admin", "source": "environment_bootstrap"},
        )

    if user is None:
        record_audit(
            database,
            AuditEvent.USER_LOGIN_FAILURE,
            actor_id=None,
            resource_type="user",
            resource_id=email,
            result="unknown_user",
        )
        database.commit()
        raise HTTPException(status_code=401, detail={"code": "authentication_required", "message": "Authentication is required"})

    if not password_matches(credentials.password, user.password_hash):
        record_audit(
            database,
            AuditEvent.USER_LOGIN_FAILURE,
            actor_id=user.id,
            resource_type="user",
            resource_id=str(user.id),
            result="bad_credentials",
        )
        database.commit()
        raise HTTPException(status_code=401, detail={"code": "authentication_required", "message": "Authentication is required"})

    if not user.is_active:
        record_audit(
            database,
            AuditEvent.USER_LOGIN_FAILURE,
            actor_id=user.id,
            resource_type="user",
            resource_id=str(user.id),
            result="account_disabled",
        )
        database.commit()
        raise HTTPException(status_code=401, detail={"code": "authentication_required", "message": "Authentication is required"})

    restricted = user.must_change_password or is_expired(user.password_expires_at)
    expires_at = int((time.time() + 60 * 60 * 12) * 1000)
    cookie, token_hash = _signed_cookie(email, expires_at, settings.auth_secret)
    database.add(
        Session(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.fromtimestamp(expires_at / 1000, tz=timezone.utc),
            restricted=restricted,
        )
    )
    current_time = now()
    user.last_login_at = current_time
    user.updated_at = current_time
    record_audit(
        database,
        AuditEvent.USER_LOGIN_SUCCESS,
        actor_id=user.id,
        resource_type="user",
        resource_id=str(user.id),
        result="change_required" if restricted else "success",
    )
    database.commit()
    return LoginResponse(cookie=cookie, expires_at=expires_at, change_required=restricted)


@router.get("/auth/me", response_model=MeResponse)
def auth_me(
    actor: Annotated[AuthenticatedActor, Depends(get_current_actor)],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> MeResponse:
    user = database.get(UserAccount, actor.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail={"code": "authentication_required", "message": "Authentication is required"})
    return MeResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        must_change_password=user.must_change_password,
        password_expires_at=user.password_expires_at,
        password_expired=is_expired(user.password_expires_at),
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )


@router.post("/auth/change-password", response_model=MeResponse)
def change_password(
    request: ChangePasswordRequest,
    actor: Annotated[AuthenticatedActor, Depends(get_current_actor)],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MeResponse:
    user = database.get(UserAccount, actor.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail={"code": "authentication_required", "message": "Authentication is required"})
    if not password_matches(request.current_password, user.password_hash):
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_current_password", "message": "The current password is incorrect"},
        )
    valid, reason = validate_password_policy(request.new_password, settings.password_min_length)
    if not valid:
        raise HTTPException(status_code=422, detail={"code": "invalid_password", "message": reason})

    current_time = now()
    user.password_hash = hash_password(request.new_password)
    user.must_change_password = False
    user.password_changed_at = current_time
    user.password_expires_at = current_time + timedelta(days=settings.password_ttl_days)
    user.updated_at = current_time
    database.execute(delete(Session).where(Session.user_id == user.id, Session.id != actor.session_id))
    current_session = database.get(Session, actor.session_id)
    if current_session is not None:
        current_session.restricted = False
    record_audit(
        database,
        AuditEvent.USER_PASSWORD_CHANGED,
        actor_id=user.id,
        resource_type="user",
        resource_id=str(user.id),
        target_user_id=user.id,
        result="success",
    )
    database.commit()
    return MeResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        must_change_password=user.must_change_password,
        password_expires_at=user.password_expires_at,
        password_expired=is_expired(user.password_expires_at),
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )


@router.get("/cluster/status", response_model=ClusterStatusResponse)
def cluster_status(
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.CLUSTERS_READ))],
    cluster: Annotated[ClusterClient, Depends(get_cluster_client)],
) -> ClusterStatusResponse:
    cluster.namespaces()
    return ClusterStatusResponse(status="connected", cluster=cluster.cluster_name)


@router.get("/cluster/namespaces", response_model=NamespaceResponse)
def cluster_namespaces(
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.CLUSTERS_READ))],
    cluster: Annotated[ClusterClient, Depends(get_cluster_client)],
) -> NamespaceResponse:
    return NamespaceResponse(
        items=[NamespaceItem(name=name, status=status) for name, status in cluster.namespaces()]
    )


@router.get("/cluster/resources/{resource_type}", response_model=ResourceResponse)
def cluster_resources(
    resource_type: ResourceType,
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.RESOURCES_READ))],
    cluster: Annotated[ClusterClient, Depends(get_cluster_client)],
    namespace: str | None = None,
) -> ResourceResponse:
    if resource_type in ("nodes", "persistent-volumes", "cluster-roles", "storage-classes") and namespace is not None:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_namespace_scope", "message": f"{resource_type} are cluster-scoped"},
        )
    return ResourceResponse(
        items=[
            ResourceItem(
                cluster=item.cluster,
                namespace=item.namespace,
                kind=item.kind,
                name=item.name,
                status=item.status,
                health=item.health,
            )
            for item in cluster.resources(resource_type, namespace)
        ]
    )


def _validate_detail_scope(resource_type: str, cluster: str, client_name: str, namespace: str | None) -> None:
    if cluster != client_name:
        raise HTTPException(status_code=422, detail={"code": "invalid_resource_identity", "message": "Invalid cluster scope"})
    if resource_type == "nodes" and namespace is not None:
        raise HTTPException(status_code=422, detail={"code": "invalid_resource_identity", "message": "Nodes are cluster-scoped"})
    if resource_type != "nodes" and not namespace:
        raise HTTPException(status_code=422, detail={"code": "invalid_resource_identity", "message": "Namespace is required"})


@router.get("/cluster/resources/{resource_type}/{name}", response_model=ResourceDetailResponse)
def resource_detail(
    resource_type: DetailResourceType,
    name: str,
    cluster: str,
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.RESOURCES_READ))],
    client: Annotated[ClusterClient, Depends(get_cluster_client)],
    namespace: str | None = None,
) -> ResourceDetailResponse:
    _validate_detail_scope(resource_type, cluster, client.cluster_name, namespace)
    detail = client.detail(resource_type, name, namespace)
    return ResourceDetailResponse(**{key: detail[key] for key in ("cluster", "resource_type", "name", "namespace", "kind", "status", "metadata")}, source="kubernetes")


@router.get("/cluster/resources/{resource_type}/{name}/yaml", response_model=YamlResponse)
def resource_yaml(
    resource_type: DetailResourceType,
    name: str,
    cluster: str,
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.RESOURCES_READ))],
    client: Annotated[ClusterClient, Depends(get_cluster_client)],
    namespace: str | None = None,
) -> YamlResponse:
    _validate_detail_scope(resource_type, cluster, client.cluster_name, namespace)
    content, truncated = client.yaml(resource_type, name, namespace)
    return YamlResponse(content=content, truncated=truncated)


@router.get("/cluster/resources/{resource_type}/{name}/logs", response_model=LogResponse)
def resource_logs(
    resource_type: DetailResourceType,
    name: str,
    cluster: str,
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.RESOURCES_READ))],
    client: Annotated[ClusterClient, Depends(get_cluster_client)],
    namespace: str | None = None,
) -> LogResponse:
    _validate_detail_scope(resource_type, cluster, client.cluster_name, namespace)
    if resource_type != "pods":
        raise HTTPException(status_code=422, detail={"code": "invalid_resource_identity", "message": "Logs are only available for pods"})
    lines, truncated, container = client.logs(name, namespace)
    return LogResponse(lines=lines, truncated=truncated, container=container)


@router.get("/cluster/resources/{resource_type}/{name}/events", response_model=EventResponse)
def resource_events(
    resource_type: DetailResourceType,
    name: str,
    cluster: str,
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.RESOURCES_READ))],
    client: Annotated[ClusterClient, Depends(get_cluster_client)],
    namespace: str | None = None,
) -> EventResponse:
    _validate_detail_scope(resource_type, cluster, client.cluster_name, namespace)
    items, truncated = client.events(name, namespace)
    return EventResponse(items=items, truncated=truncated)


_UNAVAILABLE_NODES = NodesMetricsResponse(available=False, reason="unavailable", items=[])
_UNAVAILABLE_NAMESPACE = NamespaceMetricsResponse(available=False, reason="unavailable", workloads=[], summary=None)
_UNAVAILABLE_SUMMARY = MetricsSummaryResponse(available=False, reason="unavailable", namespaces=[])


@router.get("/cluster/metrics/nodes", response_model=NodesMetricsResponse)
def cluster_metrics_nodes(
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.RESOURCES_READ))],
    cluster: Annotated[ClusterClient, Depends(get_cluster_client)],
) -> NodesMetricsResponse:
    try:
        dataset = cluster.metrics()
    except ClusterMetricsError:
        return _UNAVAILABLE_NODES
    return NodesMetricsResponse(
        available=True,
        items=[
            NodeMetricItem(
                name=node.name,
                cpu_usage_millicores=node.cpu_usage_millicores,
                cpu_allocatable_millicores=node.cpu_allocatable_millicores,
                memory_usage_bytes=node.memory_usage_bytes,
                memory_allocatable_bytes=node.memory_allocatable_bytes,
                storage_capacity_bytes=node.storage_capacity_bytes,
                storage_allocatable_bytes=node.storage_allocatable_bytes,
            )
            for node in dataset.nodes
        ],
    )


@router.get("/cluster/metrics/namespaces/{namespace}", response_model=NamespaceMetricsResponse)
def cluster_metrics_namespace(
    namespace: str,
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.RESOURCES_READ))],
    cluster: Annotated[ClusterClient, Depends(get_cluster_client)],
) -> NamespaceMetricsResponse:
    try:
        dataset = cluster.metrics()
    except ClusterMetricsError:
        return _UNAVAILABLE_NAMESPACE
    ns_pods = [pod for pod in dataset.pods if pod.namespace == namespace]
    total_cpu = sum(pod.cpu_usage_millicores for pod in ns_pods)
    total_memory = sum(pod.memory_usage_bytes for pod in ns_pods)
    return NamespaceMetricsResponse(
        available=True,
        workloads=[
            WorkloadMetricItem(
                namespace=pod.namespace,
                name=pod.name,
                kind="Pod",
                cpu_usage_millicores=pod.cpu_usage_millicores,
                memory_usage_bytes=pod.memory_usage_bytes,
            )
            for pod in ns_pods
        ],
        summary=NamespaceMetricSummary(
            namespace=namespace,
            cpu_usage_millicores=total_cpu,
            memory_usage_bytes=total_memory,
            pod_count=len(ns_pods),
        ) if ns_pods else None,
    )


@router.get("/cluster/metrics/summary", response_model=MetricsSummaryResponse)
def cluster_metrics_summary(
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.RESOURCES_READ))],
    cluster: Annotated[ClusterClient, Depends(get_cluster_client)],
) -> MetricsSummaryResponse:
    try:
        dataset = cluster.metrics()
    except ClusterMetricsError:
        return _UNAVAILABLE_SUMMARY
    ns_map: dict[str, dict[str, float | int]] = {}
    for pod in dataset.pods:
        ns = pod.namespace
        if ns not in ns_map:
            ns_map[ns] = {"cpu": 0.0, "memory": 0.0, "count": 0}
        ns_map[ns]["cpu"] += pod.cpu_usage_millicores
        ns_map[ns]["memory"] += pod.memory_usage_bytes
        ns_map[ns]["count"] += 1
    return MetricsSummaryResponse(
        available=True,
        namespaces=[
            NamespaceMetricSummary(
                namespace=ns,
                cpu_usage_millicores=vals["cpu"],
                memory_usage_bytes=vals["memory"],
                pod_count=vals["count"],
            )
            for ns, vals in sorted(ns_map.items())
        ],
    )


_UNAVAILABLE_STORAGE = StorageMetricsResponse(available=False, reason="unavailable", items=[])


@router.get("/cluster/metrics/storage", response_model=StorageMetricsResponse)
def cluster_metrics_storage(
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.RESOURCES_READ))],
    cluster: Annotated[ClusterClient, Depends(get_cluster_client)],
) -> StorageMetricsResponse:
    try:
        items = cluster.storage_metrics()
    except ClusterMetricsError:
        return _UNAVAILABLE_STORAGE
    return StorageMetricsResponse(
        available=True,
        items=[
            StorageMetricsItem(
                name=item.name,
                kind=item.kind,
                capacity_bytes=item.capacity_bytes,
                utilization=item.utilization,
            )
            for item in items
        ],
    )


def _parse_kubeconfig(content: str) -> str:
    """Parse kubeconfig YAML and return the API server endpoint."""
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as error:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_kubeconfig", "message": "kubeconfig is not valid YAML"},
        ) from error
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_kubeconfig", "message": "kubeconfig must be an object"},
        )
    clusters = data.get("clusters")
    if not isinstance(clusters, list) or not clusters:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_kubeconfig", "message": "kubeconfig has no clusters entry"},
        )
    first = clusters[0]
    try:
        server = first["cluster"]["server"]
    except (KeyError, IndexError, TypeError) as error:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_kubeconfig", "message": "kubeconfig cluster has no server"},
        ) from error
    if not isinstance(server, str) or not server.strip():
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_kubeconfig", "message": "kubeconfig cluster has no server"},
        )
    return server


@router.get("/clusters", response_model=ClusterListResponse)
def cluster_list(
    _database: Annotated[SQLAlchemySession, Depends(get_database_session)],
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.CLUSTERS_READ))],
) -> ClusterListResponse:
    rows = _database.scalars(select(ClusterConnection).order_by(ClusterConnection.name)).all()
    return ClusterListResponse(
        items=[
            ClusterSummary(
                id=row.id,
                name=row.name,
                endpoint=row.endpoint,
                status=row.status,
                created_at=row.created_at,
            )
            for row in rows
        ]
    )


async def cluster_create(
    request: Request,
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.CLUSTERS_CREATE))],
) -> ClusterSummary:
    content: str | None = None
    name: str | None = None

    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        name = form.get("name")
        file = form.get("kubeconfig_file")
        if file is None:
            raise HTTPException(
                status_code=422,
                detail={"code": "kubeconfig_required", "message": "kubeconfig_file is required"},
            )
        raw = await file.read()
        content = raw.decode("utf-8")
    else:
        from pydantic import ValidationError

        try:
            payload = ClusterCreateRequest.model_validate_json(await request.body())
        except ValidationError as error:
            raise HTTPException(
                status_code=422,
                detail={"code": "validation_error", "message": "Request validation failed"},
            ) from error
        name = payload.name
        content = payload.kubeconfig_content if payload.kubeconfig_content else None

    if not name or not name.strip():
        raise HTTPException(
            status_code=422,
            detail={"code": "validation_error", "message": "name is required"},
        )
    if content is None or not content.strip():
        raise HTTPException(
            status_code=422,
            detail={"code": "kubeconfig_required", "message": "kubeconfig content is required"},
        )

    endpoint = _parse_kubeconfig(content)

    cluster = ClusterConnection(
        name=name.strip(),
        endpoint=endpoint,
        kubeconfig_ref="",
        kubeconfig_content=content,
        status="active",
    )
    database.add(cluster)
    try:
        database.commit()
    except IntegrityError as error:
        database.rollback()
        raise HTTPException(
            status_code=409,
            detail={"code": "duplicate_cluster_name", "message": "A cluster with this name already exists"},
        ) from error
    database.refresh(cluster)
    record_audit(
        database,
        AuditEvent.CLUSTER_CREATED,
        actor_id=_authorized.user_id,
        resource_type="cluster_connection",
        resource_id=str(cluster.id),
        result="success",
    )
    database.commit()
    return ClusterSummary(
        id=cluster.id,
        name=cluster.name,
        endpoint=cluster.endpoint,
        status=cluster.status,
        created_at=cluster.created_at,
    )


@router.post("/clusters", response_model=ClusterSummary, status_code=201)
async def cluster_create_route(
    request: Request,
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.CLUSTERS_CREATE))],
) -> ClusterSummary:
    return await cluster_create(request, database, _authorized)


@router.patch("/clusters/{cluster_id}", response_model=ClusterSummary)
async def cluster_update_status(
    cluster_id: UUID,
    request: Request,
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.CLUSTERS_UPDATE))],
) -> ClusterSummary:
    from pydantic import ValidationError

    try:
        payload = ClusterStatusUpdateRequest.model_validate_json(await request.body())
    except ValidationError as error:
        raise HTTPException(
            status_code=422,
            detail={"code": "validation_error", "message": "Request validation failed"},
        ) from error
    if payload.status not in ("active", "inactive"):
        raise HTTPException(
            status_code=422,
            detail={"code": "validation_error", "message": "status must be 'active' or 'inactive'"},
        )

    row = database.get(ClusterConnection, cluster_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "cluster_not_found", "message": "Cluster was not found"},
        )

    row.status = payload.status
    database.commit()
    database.refresh(row)
    record_audit(
        database,
        AuditEvent.CLUSTER_STATUS_CHANGED,
        actor_id=_authorized.user_id,
        resource_type="cluster_connection",
        resource_id=str(row.id),
        result="success",
    )
    database.commit()
    return ClusterSummary(
        id=row.id,
        name=row.name,
        endpoint=row.endpoint,
        status=row.status,
        created_at=row.created_at,
    )
