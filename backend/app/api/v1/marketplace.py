import re
from typing import Annotated, Any
from urllib.parse import urlencode, urlsplit
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session as SQLAlchemySession

from app.core.audit import AuditEvent, record_audit
from app.core.config import Settings
from app.core.dependencies import (
    AuthenticatedActor,
    get_current_actor,
    get_database_session,
    get_settings,
)
from app.core.rbac import Permission, require_permission
from app.kubernetes.client import ClusterClient, create_cluster_client
from app.models.entities import ClusterConnection, InstallationJob

from .marketplace_schemas import (
    MarketplaceInstallationListResponse,
    MarketplaceInstallRequest,
    MarketplaceInstallResponse,
    MarketplaceInstallationStatus,
    MarketplacePackageRepository,
    MarketplacePackageSummary,
    MarketplaceSearchResponse,
    MarketplaceVersionsResponse,
)

router = APIRouter()

ARTIFACT_HUB_SEARCH_URL = "https://artifacthub.io/api/v1/packages/search"
ARTIFACT_HUB_PACKAGE_URL = "https://artifacthub.io/api/v1/packages/{kind}/{repository}/{package}"
ARTIFACT_HUB_HELM_KIND = "helm"
REQUEST_TIMEOUT_SECONDS = 15.0
DEFAULT_LIMIT = 24
MAX_LIMIT = 60
MAX_PACKAGE_SEGMENT_LENGTH = 63
PACKAGE_SEGMENT_PATTERN = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")


def _repository_summary(repository: Any) -> MarketplacePackageRepository | None:
    if not isinstance(repository, dict):
        return None
    return MarketplacePackageRepository(
        name=str(repository.get("name") or ""),
        display_name=repository.get("display_name"),
        organization_name=repository.get("organization_name"),
        organization_display_name=repository.get("organization_display_name"),
        url=repository.get("url"),
        kind=repository.get("kind"),
    )


def _package_summary(raw: dict[str, Any]) -> MarketplacePackageSummary:
    return MarketplacePackageSummary(
        package_id=str(raw.get("package_id") or ""),
        name=str(raw.get("name") or ""),
        normalized_name=raw.get("normalized_name"),
        description=raw.get("description"),
        version=raw.get("version"),
        app_version=raw.get("app_version"),
        logo_image_id=raw.get("logo_image_id"),
        stars=raw.get("stars"),
        deprecated=bool(raw.get("deprecated", False)),
        official=bool(raw.get("official", False)),
        signed=bool(raw.get("signed", False)),
        license=raw.get("license"),
        repository=_repository_summary(raw.get("repository")),
    )


def _read_limit(value: str | None) -> int:
    if value is None or value == "":
        return DEFAULT_LIMIT
    try:
        limit = int(value)
    except ValueError:
        limit = -1
    if not 1 <= limit <= MAX_LIMIT:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_pagination", "message": "limit must be an integer between 1 and 60"},
        )
    return limit


def _read_offset(value: str | None) -> int:
    if value is None or value == "":
        return 0
    try:
        offset = int(value)
    except ValueError:
        offset = -1
    if offset < 0:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_pagination", "message": "offset must be a non-negative integer"},
        )
    return offset


def _upstream_error(message: str) -> HTTPException:
    return HTTPException(
        status_code=502,
        detail={"code": "marketplace_upstream_error", "message": message},
    )


async def _fetch_artifact_hub_search(url: str) -> httpx.Response:
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        return await client.get(url)


@router.get("/marketplace/packages", response_model=MarketplaceSearchResponse)
async def list_marketplace_packages(
    _actor: Annotated[AuthenticatedActor, Depends(get_current_actor)],
    limit: Annotated[str | None, Query()] = None,
    offset: Annotated[str | None, Query()] = None,
    ts_query_web: Annotated[str | None, Query()] = None,
    sort: Annotated[str | None, Query()] = None,
) -> MarketplaceSearchResponse:
    page_size = _read_limit(limit)
    page_offset = _read_offset(offset)

    params: dict[str, Any] = {
        "kind": 0,
        "deprecated": "false",
        "limit": page_size,
        "offset": page_offset,
    }
    if ts_query_web is not None:
        params["ts_query_web"] = ts_query_web
    if sort is not None:
        params["sort"] = sort
    search_url = f"{ARTIFACT_HUB_SEARCH_URL}?{urlencode(params)}"

    try:
        upstream = await _fetch_artifact_hub_search(search_url)
    except httpx.HTTPError:
        raise _upstream_error("Artifact Hub is unavailable")

    if upstream.status_code != 200:
        raise _upstream_error(f"Artifact Hub returned status {upstream.status_code}")

    try:
        payload = upstream.json()
    except ValueError:
        raise _upstream_error("Artifact Hub returned invalid package data")

    raw_packages = payload.get("packages") if isinstance(payload, dict) else None
    if not isinstance(raw_packages, list):
        raise _upstream_error("Artifact Hub returned unexpected package data")

    total = len(raw_packages)
    total_header = upstream.headers.get("Pagination-Total-Count")
    if total_header is not None:
        try:
            total = max(total, int(total_header))
        except ValueError:
            pass

    packages = [_package_summary(item) for item in raw_packages if isinstance(item, dict)]
    return MarketplaceSearchResponse(packages=packages, total=total)


def _read_package_segment(value: str, label: str) -> str:
    if (
        not value
        or len(value) > MAX_PACKAGE_SEGMENT_LENGTH
        or not PACKAGE_SEGMENT_PATTERN.fullmatch(value)
    ):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_package_reference",
                "message": f"{label} must be a DNS-1123 label (lowercase letters, digits, dashes)",
            },
        )
    return value


def _available_version_strings(raw_versions: list[Any]) -> list[str]:
    entries: list[tuple[str, int]] = []
    for entry in raw_versions:
        if not isinstance(entry, dict):
            continue
        version = entry.get("version")
        if not isinstance(version, str) or not version:
            continue
        ts = entry.get("ts")
        entries.append((version, int(ts) if isinstance(ts, (int, float)) else 0))
    entries.sort(key=lambda item: (item[1], item[0]), reverse=True)
    return [version for version, _ in entries]


@router.get(
    "/marketplace/packages/{repository_name}/{package_name}/versions",
    response_model=MarketplaceVersionsResponse,
)
async def get_package_versions(
    _actor: Annotated[AuthenticatedActor, Depends(get_current_actor)],
    repository_name: str,
    package_name: str,
) -> MarketplaceVersionsResponse:
    repo_segment = _read_package_segment(repository_name, "repository")
    package_segment = _read_package_segment(package_name, "package")
    detail_url = ARTIFACT_HUB_PACKAGE_URL.format(
        kind=ARTIFACT_HUB_HELM_KIND,
        repository=repo_segment,
        package=package_segment,
    )

    try:
        upstream = await _fetch_artifact_hub_search(detail_url)
    except httpx.HTTPError:
        raise _upstream_error("Artifact Hub is unavailable")

    if upstream.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail={"code": "marketplace_not_found", "message": "Package not found"},
        )
    if upstream.status_code != 200:
        raise _upstream_error(f"Artifact Hub returned status {upstream.status_code}")

    try:
        payload = upstream.json()
    except ValueError:
        raise _upstream_error("Artifact Hub returned invalid package data")

    if not isinstance(payload, dict):
        raise _upstream_error("Artifact Hub returned unexpected package data")

    raw_versions = payload.get("available_versions")
    if not isinstance(raw_versions, list):
        raise _upstream_error("Artifact Hub returned unexpected package data")

    return MarketplaceVersionsResponse(
        package_id=str(payload.get("package_id") or ""),
        name=str(payload.get("name") or ""),
        repository_name=repo_segment,
        versions=_available_version_strings(raw_versions),
    )


def _resolve_cluster(database: SQLAlchemySession, name: str) -> ClusterConnection:
    row = database.scalar(select(ClusterConnection).where(ClusterConnection.name == name))
    if row is None or row.status == "inactive":
        raise HTTPException(
            status_code=404,
            detail={"code": "cluster_not_found", "message": "Cluster was not found"},
        )
    return row


def _ensure_namespace_allowed(namespace: str) -> None:
    if namespace == "kube-system":
        raise HTTPException(
            status_code=422,
            detail={
                "code": "namespace_protected",
                "message": "Installing into the kube-system namespace is not allowed",
            },
        )


def _ensure_namespace_exists(client: ClusterClient, namespace: str) -> None:
    names = [name for name, _ in client.namespaces()]
    if namespace not in names:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "namespace_not_found",
                "message": "Namespace was not found in cluster",
            },
        )


async def _fetch_package_detail(repository_name: str, package_name: str) -> dict[str, Any]:
    repo_segment = _read_package_segment(repository_name, "repository")
    package_segment = _read_package_segment(package_name, "package")
    detail_url = ARTIFACT_HUB_PACKAGE_URL.format(
        kind=ARTIFACT_HUB_HELM_KIND,
        repository=repo_segment,
        package=package_segment,
    )

    try:
        upstream = await _fetch_artifact_hub_search(detail_url)
    except httpx.HTTPError:
        raise _upstream_error("Artifact Hub is unavailable")

    if upstream.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail={"code": "marketplace_not_found", "message": "Package not found"},
        )
    if upstream.status_code != 200:
        raise _upstream_error(f"Artifact Hub returned status {upstream.status_code}")

    try:
        payload = upstream.json()
    except ValueError:
        raise _upstream_error("Artifact Hub returned invalid package data")

    if not isinstance(payload, dict):
        raise _upstream_error("Artifact Hub returned unexpected package data")

    raw_versions = payload.get("available_versions")
    if not isinstance(raw_versions, list):
        raise _upstream_error("Artifact Hub returned unexpected package data")
    versions = _available_version_strings(raw_versions)

    chart_name = str(payload.get("name") or "")
    repository = payload.get("repository")
    repo_name = str(repository.get("name") or "") if isinstance(repository, dict) else ""
    repo_url = str(repository.get("url") or "") if isinstance(repository, dict) else ""
    if not chart_name or not repo_name or not repo_url:
        raise _upstream_error("Artifact Hub returned unexpected package data")

    if not PACKAGE_SEGMENT_PATTERN.fullmatch(chart_name) or not PACKAGE_SEGMENT_PATTERN.fullmatch(
        repo_name
    ):
        raise HTTPException(
            status_code=502,
            detail={
                "code": "invalid_package_source",
                "message": "Artifact Hub returned an untrusted chart name or repository",
            },
        )
    if urlsplit(repo_url).scheme not in ("http", "https"):
        raise HTTPException(
            status_code=502,
            detail={
                "code": "invalid_package_source",
                "message": "Artifact Hub returned an untrusted chart repository URL",
            },
        )

    return {
        "package_id": str(payload.get("package_id") or ""),
        "versions": versions,
        "chart_name": chart_name,
        "chart_repository": repo_name,
        "chart_repository_url": repo_url,
    }


@router.post("/marketplace/install", response_model=MarketplaceInstallResponse, status_code=201)
async def create_installation(
    request: MarketplaceInstallRequest,
    _actor: Annotated[AuthenticatedActor, Depends(require_permission(Permission.MARKETPLACE_INSTALL))],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MarketplaceInstallResponse:
    cluster = _resolve_cluster(database, request.cluster)

    client = create_cluster_client(
        settings,
        kubeconfig_content=cluster.kubeconfig_content,
        cluster_name=cluster.name,
    )
    _ensure_namespace_allowed(request.namespace)
    _ensure_namespace_exists(client, request.namespace)

    detail = await _fetch_package_detail(request.repository_name, request.package_name)
    if request.package_id != detail["package_id"]:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "package_mismatch",
                "message": "Package does not match the requested package",
            },
        )
    if request.version not in detail["versions"]:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "version_not_available",
                "message": "Version is not available for this package",
            },
        )

    job = InstallationJob(
        package_id=request.package_id,
        package_name=request.package_name,
        chart_name=detail["chart_name"],
        chart_repository=detail["chart_repository"],
        chart_repository_url=detail["chart_repository_url"],
        chart_version=request.version,
        cluster_id=cluster.id,
        namespace=request.namespace,
        release_name=request.release_name,
        status="queued",
    )
    database.add(job)
    database.commit()
    database.refresh(job)
    record_audit(
        database,
        AuditEvent.MARKETPLACE_INSTALL_QUEUED,
        actor_id=_actor.user_id,
        resource_type="installation_job",
        resource_id=str(job.id),
        result="success",
    )
    database.commit()
    return MarketplaceInstallResponse(job_id=job.id, status="queued")


@router.get(
    "/marketplace/installations/{job_id}",
    response_model=MarketplaceInstallationStatus,
)
async def get_installation_status(
    job_id: UUID,
    _actor: Annotated[AuthenticatedActor, Depends(get_current_actor)],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> MarketplaceInstallationStatus:
    job = database.get(InstallationJob, job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "installation_not_found",
                "message": "Installation job was not found",
            },
        )
    return MarketplaceInstallationStatus(
        job_id=job.id,
        package_name=job.package_name,
        cluster=job.cluster.name,
        namespace=job.namespace,
        release_name=job.release_name,
        status=job.status,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


_INSTALLATION_STATUSES = ("queued", "running", "succeeded", "failed", "cancelled")


@router.get("/marketplace/installations", response_model=MarketplaceInstallationListResponse)
async def list_installations(
    _actor: Annotated[AuthenticatedActor, Depends(get_current_actor)],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
    status: Annotated[str | None, Query()] = None,
    limit: Annotated[int | None, Query(ge=1, le=200)] = 100,
) -> MarketplaceInstallationListResponse:
    if status is not None and status not in _INSTALLATION_STATUSES:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_status_filter",
                "message": "status must be one of queued, running, succeeded, failed, cancelled",
            },
        )

    statement = select(InstallationJob)
    count_statement = select(func.count()).select_from(InstallationJob)
    if status is not None:
        statement = statement.where(InstallationJob.status == status)
        count_statement = count_statement.where(InstallationJob.status == status)

    total = database.scalar(count_statement) or 0
    rows = database.scalars(
        statement.order_by(InstallationJob.created_at.desc(), InstallationJob.id.desc()).limit(
            limit
        )
    ).all()
    return MarketplaceInstallationListResponse(
        items=[
            MarketplaceInstallationStatus(
                job_id=job.id,
                package_name=job.package_name,
                cluster=job.cluster.name,
                namespace=job.namespace,
                release_name=job.release_name,
                status=job.status,
                error_message=job.error_message,
                created_at=job.created_at,
                started_at=job.started_at,
                completed_at=job.completed_at,
            )
            for job in rows
        ],
        total=total,
    )