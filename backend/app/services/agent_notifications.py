"""Server-authoritative notification destinations for shared AI agents."""

from datetime import datetime, timezone
import hashlib
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.agent_schemas import AgentNotificationDestinationWrite
from app.core.audit import record_audit
from app.core.config import ConfigurationError, Settings
from app.integrations import get_adapter
from app.integrations.base import IntegrationProviderError
from app.models.entities import (
    AIAgentNotificationDestination,
    IntegrationConnection,
)
from app.services.agents import fail, get_agent
from app.services.credential_encryption import CredentialEncryption
from app.services.integration_delivery import (
    IntegrationDeliveryRequest,
    enqueue_delivery,
    destination_hint,
)


SUPPORTED_PROVIDERS = frozenset({"slack", "gmail", "outlook"})
TEST_EVENT_TYPE = "agent_notification_test"
TEST_SUBJECT = "KubePilot agent notification test"
TEST_BODY = "This is a test notification from a KubePilot agent destination."


def list_destinations(database: Session, agent_id: UUID) -> list[dict]:
    get_agent(database, agent_id)
    rows = database.execute(
        select(AIAgentNotificationDestination, IntegrationConnection.status)
        .outerjoin(
            IntegrationConnection,
            IntegrationConnection.provider == AIAgentNotificationDestination.provider,
        )
        .where(AIAgentNotificationDestination.agent_id == agent_id)
        .order_by(AIAgentNotificationDestination.label, AIAgentNotificationDestination.id)
    ).all()
    return [_destination_summary(row, connection_status) for row, connection_status in rows]


def destination_summary(database: Session, row: AIAgentNotificationDestination) -> dict:
    connection = database.scalar(
        select(IntegrationConnection).where(IntegrationConnection.provider == row.provider)
    )
    return _destination_summary(row, connection.status if connection else None)


def _destination_summary(
    row: AIAgentNotificationDestination,
    connection_status: str | None,
) -> dict:
    return {
        "id": row.id,
        "provider_id": row.provider,
        "label": row.label,
        "destination_hint": row.destination_hint,
        "enabled": row.enabled,
        "connection_status": connection_status or "not_connected",
        "updated_at": row.updated_at,
    }


def save_destination(
    database: Session,
    settings: Settings,
    actor_id: UUID,
    agent_id: UUID,
    body: AgentNotificationDestinationWrite,
    identity: UUID | None = None,
) -> dict:
    get_agent(database, agent_id)
    row = database.get(AIAgentNotificationDestination, identity) if identity else None
    if identity and (row is None or row.agent_id != agent_id):
        fail(404, "agent_notification_destination_not_found", "This notification destination no longer exists.")

    try:
        adapter = get_adapter(body.provider_id)
        normalized = adapter.normalize_destination(body.destination)
        adapter.validate_destination(normalized)
    except (KeyError, IntegrationProviderError) as error:
        code = error.code if isinstance(error, IntegrationProviderError) else "integration_delivery_invalid"
        fail(422, code, "The notification destination is invalid.")

    try:
        ciphertext = CredentialEncryption.from_settings(settings).encrypt(normalized)
    except (ConfigurationError, ValueError) as error:
        fail(503, "integration_encryption_unavailable", "Integration delivery encryption is unavailable.")

    digest = _destination_digest(body.provider_id, normalized)
    if row is None:
        row = AIAgentNotificationDestination(
            agent_id=agent_id,
            created_by_id=actor_id,
        )
        database.add(row)
        audit_action = "assistant.agent_notification_destination.create"
    else:
        audit_action = "assistant.agent_notification_destination.update"

    row.provider = body.provider_id
    row.label = body.label
    row.destination_ciphertext = ciphertext
    row.destination_digest = digest
    row.destination_hint = destination_hint(normalized)
    row.enabled = body.enabled
    row.updated_by_id = actor_id
    row.updated_at = datetime.now(timezone.utc)
    try:
        database.flush()
        record_audit(
            database,
            audit_action,
            actor_id,
            "ai_agent_notification_destination",
            str(row.id),
            result="succeeded",
            context={"agent_id": str(agent_id), "provider": row.provider, "enabled": row.enabled},
        )
        database.commit()
        database.refresh(row)
    except IntegrityError as error:
        database.rollback()
        fail(409, "agent_notification_destination_conflict", "This destination is already configured for the agent.")
    except Exception:
        database.rollback()
        raise
    return destination_summary(database, row)


def delete_destination(database: Session, actor_id: UUID, agent_id: UUID, identity: UUID) -> dict:
    row = _get_destination(database, agent_id, identity)
    try:
        database.delete(row)
        record_audit(
            database,
            "assistant.agent_notification_destination.delete",
            actor_id,
            "ai_agent_notification_destination",
            str(identity),
            result="succeeded",
            context={"agent_id": str(agent_id), "provider": row.provider},
        )
        database.commit()
    except Exception:
        database.rollback()
        raise
    return {"id": identity}


def queue_test_delivery(
    database: Session,
    settings: Settings,
    actor_id: UUID,
    agent_id: UUID,
    destination_id: UUID,
) -> dict:
    agent = get_agent(database, agent_id)
    if not agent.enabled:
        fail(409, "agent_disabled", "Enable the agent before sending a test notification.")
    row = _get_destination(database, agent_id, destination_id)
    if not row.enabled:
        fail(409, "agent_notification_destination_disabled", "Enable the destination before sending a test notification.")
    connection = database.scalar(
        select(IntegrationConnection).where(
            IntegrationConnection.provider == row.provider,
            IntegrationConnection.status == "connected",
            IntegrationConnection.access_token_ciphertext.is_not(None),
        )
    )
    if connection is None:
        fail(409, "integration_delivery_not_connected", "Connect this integration before sending a test notification.")
    try:
        destination = CredentialEncryption.from_settings(settings).decrypt(row.destination_ciphertext)
    except (ConfigurationError, ValueError):
        fail(503, "integration_encryption_unavailable", "Integration delivery encryption is unavailable.")

    return enqueue_delivery(
        database,
        settings,
        IntegrationDeliveryRequest(
            idempotency_key=uuid4().hex,
            provider_id=row.provider,
            event_type=TEST_EVENT_TYPE,
            destination=destination,
            subject=TEST_SUBJECT,
            body=TEST_BODY,
            actor_id=actor_id,
            agent_id=agent_id,
            agent_destination_id=row.id,
        ),
    )


def enqueue_agent_notification(
    database: Session,
    settings: Settings,
    *,
    actor_id: UUID | None,
    agent_id: UUID,
    destination_id: UUID,
    event_type: str,
    body: str,
    subject: str | None = None,
    idempotency_key: str | None = None,
) -> dict:
    agent = get_agent(database, agent_id)
    if not agent.enabled:
        fail(409, "agent_disabled", "The agent is disabled.")
    row = _get_destination(database, agent_id, destination_id)
    if not row.enabled:
        fail(409, "agent_notification_destination_disabled", "The notification destination is disabled.")
    try:
        destination = CredentialEncryption.from_settings(settings).decrypt(row.destination_ciphertext)
    except (ConfigurationError, ValueError):
        fail(503, "integration_encryption_unavailable", "Integration delivery encryption is unavailable.")
    return enqueue_delivery(
        database,
        settings,
        IntegrationDeliveryRequest(
            idempotency_key=idempotency_key or uuid4().hex,
            provider_id=row.provider,
            event_type=event_type,
            destination=destination,
            subject=subject,
            body=body,
            actor_id=actor_id,
            agent_id=agent_id,
            agent_destination_id=row.id,
        ),
    )


def _get_destination(database: Session, agent_id: UUID, identity: UUID) -> AIAgentNotificationDestination:
    row = database.get(AIAgentNotificationDestination, identity)
    if row is None or row.agent_id != agent_id:
        fail(404, "agent_notification_destination_not_found", "This notification destination no longer exists.")
    return row


def _destination_digest(provider: str, destination: str) -> str:
    return hashlib.sha256(f"{provider}\0{destination}".encode("utf-8")).hexdigest()
