from datetime import datetime, timezone
from dataclasses import replace
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.integrations import router
from app.core.audit import AuditEvent
from app.core.config import Settings
from app.core.dependencies import AuthenticatedActor, get_current_actor, get_database_session, get_settings
from app.integrations.base import ConnectionIdentity, IntegrationProviderError, OAuthTokenSet
from app.models.base import Base
from app.models.entities import AuditAction, IntegrationConnection, IntegrationOAuthState, UserAccount
from app.services import integrations as service
from app.services import application_settings as credential_service


class FakeAdapter:
    def __init__(self, provider_id: str) -> None:
        self.provider_id = provider_id
        self.display_name = {"slack": "Slack", "gmail": "Gmail", "outlook": "Microsoft Outlook"}[provider_id]
        credential_namespace = {"slack": "slack", "gmail": "google", "outlook": "microsoft"}[provider_id]
        self.client_id_credential_key = f"integration.{credential_namespace}.client_id"
        self.client_secret_credential_key = f"integration.{credential_namespace}.client_secret"
        self.required_scopes = ("scope.send",)
        self.revoked = False

    def build_authorization_url(self, client_id: str, redirect_uri: str, state: str) -> str:
        return f"https://provider.test/authorize?client_id={client_id}&redirect_uri={redirect_uri}&state={state}"

    def exchange_code(self, client_id, client_secret, code, redirect_uri, *, client=None) -> OAuthTokenSet:
        assert (client_id, client_secret, code, redirect_uri) == (
            "client-id",
            "client-secret",
            "auth-code",
            "https://kubepilot.example/api/settings/integrations/slack/callback",
        )
        return OAuthTokenSet("access-token", "refresh-token", 3600, self.required_scopes)

    def identify(self, access_token: str, *, client=None) -> ConnectionIdentity:
        if access_token not in {"access-token", "manual-bot-token"}:
            raise IntegrationProviderError("integration_provider_unauthorized")
        return ConnectionIdentity("external-1", "Connected account", self.required_scopes)

    def refresh(self, client_id, client_secret, refresh_token, *, client=None) -> OAuthTokenSet:
        return OAuthTokenSet("refreshed-access", refresh_token, 3600, self.required_scopes)

    def revoke(self, access_token: str, *, client=None) -> None:
        assert access_token in {"access-token", "manual-bot-token", "refreshed-access"}
        self.revoked = True


@pytest.fixture()
def integration_api(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    user_id = uuid4()
    with factory() as database:
        database.add(UserAccount(id=user_id, email="admin@example.com", password_hash="hash", role="admin"))
        database.commit()

    settings = Settings(
        auth_secret="a" * 32,
        database_url="sqlite://",
        encryption_key=Fernet.generate_key().decode("ascii"),
        public_url="https://kubepilot.example",
    )
    for key, value in (
        ("integration.slack.client_id", "client-id"),
        ("integration.slack.client_secret", "client-secret"),
    ):
        with factory() as database:
            credential_service.replace_credential(database, settings, user_id, key, value)

    adapters = {provider: FakeAdapter(provider) for provider in ("slack", "gmail", "outlook")}
    monkeypatch.setattr(
        service,
        "get_adapter",
        lambda provider: adapters[provider]
        if provider in adapters
        else (_ for _ in ()).throw(IntegrationProviderError("integration_not_supported", "This integration is not supported yet")),
    )
    actor = AuthenticatedActor("admin@example.com", "admin", user_id=user_id)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_current_actor] = lambda: actor
    app.dependency_overrides[get_settings] = lambda: settings

    def database_dependency():
        database = factory()
        try:
            yield database
        finally:
            database.close()

    app.dependency_overrides[get_database_session] = database_dependency
    return TestClient(app), factory, settings, adapters, actor


def test_list_is_metadata_only_and_catalog_only_providers_are_not_supported(integration_api) -> None:
    client, _factory, _settings, _adapters, _actor = integration_api

    response = client.get("/api/v1/settings/integrations")

    assert response.status_code == 200
    payload = {item["provider_id"]: item for item in response.json()["integrations"]}
    assert payload["slack"]["supported"] is True
    assert payload["slack"]["configured"] is True
    assert payload["slack"]["manual_token_configured"] is False
    assert payload["slack"]["status"] == "not_connected"
    assert payload["teams"] == {
        "provider_id": "teams",
        "name": "Microsoft Teams",
        "supported": False,
        "configured": False,
        "manual_token_configured": False,
        "status": "not_supported",
        "external_account_label": None,
        "granted_scopes": [],
        "last_tested_at": None,
        "last_error_code": None,
    }


def test_manual_slack_token_connects_without_public_url_and_redacts_token(integration_api) -> None:
    client, factory, settings, _adapters, actor = integration_api
    with factory() as database:
        credential_service.delete_credential(database, actor.user_id, "integration.slack.client_id")
        credential_service.delete_credential(database, actor.user_id, "integration.slack.client_secret")
        credential_service.replace_credential(
            database,
            settings,
            actor.user_id,
            "integration.slack.bot_token",
            "manual-bot-token",
        )

    client.app.dependency_overrides[get_settings] = lambda: replace(settings, public_url=None)
    response = client.post("/api/v1/settings/integrations/slack/connect")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider_id"] == "slack"
    assert payload["status"] == "connected"
    assert payload["manual_token_configured"] is True
    assert "manual-bot-token" not in response.text

    with factory() as database:
        connection = database.scalar(select(IntegrationConnection))
        audit = database.scalar(
            select(AuditAction).where(AuditAction.action == AuditEvent.INTEGRATION_CONNECTED)
        )
        assert connection is not None
        assert connection.access_token_ciphertext != "manual-bot-token"
        assert audit is not None and "manual-bot-token" not in (audit.context or "")


def test_invalid_manual_slack_token_does_not_create_connection(integration_api) -> None:
    client, factory, settings, _adapters, actor = integration_api
    with factory() as database:
        credential_service.replace_credential(
            database,
            settings,
            actor.user_id,
            "integration.slack.bot_token",
            "invalid-bot-token",
        )

    client.app.dependency_overrides[get_settings] = lambda: replace(settings, public_url=None)
    response = client.post("/api/v1/settings/integrations/slack/connect")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "integration_provider_unauthorized"
    with factory() as database:
        assert database.scalar(select(IntegrationConnection)) is None
        audits = database.scalars(
            select(AuditAction).where(AuditAction.action == AuditEvent.INTEGRATION_MANUAL_CONNECTION_FAILED)
        ).all()
        assert audits
        assert "invalid-bot-token" not in "".join(audit.context or "" for audit in audits)


def test_manual_slack_disconnect_preserves_token_for_reconnect(integration_api) -> None:
    client, factory, settings, adapters, actor = integration_api
    with factory() as database:
        credential_service.delete_credential(database, actor.user_id, "integration.slack.client_id")
        credential_service.delete_credential(database, actor.user_id, "integration.slack.client_secret")
        credential_service.replace_credential(
            database,
            settings,
            actor.user_id,
            "integration.slack.bot_token",
            "manual-bot-token",
        )

    client.app.dependency_overrides[get_settings] = lambda: replace(settings, public_url=None)
    connected = client.post("/api/v1/settings/integrations/slack/connect")
    assert connected.status_code == 200

    disconnected = client.delete("/api/v1/settings/integrations/slack")
    assert disconnected.status_code == 200
    assert disconnected.json()["status"] == "revoked"
    assert adapters["slack"].revoked is False

    reconnected = client.post("/api/v1/settings/integrations/slack/connect")
    assert reconnected.status_code == 200
    assert reconnected.json()["status"] == "connected"

    with factory() as database:
        connection = database.scalar(select(IntegrationConnection))
        assert connection is not None
        assert connection.status == "connected"
        assert connection.access_token_ciphertext is not None


def test_manual_slack_connect_requires_settings_write(integration_api) -> None:
    client, _factory, settings, _adapters, _actor = integration_api
    client.app.dependency_overrides[get_current_actor] = lambda: AuthenticatedActor(
        "operator@example.com",
        "operator",
    )
    client.app.dependency_overrides[get_settings] = lambda: replace(settings, public_url=None)

    response = client.post("/api/v1/settings/integrations/slack/connect")

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "insufficient_permissions"


def test_oauth_callback_is_one_use_and_persists_only_ciphertext(integration_api) -> None:
    client, factory, settings, _adapters, actor = integration_api

    start = client.post("/api/v1/settings/integrations/slack/authorize")
    assert start.status_code == 200
    authorization_url = start.json()["authorization_url"]
    state = parse_qs(urlparse(authorization_url).query)["state"][0]

    with factory() as database:
        connection = database.scalar(select(IntegrationConnection))
        assert connection is not None
        assert connection.status == "authorizing"

    callback = client.get(f"/api/v1/settings/integrations/slack/callback?state={state}&code=auth-code")
    assert callback.status_code == 200
    assert callback.json() == {
        "provider_id": "slack",
        "status": "connected",
        "connected": True,
        "message": "The integration is connected",
        "error_code": None,
    }

    with factory() as database:
        connection = database.scalar(select(IntegrationConnection))
        oauth_state = database.scalar(select(IntegrationOAuthState))
        audit = database.scalar(select(AuditAction).where(AuditAction.action == AuditEvent.INTEGRATION_CONNECTED))
        assert connection is not None
        assert connection.access_token_ciphertext != "access-token"
        assert connection.refresh_token_ciphertext != "refresh-token"
        assert connection.external_account_label == "Connected account"
        assert oauth_state is not None and oauth_state.consumed_at is not None
        assert audit is not None and "access-token" not in (audit.context or "")
        assert str(actor.user_id) == str(oauth_state.actor_id)

    replay = client.get(f"/api/v1/settings/integrations/slack/callback?state={state}&code=auth-code")
    assert replay.status_code == 400
    assert replay.json()["detail"]["code"] == "integration_state_invalid"


def test_test_and_disconnect_are_audited_and_clear_local_tokens(integration_api) -> None:
    client, factory, _settings, adapters, _actor = integration_api
    start = client.post("/api/v1/settings/integrations/slack/authorize")
    state = parse_qs(urlparse(start.json()["authorization_url"]).query)["state"][0]
    assert client.get(f"/api/v1/settings/integrations/slack/callback?state={state}&code=auth-code").status_code == 200

    tested = client.post("/api/v1/settings/integrations/slack/test")
    assert tested.status_code == 200
    assert tested.json()["status"] == "connected"
    disconnected = client.delete("/api/v1/settings/integrations/slack")
    assert disconnected.status_code == 200
    assert disconnected.json()["status"] == "revoked"
    assert adapters["slack"].revoked is True

    with factory() as database:
        connection = database.scalar(select(IntegrationConnection))
        actions = {row.action for row in database.scalars(select(AuditAction)).all()}
        assert connection is not None
        assert connection.access_token_ciphertext is None
        assert connection.refresh_token_ciphertext is None
        assert AuditEvent.INTEGRATION_TEST_SUCCEEDED in actions
        assert AuditEvent.INTEGRATION_DISCONNECTED in actions


def test_operator_cannot_read_integration_settings(integration_api) -> None:
    client, _factory, _settings, _adapters, _actor = integration_api
    client.app.dependency_overrides[get_current_actor] = lambda: AuthenticatedActor("operator@example.com", "operator")

    response = client.get("/api/v1/settings/integrations")

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "insufficient_permissions"


def test_expired_state_and_catalog_only_provider_are_rejected(integration_api) -> None:
    client, factory, _settings, _adapters, _actor = integration_api
    start = client.post("/api/v1/settings/integrations/slack/authorize")
    state = parse_qs(urlparse(start.json()["authorization_url"]).query)["state"][0]
    with factory() as database:
        oauth_state = database.scalar(select(IntegrationOAuthState))
        assert oauth_state is not None
        oauth_state.expires_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
        database.commit()

    expired = client.get(f"/api/v1/settings/integrations/slack/callback?state={state}&code=auth-code")
    assert expired.status_code == 400
    assert expired.json()["detail"]["code"] == "integration_state_expired"

    unsupported = client.post("/api/v1/settings/integrations/teams/authorize")
    assert unsupported.status_code == 422
    assert unsupported.json()["detail"]["code"] == "integration_not_supported"
