import re
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.audit import AuditEvent, record_audit
from app.core.config import Settings
from app.core.dependencies import AuthenticatedActor, get_database_session, get_settings
from app.core.rbac import Permission, require_permission
from app.kubernetes.helm import HelmError, history, list_releases, resolve_chart_source, validate_chart_version, validate_target_name
from app.models.entities import ClusterConnection, HelmRepository, InstallationJob

from .helm_release_schemas import (
    HelmReleaseActionRequest,
    HelmReleaseActionResponse,
    HelmReleaseHistoryResponse,
    HelmReleaseListResponse,
    HelmReleaseRevision,
    HelmReleaseSummary,
    HelmReleaseUpgradeRequest,
)

router = APIRouter(prefix="/cluster/helm", tags=["helm-releases"])
_PENDING_STATUSES = ("queued", "running")
_CHART_VERSION = re.compile(r"^.+-(.+)$")


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _cluster(request: Request, database: Session) -> ClusterConnection:
    values = request.query_params.getlist("cluster")
    if len(values) != 1 or not values[0].strip() or values[0] != values[0].strip():
        raise _error(422, "invalid_cluster_scope", "Select one explicit registered cluster.")
    cluster = database.scalar(select(ClusterConnection).where(ClusterConnection.name == values[0]))
    if cluster is None or cluster.status != "active":
        raise _error(404, "cluster_not_found", "Cluster was not found.")
    return cluster


def _target(request: Request, database: Session, release_name: str | None = None) -> tuple[ClusterConnection, str]:
    cluster = _cluster(request, database)
    namespaces = request.query_params.getlist("namespace")
    if len(namespaces) != 1:
        raise _error(422, "invalid_namespace_scope", "Select one release namespace.")
    namespace = namespaces[0]
    try:
        validate_target_name(namespace, "namespace")
        if release_name is not None:
            validate_target_name(release_name, "release name")
    except ValueError as error:
        raise _error(422, "invalid_release_identity", str(error)) from error
    return cluster, namespace


def _helm_failure(error: HelmError) -> HTTPException:
    return _error(503, error.code, str(error))


def _find_release(settings: Settings, cluster: ClusterConnection, release_name: str, namespace: str):
    try:
        releases = list_releases(settings, cluster)
    except HelmError as error:
        raise _helm_failure(error) from error
    return next((item for item in releases if item.name == release_name and item.namespace == namespace), None)


def _summary(item) -> HelmReleaseSummary:
    return HelmReleaseSummary(
        name=item.name,
        namespace=item.namespace,
        status=item.status,
        revision=item.revision,
        chart=item.chart,
        app_version=item.app_version,
        updated=item.updated,
        description=item.description,
    )


@router.get("/releases", response_model=HelmReleaseListResponse)
def get_releases(
    request: Request,
    _actor: Annotated[AuthenticatedActor, Depends(require_permission(Permission.RESOURCES_READ))],
    database: Annotated[Session, Depends(get_database_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HelmReleaseListResponse:
    cluster = _cluster(request, database)
    try:
        releases = list_releases(settings, cluster)
    except HelmError as error:
        raise _helm_failure(error) from error
    return HelmReleaseListResponse(items=[_summary(item) for item in releases])


@router.get("/releases/{release_name}/history", response_model=HelmReleaseHistoryResponse)
def get_release_history(
    release_name: str,
    request: Request,
    _actor: Annotated[AuthenticatedActor, Depends(require_permission(Permission.RESOURCES_READ))],
    database: Annotated[Session, Depends(get_database_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HelmReleaseHistoryResponse:
    cluster, namespace = _target(request, database, release_name)
    if _find_release(settings, cluster, release_name, namespace) is None:
        raise _error(404, "release_not_found", "The Helm release was not found in this namespace.")
    try:
        revisions = history(settings, cluster, release_name, namespace)
    except HelmError as error:
        raise _helm_failure(error) from error
    return HelmReleaseHistoryResponse(
        release_name=release_name,
        namespace=namespace,
        revisions=[HelmReleaseRevision(**revision.__dict__) for revision in revisions],
    )


def _queue_action(
    action: str,
    release_name: str,
    request: Request,
    body: HelmReleaseActionRequest,
    actor: AuthenticatedActor,
    database: Session,
    settings: Settings,
) -> HelmReleaseActionResponse:
    cluster, namespace = _target(request, database, release_name)
    if body.confirm_name != release_name:
        raise _error(422, "confirmation_required", "Type the exact release name to confirm this action.")
    live = _find_release(settings, cluster, release_name, namespace)
    if live is None:
        raise _error(404, "release_not_found", "The Helm release was not found in this namespace.")
    pending = database.scalar(
        select(InstallationJob).where(
            InstallationJob.cluster_id == cluster.id,
            InstallationJob.namespace == namespace,
            InstallationJob.release_name == release_name,
            InstallationJob.action.in_(("rollback", "uninstall", "upgrade")),
            InstallationJob.status.in_(_PENDING_STATUSES),
        )
    )
    if pending is not None:
        raise _error(409, "release_action_conflict", "Another action is already pending for this release.")

    chart_name = None
    chart_version = None
    if live.chart:
        match = _CHART_VERSION.match(live.chart)
        if match:
            chart_name = live.chart[: match.start(1) - 1]
            chart_version = match.group(1)[:64]
    job = InstallationJob(
        package_id=None,
        package_name=release_name,
        chart_name=chart_name,
        chart_repository=None,
        chart_repository_url=None,
        chart_version=chart_version,
        cluster_id=cluster.id,
        namespace=namespace,
        release_name=release_name,
        action=action,
        status="queued",
        revision=live.revision,
    )
    operation_id = uuid.uuid4()
    database.add(job)
    try:
        database.flush()
        record_audit(
            database,
            AuditEvent.HELM_RELEASE_ROLLBACK_QUEUED if action == "rollback" else AuditEvent.HELM_RELEASE_UNINSTALL_QUEUED,
            actor.user_id,
            "helm_release",
            f"{cluster.name}/{namespace}/{release_name}",
            result="requested",
            context={
                "operation_id": str(operation_id),
                "cluster_id": str(cluster.id),
                "cluster": cluster.name,
                "namespace": namespace,
                "release": release_name,
                "action": action,
            },
        )
        database.commit()
    except SQLAlchemyError as error:
        database.rollback()
        raise _error(503, "operation_outcome_unknown", "The action could not be queued. Refresh before retrying.") from error
    return HelmReleaseActionResponse(job_id=job.id, status="queued")


def _queue_upgrade(
    release_name: str,
    request: Request,
    body: HelmReleaseUpgradeRequest,
    actor: AuthenticatedActor,
    database: Session,
    settings: Settings,
) -> HelmReleaseActionResponse:
    cluster, namespace = _target(request, database, release_name)
    try:
        validate_target_name(body.chart_name, "chart name")
        validate_chart_version(body.version)
    except ValueError as error:
        raise _error(422, "invalid_chart_source", str(error)) from error
    if body.confirm_name != release_name:
        raise _error(422, "confirmation_required", "Type the exact release name to confirm this action.")
    live = _find_release(settings, cluster, release_name, namespace)
    if live is None:
        raise _error(404, "release_not_found", "The Helm release was not found in this namespace.")
    pending = database.scalar(
        select(InstallationJob).where(
            InstallationJob.cluster_id == cluster.id,
            InstallationJob.namespace == namespace,
            InstallationJob.release_name == release_name,
            InstallationJob.action.in_(("rollback", "uninstall", "upgrade")),
            InstallationJob.status.in_(_PENDING_STATUSES),
        )
    )
    if pending is not None:
        raise _error(409, "release_action_conflict", "Another action is already pending for this release.")
    repository = database.get(HelmRepository, body.repository_id)
    if repository is None:
        raise _error(404, "repository_not_found", "The selected Helm repository was not found.")
    try:
        resolve_chart_source(settings, repository.name, repository.url, body.chart_name, body.version)
    except HelmError as error:
        raise _helm_failure(error) from error

    job = InstallationJob(
        package_id=None,
        package_name=release_name,
        chart_name=body.chart_name,
        chart_repository=repository.name,
        chart_repository_url=repository.url,
        chart_version=body.version,
        cluster_id=cluster.id,
        namespace=namespace,
        release_name=release_name,
        action="upgrade",
        status="queued",
        revision=live.revision,
    )
    operation_id = uuid.uuid4()
    database.add(job)
    try:
        database.flush()
        record_audit(
            database,
            AuditEvent.HELM_RELEASE_UPGRADE_QUEUED,
            actor.user_id,
            "helm_release",
            f"{cluster.name}/{namespace}/{release_name}",
            result="requested",
            context={
                "operation_id": str(operation_id),
                "cluster_id": str(cluster.id),
                "cluster": cluster.name,
                "namespace": namespace,
                "release": release_name,
                "action": "upgrade",
                "repository_id": str(repository.id),
                "repository": repository.name,
                "repository_url": repository.url,
                "chart": body.chart_name,
                "version": body.version,
            },
        )
        database.commit()
    except SQLAlchemyError as error:
        database.rollback()
        raise _error(503, "operation_outcome_unknown", "The upgrade could not be queued. Refresh before retrying.") from error
    return HelmReleaseActionResponse(job_id=job.id, status="queued")


@router.post("/releases/{release_name}/rollback", response_model=HelmReleaseActionResponse, status_code=201)
def rollback_release(
    release_name: str,
    request: Request,
    body: HelmReleaseActionRequest,
    actor: Annotated[AuthenticatedActor, Depends(require_permission(Permission.MARKETPLACE_RELEASE))],
    database: Annotated[Session, Depends(get_database_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HelmReleaseActionResponse:
    return _queue_action("rollback", release_name, request, body, actor, database, settings)


@router.post("/releases/{release_name}/uninstall", response_model=HelmReleaseActionResponse, status_code=201)
def uninstall_release(
    release_name: str,
    request: Request,
    body: HelmReleaseActionRequest,
    actor: Annotated[AuthenticatedActor, Depends(require_permission(Permission.MARKETPLACE_RELEASE))],
    database: Annotated[Session, Depends(get_database_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HelmReleaseActionResponse:
    return _queue_action("uninstall", release_name, request, body, actor, database, settings)


@router.post("/releases/{release_name}/upgrade", response_model=HelmReleaseActionResponse, status_code=201)
def upgrade_release(
    release_name: str,
    request: Request,
    body: HelmReleaseUpgradeRequest,
    actor: Annotated[AuthenticatedActor, Depends(require_permission(Permission.MARKETPLACE_RELEASE))],
    database: Annotated[Session, Depends(get_database_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HelmReleaseActionResponse:
    return _queue_upgrade(release_name, request, body, actor, database, settings)
