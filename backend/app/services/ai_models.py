from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as SQLAlchemySession

from app.core.audit import AuditEvent, record_audit
from app.core.config import Settings
from app.models.entities import AIModelConfig
from app.services.ai_providers import (
    HTTPClientFactory,
    PROVIDER_DEFINITIONS,
    UnknownProviderError,
    fetch_provider_model_ids,
    get_provider,
    list_providers,
)


CAPABILITY_FIELDS = {
    "streaming": "supports_streaming",
    "tools": "supports_tools",
    "reasoning": "supports_reasoning",
    "vision": "supports_vision",
    "large_context": "supports_large_context",
}


class AIModelServiceError(RuntimeError):
    status_code = 422
    code = "model_error"


class AIModelNotFoundError(AIModelServiceError):
    status_code = 404
    code = "model_not_found"


class AIModelConflictError(AIModelServiceError):
    status_code = 409
    code = "model_conflict"


class DefaultModelConflictError(AIModelConflictError):
    code = "default_model_conflict"


class AIModelValidationError(AIModelServiceError):
    code = "invalid_model"


def list_models(database: SQLAlchemySession) -> list[dict[str, Any]]:
    rows = database.scalars(
        select(AIModelConfig).order_by(AIModelConfig.provider_id, AIModelConfig.friendly_name, AIModelConfig.id)
    ).all()
    return [_summary(row) for row in rows]


def create_model(
    database: SQLAlchemySession,
    actor_id: UUID,
    *,
    provider_id: str,
    external_model_id: str,
    friendly_name: str,
    enabled: bool,
    capabilities: dict[str, bool],
) -> dict[str, Any]:
    definition = _provider_definition(provider_id)
    model = AIModelConfig(
        provider_id=definition.provider_id,
        external_model_id=_clean(external_model_id, "external model ID", 255),
        friendly_name=_clean(friendly_name, "friendly name", 128),
        enabled=enabled,
        created_by_id=actor_id,
        updated_by_id=actor_id,
        **_capability_columns(capabilities),
    )
    database.add(model)
    try:
        database.flush()
        record_audit(
            database,
            AuditEvent.AI_MODEL_CREATED,
            actor_id,
            "ai_model",
            str(model.id),
            result="succeeded",
            context={"provider_id": model.provider_id, "external_model_id": model.external_model_id},
        )
        database.commit()
        database.refresh(model)
    except IntegrityError as error:
        database.rollback()
        raise AIModelConflictError("A model with this provider and external ID already exists") from error
    except Exception:
        database.rollback()
        raise
    return _summary(model)


def update_model(
    database: SQLAlchemySession,
    actor_id: UUID,
    model_id: UUID,
    *,
    provider_id: str,
    external_model_id: str,
    friendly_name: str,
    enabled: bool,
    capabilities: dict[str, bool],
) -> dict[str, Any]:
    model = _get_model(database, model_id)
    definition = _provider_definition(provider_id)
    clean_external_id = _clean(external_model_id, "external model ID", 255)
    clean_name = _clean(friendly_name, "friendly name", 128)
    identity_changed = model.provider_id != definition.provider_id or model.external_model_id != clean_external_id
    if model.is_default and (identity_changed or not enabled):
        raise DefaultModelConflictError("Select another default model before changing or disabling this model")

    model.provider_id = definition.provider_id
    model.external_model_id = clean_external_id
    model.friendly_name = clean_name
    model.enabled = enabled
    for key, value in _capability_columns(capabilities).items():
        setattr(model, key, value)
    if identity_changed:
        model.availability = "unknown"
        model.availability_message = None
        model.availability_checked_at = None
    model.updated_by_id = actor_id
    model.updated_at = _now()
    try:
        record_audit(
            database,
            AuditEvent.AI_MODEL_UPDATED,
            actor_id,
            "ai_model",
            str(model.id),
            result="succeeded",
            context={"provider_id": model.provider_id, "external_model_id": model.external_model_id},
        )
        database.commit()
        database.refresh(model)
    except IntegrityError as error:
        database.rollback()
        raise AIModelConflictError("A model with this provider and external ID already exists") from error
    except Exception:
        database.rollback()
        raise
    return _summary(model)


def delete_model(database: SQLAlchemySession, actor_id: UUID, model_id: UUID) -> dict[str, Any]:
    model = _get_model(database, model_id)
    if model.is_default:
        raise DefaultModelConflictError("Select another default model before deleting this model")
    result = _summary(model)
    database.delete(model)
    try:
        record_audit(
            database,
            AuditEvent.AI_MODEL_DELETED,
            actor_id,
            "ai_model",
            str(model.id),
            result="succeeded",
            context={"provider_id": model.provider_id, "external_model_id": model.external_model_id},
        )
        database.commit()
    except Exception:
        database.rollback()
        raise
    return result


def set_default_model(database: SQLAlchemySession, actor_id: UUID, model_id: UUID) -> dict[str, Any]:
    model = _get_model(database, model_id)
    if not model.enabled or model.availability != "available":
        raise DefaultModelConflictError("Only an enabled, available model can be the default")
    try:
        database.execute(
            update(AIModelConfig)
            .where(AIModelConfig.is_default.is_(True), AIModelConfig.id != model.id)
            .values(is_default=False, updated_by_id=actor_id, updated_at=_now())
        )
        model.is_default = True
        model.updated_by_id = actor_id
        model.updated_at = _now()
        record_audit(
            database,
            AuditEvent.AI_MODEL_DEFAULT_CHANGED,
            actor_id,
            "ai_model",
            str(model.id),
            result="succeeded",
            context={"provider_id": model.provider_id, "external_model_id": model.external_model_id},
        )
        database.commit()
        database.refresh(model)
    except Exception:
        database.rollback()
        raise
    return _summary(model)


def check_model_availability(
    database: SQLAlchemySession,
    settings: Settings,
    actor_id: UUID,
    model_id: UUID,
    *,
    client_factory: HTTPClientFactory | None = None,
) -> dict[str, Any]:
    model = _get_model(database, model_id)
    catalog = fetch_provider_model_ids(
        database,
        settings,
        model.provider_id,
        client_factory=client_factory,
    )
    if catalog.status == "connected":
        if model.external_model_id in catalog.model_ids:
            model.availability = "available"
            model.availability_message = "The model is available from the configured provider."
        else:
            model.availability = "unavailable"
            model.availability_message = "The configured provider did not report this model."
    else:
        model.availability = "unknown"
        model.availability_message = catalog.message[:512]
    model.availability_checked_at = _now()
    model.updated_by_id = actor_id
    model.updated_at = _now()
    try:
        record_audit(
            database,
            AuditEvent.AI_MODEL_AVAILABILITY_CHECKED,
            actor_id,
            "ai_model",
            str(model.id),
            result=model.availability,
            context={"provider_id": model.provider_id, "external_model_id": model.external_model_id},
        )
        database.commit()
        database.refresh(model)
    except Exception:
        database.rollback()
        raise
    return _summary(model)


def list_eligible_models(database: SQLAlchemySession) -> list[dict[str, Any]]:
    configured = {
        provider["provider_id"]
        for provider in list_providers(database)
        if provider["status"] == "configured"
    }
    rows = database.scalars(
        select(AIModelConfig)
        .where(
            AIModelConfig.enabled.is_(True),
            AIModelConfig.availability == "available",
            AIModelConfig.supports_streaming.is_(True),
            AIModelConfig.supports_tools.is_(True),
        )
        .order_by(AIModelConfig.is_default.desc(), AIModelConfig.friendly_name, AIModelConfig.id)
    ).all()
    return [_eligible_summary(row) for row in rows if row.provider_id in configured]


def _get_model(database: SQLAlchemySession, model_id: UUID) -> AIModelConfig:
    model = database.get(AIModelConfig, model_id)
    if model is None:
        raise AIModelNotFoundError("AI model not found")
    return model


def _clean(value: str, label: str, limit: int) -> str:
    clean = value.strip()
    if not clean:
        raise AIModelValidationError(f"A {label} is required")
    if len(clean) > limit:
        raise AIModelValidationError(f"The {label} is too long")
    return clean


def _capability_columns(capabilities: dict[str, bool]) -> dict[str, bool]:
    if set(capabilities) != set(CAPABILITY_FIELDS):
        raise AIModelValidationError("All supported model capabilities are required")
    if any(type(value) is not bool for value in capabilities.values()):
        raise AIModelValidationError("Model capabilities must be booleans")
    return {column: capabilities[name] for name, column in CAPABILITY_FIELDS.items()}


def _capabilities(model: AIModelConfig) -> dict[str, bool]:
    return {name: bool(getattr(model, column)) for name, column in CAPABILITY_FIELDS.items()}


def _provider_definition(provider_id: str):
    try:
        return get_provider(provider_id)
    except UnknownProviderError as error:
        raise AIModelValidationError("Provider is not registered") from error


def _summary(model: AIModelConfig) -> dict[str, Any]:
    definition = PROVIDER_DEFINITIONS[model.provider_id]
    return {
        "id": model.id,
        "provider_id": model.provider_id,
        "provider_name": definition.name,
        "external_model_id": model.external_model_id,
        "friendly_name": model.friendly_name,
        "enabled": model.enabled,
        "is_default": model.is_default,
        "capabilities": _capabilities(model),
        "availability": model.availability,
        "availability_message": model.availability_message,
        "availability_checked_at": model.availability_checked_at,
        "created_at": model.created_at,
        "updated_at": model.updated_at,
    }


def _eligible_summary(model: AIModelConfig) -> dict[str, Any]:
    summary = _summary(model)
    return {
        key: summary[key]
        for key in (
            "id",
            "provider_id",
            "provider_name",
            "external_model_id",
            "friendly_name",
            "capabilities",
            "is_default",
        )
    }


def _now() -> datetime:
    return datetime.now(timezone.utc)
