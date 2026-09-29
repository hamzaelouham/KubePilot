import json
import math
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session as SQLAlchemySession

from app.core.dependencies import AuthenticatedActor, get_current_actor, get_database_session, get_settings
from app.core.config import Settings
from app.core.rbac import Permission, require_permission
from app.models.entities import AuditAction, UserAccount

from app.services.settings import get_user_preferences, update_user_preferences
from app.services.application_settings import (
    SettingsServiceError,
    delete_application_setting,
    delete_credential,
    list_application_settings,
    list_credential_metadata,
    replace_credential,
    upsert_application_setting,
)
from app.services.ai_providers import (
    ProviderServiceError,
    list_providers,
    save_provider,
    test_provider as run_provider_test,
)
from app.services.ai_models import (
    AIModelServiceError,
    check_model_availability,
    create_model,
    delete_model,
    list_models,
    set_default_model,
    update_model,
)

from .settings_schemas import (
    SettingsAccessResponse,
    SettingsPreferencesResponse,
    SettingsPreferencesUpdate,
    ApplicationSettingItem,
    ApplicationSettingsResponse,
    ApplicationSettingValueRequest,
    CredentialMetadata,
    CredentialValueRequest,
    CredentialsResponse,
    ProviderSaveRequest,
    ProviderSummary,
    ProviderTestResponse,
    ProvidersResponse,
    AuditLogActor,
    AuditLogCategory,
    AuditLogItem,
    AuditLogsResponse,
    ModelSummary,
    ModelsResponse,
    ModelWriteRequest,
)

router = APIRouter()

AuditResultFilter = Literal["requested", "pending", "success", "succeeded", "failure", "failed", "unknown", "denied"]

SENSITIVE_CONTEXT_TERMS = (
    "secret",
    "token",
    "password",
    "credential",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "kubeconfig",
    "prompt",
    "messages",
    "raw",
)

ACTION_CATEGORY_PREFIXES: dict[AuditLogCategory, tuple[str, ...]] = {
    "admin": (
        "USER_",
        "cluster.",
        "settings.",
        "credential.",
        "integration.",
    ),
    "resource": (
        "resource.",
    ),
    "helm": (
        "marketplace.",
        "helm.",
    ),
    "ai": (
        "assistant.",
        "ai_model.",
    ),
    "other": (),
}


def _audit_category(action: str) -> AuditLogCategory:
    for category, prefixes in ACTION_CATEGORY_PREFIXES.items():
        if category == "other":
            continue
        if any(action.startswith(prefix) for prefix in prefixes):
            return category
    return "other"


def _category_filter(category: AuditLogCategory):
    prefixes = ACTION_CATEGORY_PREFIXES[category]
    if category == "other":
        known_prefixes = [prefix for values in ACTION_CATEGORY_PREFIXES.values() for prefix in values]
        return ~or_(*(AuditAction.action.startswith(prefix) for prefix in known_prefixes))
    return or_(*(AuditAction.action.startswith(prefix) for prefix in prefixes))


def _redact_context(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if any(term in str(key).lower() for term in SENSITIVE_CONTEXT_TERMS):
                redacted[str(key)] = "[redacted]"
            else:
                redacted[str(key)] = _redact_context(item)
        return redacted
    if isinstance(value, list):
        return [_redact_context(item) for item in value]
    return value


def _safe_context(context: str | None) -> Any:
    if context is None:
        return None
    try:
        parsed = json.loads(context)
    except json.JSONDecodeError:
        return {"value": "[redacted]" if any(term in context.lower() for term in SENSITIVE_CONTEXT_TERMS) else context}
    return _redact_context(parsed)


def _actor_summary(user: UserAccount | None) -> AuditLogActor | None:
    if user is None:
        return None
    return AuditLogActor(id=user.id, email=user.email)


def _audit_item(row: AuditAction, users: dict[UUID, UserAccount]) -> AuditLogItem:
    return AuditLogItem(
        id=row.id,
        created_at=row.created_at,
        actor=_actor_summary(users.get(row.actor_id) if row.actor_id else None),
        action=row.action,
        category=_audit_category(row.action),
        resource_type=row.resource_type,
        resource_id=row.resource_id,
        target_user=_actor_summary(users.get(row.target_user_id) if row.target_user_id else None),
        result=row.result,
        context=_safe_context(row.context),
    )


@router.get("/settings/access", response_model=SettingsAccessResponse)
def settings_access(
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.SETTINGS_READ))],
) -> SettingsAccessResponse:
    return SettingsAccessResponse(allowed=True)


@router.get("/settings/audit-logs", response_model=AuditLogsResponse)
def audit_logs(
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.SETTINGS_READ))],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
    page: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    category: AuditLogCategory | None = None,
    result: AuditResultFilter | None = None,
    actor: Annotated[str | None, Query(min_length=1, max_length=255)] = None,
    resource_type: Annotated[str | None, Query(min_length=1, max_length=128)] = None,
    action: Annotated[str | None, Query(min_length=1, max_length=128)] = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> AuditLogsResponse:
    filters = []
    if category:
        filters.append(_category_filter(category))
    if result:
        filters.append(AuditAction.result == result)
    if resource_type:
        filters.append(AuditAction.resource_type == resource_type)
    if action:
        filters.append(AuditAction.action.ilike(f"%{action.strip()}%"))
    if date_from:
        filters.append(AuditAction.created_at >= date_from)
    if date_to:
        filters.append(AuditAction.created_at <= date_to)
    if actor:
        actor_match = f"%{actor.strip()}%"
        matching_users = select(UserAccount.id).where(UserAccount.email.ilike(actor_match))
        filters.append(AuditAction.actor_id.in_(matching_users))

    base = select(AuditAction)
    count_query = select(func.count()).select_from(AuditAction)
    for condition in filters:
        base = base.where(condition)
        count_query = count_query.where(condition)

    total = database.scalar(count_query) or 0
    rows = list(
        database.scalars(
            base.order_by(AuditAction.created_at.desc(), AuditAction.id.desc())
            .offset(page * limit)
            .limit(limit)
        )
    )
    user_ids = {row.actor_id for row in rows if row.actor_id} | {row.target_user_id for row in rows if row.target_user_id}
    users = {
        user.id: user
        for user in database.scalars(select(UserAccount).where(UserAccount.id.in_(user_ids))).all()
    } if user_ids else {}

    return AuditLogsResponse(
        logs=[_audit_item(row, users) for row in rows],
        page=page,
        limit=limit,
        total=total,
        total_pages=max(1, math.ceil(total / limit)),
    )


@router.get("/settings/preferences", response_model=SettingsPreferencesResponse)
def settings_preferences(
    actor: Annotated[AuthenticatedActor, Depends(get_current_actor)],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> SettingsPreferencesResponse:
    return get_user_preferences(database, actor.user_id)


@router.patch("/settings/preferences", response_model=SettingsPreferencesResponse)
def update_settings_preferences(
    changes: SettingsPreferencesUpdate,
    actor: Annotated[AuthenticatedActor, Depends(get_current_actor)],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> SettingsPreferencesResponse:
    return update_user_preferences(database, actor.user_id, changes)


def _settings_service_error(error: SettingsServiceError) -> HTTPException:
    return HTTPException(
        status_code=error.status_code,
        detail={"code": error.code, "message": str(error)},
    )


@router.get("/settings/configuration", response_model=ApplicationSettingsResponse)
def application_settings(
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.SETTINGS_READ))],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> ApplicationSettingsResponse:
    return ApplicationSettingsResponse(settings=list_application_settings(database))


@router.put("/settings/configuration/{key}", response_model=ApplicationSettingItem)
def update_application_setting(
    key: str,
    changes: ApplicationSettingValueRequest,
    actor: Annotated[AuthenticatedActor, Depends(require_permission(Permission.SETTINGS_WRITE))],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> ApplicationSettingItem:
    try:
        return upsert_application_setting(database, actor.user_id, key, changes.value)
    except SettingsServiceError as error:
        raise _settings_service_error(error) from error


@router.delete("/settings/configuration/{key}", response_model=ApplicationSettingItem)
def remove_application_setting(
    key: str,
    actor: Annotated[AuthenticatedActor, Depends(require_permission(Permission.SETTINGS_WRITE))],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> ApplicationSettingItem:
    try:
        return delete_application_setting(database, actor.user_id, key)
    except SettingsServiceError as error:
        raise _settings_service_error(error) from error


@router.get("/settings/credentials", response_model=CredentialsResponse)
def credential_metadata(
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.SETTINGS_READ))],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> CredentialsResponse:
    return CredentialsResponse(credentials=list_credential_metadata(database))


@router.put("/settings/credentials/{credential_key}", response_model=CredentialMetadata)
def put_credential(
    credential_key: str,
    changes: CredentialValueRequest,
    actor: Annotated[AuthenticatedActor, Depends(require_permission(Permission.SETTINGS_WRITE))],
    settings: Annotated[Settings, Depends(get_settings)],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> CredentialMetadata:
    try:
        return replace_credential(database, settings, actor.user_id, credential_key, changes.value)
    except SettingsServiceError as error:
        raise _settings_service_error(error) from error


@router.delete("/settings/credentials/{credential_key}", response_model=CredentialMetadata)
def remove_credential(
    credential_key: str,
    actor: Annotated[AuthenticatedActor, Depends(require_permission(Permission.SETTINGS_WRITE))],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> CredentialMetadata:
    try:
        return delete_credential(database, actor.user_id, credential_key)
    except SettingsServiceError as error:
        raise _settings_service_error(error) from error


def _provider_service_error(error: ProviderServiceError) -> HTTPException:
    return HTTPException(
        status_code=error.status_code,
        detail={"code": error.code, "message": str(error)},
    )


@router.get("/settings/providers", response_model=ProvidersResponse)
def providers(
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.SETTINGS_READ))],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> ProvidersResponse:
    return ProvidersResponse(providers=list_providers(database))


@router.put("/settings/providers/{provider_id}", response_model=ProviderSummary)
def update_provider(
    provider_id: str,
    changes: ProviderSaveRequest,
    actor: Annotated[AuthenticatedActor, Depends(require_permission(Permission.SETTINGS_WRITE))],
    settings: Annotated[Settings, Depends(get_settings)],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> ProviderSummary:
    try:
        return save_provider(
            database,
            settings,
            actor.user_id,
            provider_id,
            changes.base_url,
            changes.api_key_action,
            changes.api_key,
        )
    except ProviderServiceError as error:
        raise _provider_service_error(error) from error


@router.post("/settings/providers/{provider_id}/test", response_model=ProviderTestResponse)
def test_configured_provider(
    provider_id: str,
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.SETTINGS_WRITE))],
    settings: Annotated[Settings, Depends(get_settings)],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> ProviderTestResponse:
    try:
        return run_provider_test(database, settings, provider_id)
    except ProviderServiceError as error:
        raise _provider_service_error(error) from error


def _model_service_error(error: AIModelServiceError) -> HTTPException:
    return HTTPException(
        status_code=error.status_code,
        detail={"code": error.code, "message": str(error)},
    )


@router.get("/settings/models", response_model=ModelsResponse)
def models(
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.SETTINGS_READ))],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> ModelsResponse:
    return ModelsResponse(models=list_models(database))


@router.post("/settings/models", response_model=ModelSummary, status_code=201)
def add_model(
    changes: ModelWriteRequest,
    actor: Annotated[AuthenticatedActor, Depends(require_permission(Permission.SETTINGS_WRITE))],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> ModelSummary:
    try:
        return create_model(database, actor.user_id, **changes.model_dump())
    except AIModelServiceError as error:
        raise _model_service_error(error) from error


@router.put("/settings/models/{model_id}", response_model=ModelSummary)
def put_model(
    model_id: UUID,
    changes: ModelWriteRequest,
    actor: Annotated[AuthenticatedActor, Depends(require_permission(Permission.SETTINGS_WRITE))],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> ModelSummary:
    try:
        return update_model(database, actor.user_id, model_id, **changes.model_dump())
    except AIModelServiceError as error:
        raise _model_service_error(error) from error


@router.delete("/settings/models/{model_id}", response_model=ModelSummary)
def remove_model(
    model_id: UUID,
    actor: Annotated[AuthenticatedActor, Depends(require_permission(Permission.SETTINGS_WRITE))],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> ModelSummary:
    try:
        return delete_model(database, actor.user_id, model_id)
    except AIModelServiceError as error:
        raise _model_service_error(error) from error


@router.post("/settings/models/{model_id}/check", response_model=ModelSummary)
def check_model(
    model_id: UUID,
    actor: Annotated[AuthenticatedActor, Depends(require_permission(Permission.SETTINGS_WRITE))],
    settings: Annotated[Settings, Depends(get_settings)],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> ModelSummary:
    try:
        return check_model_availability(database, settings, actor.user_id, model_id)
    except AIModelServiceError as error:
        raise _model_service_error(error) from error


@router.post("/settings/models/{model_id}/default", response_model=ModelSummary)
def make_default_model(
    model_id: UUID,
    actor: Annotated[AuthenticatedActor, Depends(require_permission(Permission.SETTINGS_WRITE))],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> ModelSummary:
    try:
        return set_default_model(database, actor.user_id, model_id)
    except AIModelServiceError as error:
        raise _model_service_error(error) from error
