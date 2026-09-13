import re
from typing import Annotated
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.audit import AuditEvent, record_audit
from app.core.dependencies import AuthenticatedActor, get_database_session
from app.core.rbac import Permission, require_permission
from app.core.timeutils import now
from app.models.entities import HelmRepository

from .helm_repository_schemas import (
    HelmRepositoryCreateRequest,
    HelmRepositoryDeleteResponse,
    HelmRepositoryListResponse,
    HelmRepositorySummary,
    HelmRepositoryUpdateRequest,
)

router = APIRouter(prefix="/helm/repositories", tags=["helm-repositories"])
_NAME_PATTERN = re.compile(r"^[a-z0-9](?:[-a-z0-9]{0,61}[a-z0-9])?$")


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _normalize_name(value: str) -> str:
    name = value.strip().lower()
    if not _NAME_PATTERN.fullmatch(name):
        raise _error(422, "invalid_repository_name", "Repository names must use lowercase letters, numbers, and hyphens.")
    return name


def _normalize_url(value: str) -> str:
    url = value.strip().rstrip("/")
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
    except ValueError as error:
        raise _error(422, "invalid_repository_url", "Repository URL must be a valid public HTTP(S) URL.") from error
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.netloc
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise _error(422, "invalid_repository_url", "Repository URL must be a public HTTP(S) URL without credentials or query parameters.")
    return url


def _get_repository(database: Session, repository_id: UUID) -> HelmRepository:
    repository = database.get(HelmRepository, repository_id)
    if repository is None:
        raise _error(404, "repository_not_found", "The Helm repository was not found.")
    return repository


def _commit_or_conflict(database: Session, conflict_message: str) -> None:
    try:
        database.commit()
    except IntegrityError as error:
        database.rollback()
        raise _error(409, "repository_conflict", conflict_message) from error
    except SQLAlchemyError as error:
        database.rollback()
        raise _error(503, "operation_outcome_unknown", "The repository operation outcome is unknown. Refresh before trying again.") from error


@router.get("", response_model=HelmRepositoryListResponse)
def list_repositories(
    _actor: Annotated[AuthenticatedActor, Depends(require_permission(Permission.RESOURCES_READ))],
    database: Annotated[Session, Depends(get_database_session)],
) -> HelmRepositoryListResponse:
    repositories = database.scalars(select(HelmRepository).order_by(HelmRepository.name)).all()
    return HelmRepositoryListResponse(items=[HelmRepositorySummary.model_validate(item) for item in repositories])


@router.post("", response_model=HelmRepositorySummary, status_code=201)
def create_repository(
    request: HelmRepositoryCreateRequest,
    actor: Annotated[AuthenticatedActor, Depends(require_permission(Permission.HELM_REPOSITORIES_MANAGE))],
    database: Annotated[Session, Depends(get_database_session)],
) -> HelmRepositorySummary:
    name = _normalize_name(request.name)
    url = _normalize_url(request.url)
    if database.scalar(select(HelmRepository).where(HelmRepository.name == name)) is not None:
        raise _error(409, "repository_conflict", "A Helm repository with this name already exists.")
    if database.scalar(select(HelmRepository).where(HelmRepository.url == url)) is not None:
        raise _error(409, "repository_conflict", "A Helm repository with this URL already exists.")

    repository = HelmRepository(name=name, url=url, created_by_id=actor.user_id, updated_by_id=actor.user_id)
    database.add(repository)
    try:
        database.flush()
        record_audit(
            database,
            AuditEvent.HELM_REPOSITORY_CREATED,
            actor.user_id,
            "helm_repository",
            str(repository.id),
            result="success",
            context={"name": name, "url": url},
        )
    except IntegrityError as error:
        database.rollback()
        raise _error(409, "repository_conflict", "A Helm repository with this name or URL already exists.") from error
    except SQLAlchemyError as error:
        database.rollback()
        raise _error(503, "operation_outcome_unknown", "The repository operation outcome is unknown. Refresh before trying again.") from error
    _commit_or_conflict(database, "A Helm repository with this name or URL already exists.")
    return HelmRepositorySummary.model_validate(repository)


@router.patch("/{repository_id}", response_model=HelmRepositorySummary)
def update_repository(
    repository_id: UUID,
    request: HelmRepositoryUpdateRequest,
    actor: Annotated[AuthenticatedActor, Depends(require_permission(Permission.HELM_REPOSITORIES_MANAGE))],
    database: Annotated[Session, Depends(get_database_session)],
) -> HelmRepositorySummary:
    repository = _get_repository(database, repository_id)
    if request.name is None and request.url is None:
        raise _error(422, "empty_repository_update", "Provide a repository name or URL to update.")
    old_name, old_url = repository.name, repository.url
    name = _normalize_name(request.name) if request.name is not None else old_name
    url = _normalize_url(request.url) if request.url is not None else old_url
    duplicate = database.scalar(
        select(HelmRepository).where(
            HelmRepository.id != repository.id,
            (HelmRepository.name == name) | (HelmRepository.url == url),
        )
    )
    if duplicate is not None:
        raise _error(409, "repository_conflict", "Another Helm repository already uses this name or URL.")

    repository.name = name
    repository.url = url
    repository.updated_by_id = actor.user_id
    repository.updated_at = now()
    try:
        database.flush()
        record_audit(
            database,
            AuditEvent.HELM_REPOSITORY_UPDATED,
            actor.user_id,
            "helm_repository",
            str(repository.id),
            result="success",
            context={"name": name, "url": url, "previous_name": old_name, "previous_url": old_url},
        )
    except IntegrityError as error:
        database.rollback()
        raise _error(409, "repository_conflict", "Another Helm repository already uses this name or URL.") from error
    except SQLAlchemyError as error:
        database.rollback()
        raise _error(503, "operation_outcome_unknown", "The repository operation outcome is unknown. Refresh before trying again.") from error
    _commit_or_conflict(database, "Another Helm repository already uses this name or URL.")
    return HelmRepositorySummary.model_validate(repository)


@router.delete("/{repository_id}", response_model=HelmRepositoryDeleteResponse)
def delete_repository(
    repository_id: UUID,
    actor: Annotated[AuthenticatedActor, Depends(require_permission(Permission.HELM_REPOSITORIES_MANAGE))],
    database: Annotated[Session, Depends(get_database_session)],
) -> HelmRepositoryDeleteResponse:
    repository = _get_repository(database, repository_id)
    repository_id_value = repository.id
    context = {"name": repository.name, "url": repository.url}
    database.delete(repository)
    try:
        database.flush()
        record_audit(
            database,
            AuditEvent.HELM_REPOSITORY_DELETED,
            actor.user_id,
            "helm_repository",
            str(repository_id_value),
            result="success",
            context=context,
        )
    except SQLAlchemyError as error:
        database.rollback()
        raise _error(503, "operation_outcome_unknown", "The repository operation outcome is unknown. Refresh before trying again.") from error
    _commit_or_conflict(database, "The repository could not be removed because it is in use.")
    return HelmRepositoryDeleteResponse(id=repository_id_value, status="deleted")
