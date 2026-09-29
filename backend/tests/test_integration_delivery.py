from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.audit import AuditEvent
from app.core.config import Settings
from app.core.dependencies import AuthenticatedActor, get_current_actor, get_database_session, get_settings
from app.integrations.base import DeliveryReceipt, IntegrationProviderError
from app.models.base import Base
from app.models.entities import AuditAction, IntegrationConnection, IntegrationDeliveryJob, UserAccount
from app.api.v1.integrations import router
from app.services import integration_delivery as delivery
from app.services.credential_encryption import CredentialEncryption
from app.jobs import integration_delivery_worker as worker


class FakeDeliveryAdapter:
    provider_id = "slack"
    display_name = "Slack"
    client_id_credential_key = "integration.slack.client_id"
    client_secret_credential_key = "integration.slack.client_secret"
    required_scopes = ("chat:write",)

    def __init__(self) -> None:
        self.calls = 0
        self.failure: IntegrationProviderError | None = None

    def validate_destination(self, destination: str) -> None:
        if destination != "C123":
            raise IntegrationProviderError("integration_delivery_invalid")

    def send(self, access_token, destination, subject, body, *, client=None) -> DeliveryReceipt:
        self.calls += 1
        if self.failure:
            raise self.failure
        assert (access_token, destination, subject, body) == ("access-token", "C123", "Subject", "Body")
        return DeliveryReceipt("receipt-1")


@pytest.fixture()
def delivery_context(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    settings = Settings(
        auth_secret="a" * 32,
        database_url="sqlite://",
        encryption_key=Fernet.generate_key().decode("ascii"),
        public_url="https://kubepilot.example",
    )
    adapter = FakeDeliveryAdapter()
    monkeypatch.setattr(delivery, "get_adapter", lambda _provider: adapter)
    with factory() as database:
        encryption = CredentialEncryption.from_settings(settings)
        database.add(
            IntegrationConnection(
                provider="slack",
                status="connected",
                access_token_ciphertext=encryption.encrypt("access-token"),
                granted_scopes=["chat:write"],
            )
        )
        database.commit()
    return factory, settings, adapter


def request(key: str) -> delivery.IntegrationDeliveryRequest:
    return delivery.IntegrationDeliveryRequest(
        idempotency_key=key,
        provider_id="slack",
        event_type="workload.failed",
        destination="C123",
        subject="Subject",
        body="Body",
    )


def test_enqueue_encrypts_payload_and_deduplicates(delivery_context) -> None:
    factory, settings, _adapter = delivery_context
    with factory() as database:
        first = delivery.enqueue_delivery(database, settings, request("event-1"))
        second = delivery.enqueue_delivery(database, settings, request("event-1"))
        row = database.scalar(select(IntegrationDeliveryJob))
        assert first["deduplicated"] is False
        assert second["deduplicated"] is True
        assert row is not None
        assert "Subject" not in row.payload_ciphertext
        assert "Body" not in row.payload_ciphertext
        assert first["status"] == "queued"
        audit = database.scalar(select(AuditAction).where(AuditAction.action == AuditEvent.INTEGRATION_DELIVERY_QUEUED))
        assert audit is not None
        assert "Body" not in (audit.context or "")


def test_worker_delivers_once_and_records_success(delivery_context) -> None:
    factory, settings, adapter = delivery_context
    with factory() as database:
        queued = delivery.enqueue_delivery(database, settings, request("event-2"))
        worker.run_pending_deliveries(database, settings)
        row = database.get(IntegrationDeliveryJob, queued["delivery_id"])
        assert row is not None and row.status == "succeeded"
        assert row.attempt_count == 1
        assert adapter.calls == 1
        audit = database.scalar(select(AuditAction).where(AuditAction.action == AuditEvent.INTEGRATION_DELIVERY_SUCCEEDED))
        assert audit is not None


def test_worker_retries_transient_failure_with_bounded_attempts(delivery_context) -> None:
    factory, settings, adapter = delivery_context
    adapter.failure = IntegrationProviderError("integration_provider_rate_limited", retryable=True)
    with factory() as database:
        queued = delivery.enqueue_delivery(database, settings, request("event-3"))
        worker.run_pending_deliveries(database, settings)
        row = database.get(IntegrationDeliveryJob, queued["delivery_id"])
        assert row is not None and row.status == "queued"
        assert row.attempt_count == 1
        assert row.last_error_code == "integration_rate_limited"
        assert row.next_attempt_at > datetime.now(timezone.utc)
        row.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        adapter.failure = None
        database.commit()
        worker.run_pending_deliveries(database, settings)
        assert row.status == "succeeded"
        assert row.attempt_count == 2


def test_ambiguous_provider_result_is_not_retried(delivery_context) -> None:
    factory, settings, adapter = delivery_context
    adapter.failure = IntegrationProviderError("integration_provider_unavailable", outcome_unknown=True)
    with factory() as database:
        queued = delivery.enqueue_delivery(database, settings, request("event-4"))
        worker.run_pending_deliveries(database, settings)
        row = database.get(IntegrationDeliveryJob, queued["delivery_id"])
        assert row is not None and row.status == "outcome_unknown"
        assert row.last_error_code == "integration_provider_unavailable"
        assert adapter.calls == 1
        audit = database.scalar(select(AuditAction).where(AuditAction.action == AuditEvent.INTEGRATION_DELIVERY_OUTCOME_UNKNOWN))
        assert audit is not None


def test_invalid_request_and_catalog_provider_are_rejected(delivery_context, monkeypatch: pytest.MonkeyPatch) -> None:
    factory, settings, _adapter = delivery_context
    original_get_adapter = delivery.get_adapter

    def get_adapter(provider: str):
        if provider == "teams":
            raise IntegrationProviderError("integration_not_supported", "This integration is not supported yet")
        return original_get_adapter(provider)

    monkeypatch.setattr(delivery, "get_adapter", get_adapter)
    with factory() as database:
        with pytest.raises(delivery.DeliveryServiceError) as invalid:
            delivery.enqueue_delivery(database, settings, request("bad key"))
        assert invalid.value.code == "integration_delivery_invalid"
        with pytest.raises(delivery.DeliveryServiceError) as unsupported:
            delivery.enqueue_delivery(
                database,
                settings,
                delivery.IntegrationDeliveryRequest(
                    idempotency_key="event-5",
                    provider_id="teams",
                    event_type="test",
                    destination="C123",
                    body="Body",
                ),
            )
        assert unsupported.value.code == "integration_not_supported"


def test_delivery_history_and_retry_use_settings_permissions(delivery_context) -> None:
    factory, settings, adapter = delivery_context
    actor_id = uuid4()
    with factory() as database:
        database.add(UserAccount(id=actor_id, email="admin@example.com", password_hash="hash", role="admin"))
        database.commit()
        queued = delivery.enqueue_delivery(database, settings, request("event-api"))
        adapter.failure = IntegrationProviderError("integration_provider_rejected")
        worker.run_pending_deliveries(database, settings)

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_current_actor] = lambda: AuthenticatedActor("admin@example.com", "admin", user_id=actor_id)
    app.dependency_overrides[get_settings] = lambda: settings

    def database_dependency():
        database = factory()
        try:
            yield database
        finally:
            database.close()

    app.dependency_overrides[get_database_session] = database_dependency
    client = TestClient(app)
    history = client.get("/api/v1/settings/integrations/deliveries")
    assert history.status_code == 200
    assert history.json()["items"][0]["delivery_id"] == str(queued["delivery_id"])
    assert "Body" not in history.text
    retried = client.post(f"/api/v1/settings/integrations/deliveries/{queued['delivery_id']}/retry")
    assert retried.status_code == 200
    assert retried.json()["status"] == "queued"
