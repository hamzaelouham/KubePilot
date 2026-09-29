"""Trusted integration delivery queue and safe status projections."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import re
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as SQLAlchemySession

from app.core.audit import AuditEvent, record_audit
from app.core.config import ConfigurationError, Settings
from app.integrations import get_adapter
from app.integrations.base import IntegrationProviderError, DeliveryReceipt
from app.models.entities import IntegrationConnection, IntegrationDeliveryJob
from app.services.credential_encryption import CredentialEncryption
from app.services.integrations import IntegrationServiceError, get_usable_access_token


MAX_ATTEMPTS = 3
BACKOFFS = (timedelta(minutes=1), timedelta(minutes=5))
MAX_BODY_LENGTH = 16_384
MAX_SUBJECT_LENGTH = 255
MAX_DESTINATION_LENGTH = 512
_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_EVENT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class DeliveryServiceError(RuntimeError):
    status_code = 422

    def __init__(self, code: str, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        if status_code is not None:
            self.status_code = status_code


class DeliveryDispatchError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool = False, outcome_unknown: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable
        self.outcome_unknown = outcome_unknown


@dataclass(frozen=True)
class IntegrationDeliveryRequest:
    idempotency_key: str
    provider_id: str
    event_type: str
    destination: str
    body: str
    subject: str | None = None
    actor_id: UUID | None = None


def enqueue_delivery(
    database: SQLAlchemySession,
    settings: Settings,
    request: IntegrationDeliveryRequest,
) -> dict[str, Any]:
    adapter = _validate_request(request)
    existing = database.scalar(
        select(IntegrationDeliveryJob).where(
            IntegrationDeliveryJob.idempotency_key == request.idempotency_key
        )
    )
    if existing is not None:
        return {**delivery_metadata(existing), "deduplicated": True}

    connection = database.scalar(
        select(IntegrationConnection).where(
            IntegrationConnection.provider == request.provider_id,
            IntegrationConnection.status == "connected",
            IntegrationConnection.access_token_ciphertext.is_not(None),
        )
    )
    if connection is None:
        raise DeliveryServiceError(
            "integration_delivery_not_connected",
            "The integration is not connected",
            status_code=409,
        )

    try:
        payload_ciphertext = _encrypt_payload(
            settings,
            {
                "destination": request.destination,
                "subject": request.subject,
                "body": request.body,
            },
        )
    except (ConfigurationError, ValueError) as error:
        raise DeliveryServiceError(
            "integration_encryption_unavailable",
            "Integration delivery encryption is unavailable",
            status_code=503,
        ) from error

    job = IntegrationDeliveryJob(
        connection_id=connection.id,
        provider=request.provider_id,
        idempotency_key=request.idempotency_key,
        event_type=request.event_type,
        destination_hint=_destination_hint(request.destination),
        payload_ciphertext=payload_ciphertext,
        status="queued",
        attempt_count=0,
        max_attempts=MAX_ATTEMPTS,
        next_attempt_at=_now(),
        actor_id=request.actor_id,
    )
    database.add(job)
    try:
        database.flush()
    except IntegrityError as error:
        database.rollback()
        existing = database.scalar(
            select(IntegrationDeliveryJob).where(
                IntegrationDeliveryJob.idempotency_key == request.idempotency_key
            )
        )
        if existing is None:
            raise DeliveryServiceError(
                "integration_delivery_duplicate",
                "The delivery could not be queued safely",
                status_code=409,
            ) from error
        return {**delivery_metadata(existing), "deduplicated": True}

    record_audit(
        database,
        AuditEvent.INTEGRATION_DELIVERY_QUEUED,
        request.actor_id,
        "integration_delivery",
        str(job.id),
        result="queued",
        context={"provider": request.provider_id, "status": "queued", "attempt_count": 0},
    )
    database.commit()
    return {**delivery_metadata(job), "deduplicated": False}


def list_delivery_jobs(
    database: SQLAlchemySession,
    *,
    provider: str | None = None,
    status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = 1,
    limit: int = 20,
) -> dict[str, Any]:
    query = select(IntegrationDeliveryJob)
    count_query = select(func.count()).select_from(IntegrationDeliveryJob)
    if provider:
        query = query.where(IntegrationDeliveryJob.provider == provider)
        count_query = count_query.where(IntegrationDeliveryJob.provider == provider)
    if status:
        if status not in {"queued", "running", "succeeded", "failed", "outcome_unknown"}:
            raise DeliveryServiceError("integration_delivery_invalid", "The delivery status filter is invalid")
        query = query.where(IntegrationDeliveryJob.status == status)
        count_query = count_query.where(IntegrationDeliveryJob.status == status)
    if date_from:
        query = query.where(IntegrationDeliveryJob.created_at >= date_from)
        count_query = count_query.where(IntegrationDeliveryJob.created_at >= date_from)
    if date_to:
        query = query.where(IntegrationDeliveryJob.created_at <= date_to)
        count_query = count_query.where(IntegrationDeliveryJob.created_at <= date_to)
    total = database.scalar(count_query) or 0
    rows = database.scalars(
        query.order_by(IntegrationDeliveryJob.created_at.desc(), IntegrationDeliveryJob.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()
    return {"items": [delivery_metadata(row) for row in rows], "total": total, "page": page, "limit": limit}


def get_delivery_job(database: SQLAlchemySession, delivery_id: UUID) -> dict[str, Any]:
    row = database.get(IntegrationDeliveryJob, delivery_id)
    if row is None:
        raise DeliveryServiceError("integration_delivery_not_found", "The delivery was not found", status_code=404)
    return delivery_metadata(row)


def retry_delivery(database: SQLAlchemySession, actor_id: UUID, delivery_id: UUID) -> dict[str, Any]:
    row = database.get(IntegrationDeliveryJob, delivery_id)
    if row is None:
        raise DeliveryServiceError("integration_delivery_not_found", "The delivery was not found", status_code=404)
    if row.status != "failed":
        raise DeliveryServiceError(
            "integration_delivery_not_retryable",
            "Only failed deliveries can be retried",
            status_code=409,
        )
    row.status = "queued"
    row.attempt_count = 0
    row.max_attempts = MAX_ATTEMPTS
    row.next_attempt_at = _now()
    row.last_error_code = None
    row.started_at = None
    row.completed_at = None
    record_audit(
        database,
        AuditEvent.INTEGRATION_DELIVERY_RETRY_REQUESTED,
        actor_id,
        "integration_delivery",
        str(row.id),
        result="queued",
        context={"provider": row.provider, "status": "queued", "attempt_count": 0},
    )
    database.commit()
    return delivery_metadata(row)


def dispatch_delivery(database: SQLAlchemySession, settings: Settings, row: IntegrationDeliveryJob) -> DeliveryReceipt:
    connection = database.get(IntegrationConnection, row.connection_id)
    if connection is None or connection.status != "connected" or not connection.access_token_ciphertext:
        raise DeliveryDispatchError("integration_delivery_not_connected")
    try:
        adapter = get_adapter(row.provider)
        payload = _decrypt_payload(settings, row.payload_ciphertext)
        access_token = get_usable_access_token(database, settings, connection, adapter)
        return adapter.send(
            access_token,
            payload["destination"],
            payload.get("subject"),
            payload["body"],
        )
    except ConfigurationError as error:
        _mark_connection_error(connection, "integration_encryption_unavailable")
        raise DeliveryDispatchError("integration_encryption_unavailable") from error
    except IntegrationServiceError as error:
        _mark_connection_error(connection, error.code)
        raise DeliveryDispatchError(error.code) from error
    except IntegrationProviderError as error:
        if error.code in {"integration_provider_unauthorized", "integration_connection_invalid", "integration_refresh_unsupported"}:
            _mark_connection_error(connection, error.code)
        raise DeliveryDispatchError(
            _delivery_error_code(error.code),
            retryable=error.retryable,
            outcome_unknown=error.outcome_unknown,
        ) from error
    except (KeyError, TypeError, ValueError) as error:
        raise DeliveryDispatchError("integration_delivery_invalid") from error


def delivery_metadata(row: IntegrationDeliveryJob) -> dict[str, Any]:
    return {
        "delivery_id": row.id,
        "provider_id": row.provider,
        "event_type": row.event_type,
        "destination_hint": row.destination_hint,
        "status": row.status,
        "attempt_count": row.attempt_count,
        "max_attempts": row.max_attempts,
        "next_attempt_at": row.next_attempt_at,
        "last_error_code": row.last_error_code,
        "created_at": row.created_at,
        "started_at": row.started_at,
        "completed_at": row.completed_at,
    }


def _validate_request(request: IntegrationDeliveryRequest):
    if not _KEY_PATTERN.fullmatch(request.idempotency_key):
        raise DeliveryServiceError("integration_delivery_invalid", "The idempotency key is invalid")
    if not _EVENT_PATTERN.fullmatch(request.event_type):
        raise DeliveryServiceError("integration_delivery_invalid", "The event type is invalid")
    if not request.destination or len(request.destination) > MAX_DESTINATION_LENGTH or "\x00" in request.destination:
        raise DeliveryServiceError("integration_delivery_invalid", "The delivery destination is invalid")
    if not request.body or len(request.body) > MAX_BODY_LENGTH or "\x00" in request.body:
        raise DeliveryServiceError("integration_delivery_invalid", "The delivery body is invalid")
    if request.subject is not None and (len(request.subject) > MAX_SUBJECT_LENGTH or "\x00" in request.subject):
        raise DeliveryServiceError("integration_delivery_invalid", "The delivery subject is invalid")
    try:
        adapter = get_adapter(request.provider_id)
        adapter.validate_destination(request.destination)
    except IntegrationProviderError as error:
        raise DeliveryServiceError(error.code, "The delivery destination is invalid") from error
    return adapter


def _encrypt_payload(settings: Settings, payload: dict[str, Any]) -> str:
    return CredentialEncryption.from_settings(settings).encrypt(json.dumps(payload, separators=(",", ":")))


def _decrypt_payload(settings: Settings, ciphertext: str) -> dict[str, Any]:
    payload = json.loads(CredentialEncryption.from_settings(settings).decrypt(ciphertext))
    if not isinstance(payload, dict):
        raise ConfigurationError("Stored delivery material is invalid")
    return payload


def _destination_hint(destination: str) -> str:
    if "@" in destination:
        local, domain = destination.split("@", 1)
        return f"{local[:1]}***@{domain}"
    return f"…{destination[-4:]}" if len(destination) > 4 else "…"


def _delivery_error_code(code: str) -> str:
    return {
        "integration_provider_rate_limited": "integration_rate_limited",
        "integration_provider_unavailable": "integration_provider_unavailable",
        "integration_provider_unauthorized": "integration_connection_invalid",
    }.get(code, code)


def _mark_connection_error(connection: IntegrationConnection, code: str) -> None:
    connection.status = "error"
    connection.last_error_code = code
    connection.updated_at = _now()


def _now() -> datetime:
    return datetime.now(timezone.utc)
