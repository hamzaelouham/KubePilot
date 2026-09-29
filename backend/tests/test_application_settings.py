from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.settings import router
from app.core.config import ConfigurationError, Settings
from app.core.dependencies import AuthenticatedActor, get_current_actor, get_database_session, get_settings
from app.core.rbac import Permission, has_permission
from app.models.base import Base
from app.models.entities import ApplicationCredential, AuditAction, UserAccount
from app.services import application_settings as service


def test_integration_oauth_credentials_are_fixed_registered_keys() -> None:
    expected = {
        "integration.slack.client_id",
        "integration.slack.client_secret",
        "integration.slack.bot_token",
        "integration.google.client_id",
        "integration.google.client_secret",
        "integration.microsoft.client_id",
        "integration.microsoft.client_secret",
    }
    assert expected <= set(service.CREDENTIAL_DEFINITIONS)
    assert all(service.CREDENTIAL_DEFINITIONS[key].category == "integration" for key in expected)


@pytest.fixture()
def settings_store(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    user_id = uuid4()
    with factory() as database:
        database.add(UserAccount(id=user_id, email="admin@example.com", password_hash="hash", role="admin"))
        database.commit()

    monkeypatch.setattr(
        service,
        "SETTING_DEFINITIONS",
        {"safe.runtime": service.SettingDefinition("safe.runtime", default={"enabled": False})},
    )
    monkeypatch.setattr(
        service,
        "CREDENTIAL_DEFINITIONS",
        {
            "provider.api_key": service.CredentialDefinition(
                key="provider.api_key",
                display_name="Provider API key",
                description="API key used by the test provider.",
                category="provider",
            )
        },
    )
    settings = Settings(
        auth_secret="a" * 32,
        database_url="sqlite://",
        encryption_key=Fernet.generate_key().decode("ascii"),
    )
    return factory, user_id, settings


@pytest.fixture()
def settings_api(settings_store):
    factory, user_id, settings = settings_store
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
    return TestClient(app), factory, settings, app


def test_credential_persists_ciphertext_and_redacted_audit(settings_store) -> None:
    factory, user_id, settings = settings_store
    secret = "sk-live-value"

    with factory() as database:
        result = service.replace_credential(database, settings, user_id, "provider.api_key", secret)
        assert result["credential_key"] == "provider.api_key"
        assert result["display_name"] == "Provider API key"
        assert result["description"] == "API key used by the test provider."
        assert result["category"] == "provider"
        assert result["configured"] is True
        assert "value" not in result
        assert "ciphertext" not in result
        assert service.read_credential_value(database, settings, "provider.api_key") == secret
        row = database.scalar(select(ApplicationCredential))
        audit = database.scalar(select(AuditAction).order_by(AuditAction.created_at.desc()))

    assert row is not None
    assert row.ciphertext != secret
    assert secret not in (audit.context or "")

    with factory() as new_session:
        persisted = new_session.scalar(select(ApplicationCredential))
        assert persisted is not None
        assert persisted.ciphertext == row.ciphertext


def test_credential_metadata_lists_registered_configured_and_missing_rows(settings_store) -> None:
    factory, user_id, settings = settings_store

    with factory() as database:
        missing = service.list_credential_metadata(database)
        assert missing == [{
            "credential_key": "provider.api_key",
            "display_name": "Provider API key",
            "description": "API key used by the test provider.",
            "category": "provider",
            "configured": False,
            "updated_at": None,
        }]
        service.replace_credential(database, settings, user_id, "provider.api_key", "  exact secret  ")
        configured = service.list_credential_metadata(database)
        assert configured[0]["configured"] is True
        assert configured[0]["updated_at"] is not None
        assert service.read_credential_value(database, settings, "provider.api_key") == "  exact secret  "
        assert "exact secret" not in str(configured)


def test_credential_replace_and_delete_share_one_registered_row(settings_store) -> None:
    factory, user_id, settings = settings_store

    with factory() as database:
        service.replace_credential(database, settings, user_id, "provider.api_key", "first")
        service.replace_credential(database, settings, user_id, "provider.api_key", "second")
        rows = database.scalars(select(ApplicationCredential)).all()
        assert len(rows) == 1
        assert service.read_credential_value(database, settings, "provider.api_key") == "second"

        removed = service.delete_credential(database, user_id, "provider.api_key")
        assert removed["configured"] is False
        assert removed["updated_at"] is None
        assert database.scalar(select(ApplicationCredential)) is None

        already_missing = service.delete_credential(database, user_id, "provider.api_key")
        assert already_missing == removed


def test_unknown_and_blank_credentials_are_rejected_without_persistence(settings_store) -> None:
    factory, user_id, settings = settings_store

    with factory() as database:
        with pytest.raises(service.UnknownCredentialError):
            service.replace_credential(database, settings, user_id, "DATABASE_URL", "secret")
        with pytest.raises(service.InvalidCredentialValueError):
            service.replace_credential(database, settings, user_id, "provider.api_key", " \t\n ")
        with pytest.raises(service.UnknownCredentialError):
            service.delete_credential(database, user_id, "DATABASE_URL")
        assert database.scalar(select(ApplicationCredential)) is None


def test_credential_api_is_metadata_only_and_uses_the_shared_encrypted_row(settings_api) -> None:
    client, factory, settings, _app = settings_api
    secret = "  api-secret  "

    with client as api:
        initial = api.get("/api/v1/settings/credentials")
        assert initial.status_code == 200
        assert initial.json()["credentials"][0]["configured"] is False

        saved = api.put("/api/v1/settings/credentials/provider.api_key", json={"value": secret})
        assert saved.status_code == 200
        assert saved.json()["configured"] is True
        assert secret not in saved.text
        assert "ciphertext" not in saved.text

        blank = api.put("/api/v1/settings/credentials/provider.api_key", json={"value": " \t "})
        assert blank.status_code == 422
        assert blank.json()["detail"]["code"] == "invalid_credential_value"

        unknown = api.put("/api/v1/settings/credentials/DATABASE_URL", json={"value": "unsafe"})
        assert unknown.status_code == 404
        assert unknown.json()["detail"]["code"] == "credential_not_found"

        removed = api.delete("/api/v1/settings/credentials/provider.api_key")
        assert removed.status_code == 200
        assert removed.json()["configured"] is False

    with factory() as database:
        assert service.read_credential_value(database, settings, "provider.api_key") is None
        audits = database.scalars(select(AuditAction)).all()
        assert audits
        assert secret not in "".join(audit.context or "" for audit in audits)


@pytest.mark.parametrize("role", ["operator", "viewer"])
def test_credential_api_denies_non_admin_roles(settings_api, role: str) -> None:
    client, _factory, _settings, app = settings_api
    app.dependency_overrides[get_current_actor] = lambda: AuthenticatedActor(f"{role}@example.com", role, user_id=uuid4())

    with client as api:
        assert api.get("/api/v1/settings/credentials").status_code == 403
        assert api.put("/api/v1/settings/credentials/provider.api_key", json={"value": "secret"}).status_code == 403
        assert api.delete("/api/v1/settings/credentials/provider.api_key").status_code == 403


def test_credential_api_requires_authentication(settings_api) -> None:
    client, _factory, _settings, app = settings_api

    def unauthenticated():
        raise HTTPException(status_code=401, detail={"code": "not_authenticated", "message": "Authentication required"})

    app.dependency_overrides[get_current_actor] = unauthenticated
    with client as api:
        assert api.get("/api/v1/settings/credentials").status_code == 401


def test_missing_encryption_key_fails_before_credential_persistence(settings_store) -> None:
    factory, user_id, settings = settings_store
    unavailable = Settings(auth_secret=settings.auth_secret, database_url=settings.database_url)

    with factory() as database:
        with pytest.raises(ConfigurationError) as error:
            service.replace_credential(database, unavailable, user_id, "provider.api_key", "secret")
        assert "KUBEPILOT_ENCRYPTION_KEY" in str(error.value)
        assert database.scalar(select(ApplicationCredential)) is None


def test_credential_commit_failure_rolls_back_secret_and_audit(settings_store, monkeypatch: pytest.MonkeyPatch) -> None:
    factory, user_id, settings = settings_store

    with factory() as database:
        def fail_commit():
            raise RuntimeError("database unavailable")

        monkeypatch.setattr(database, "commit", fail_commit)
        with pytest.raises(RuntimeError, match="database unavailable"):
            service.replace_credential(database, settings, user_id, "provider.api_key", "secret")

    with factory() as database:
        assert database.scalar(select(ApplicationCredential)) is None
        assert database.scalar(select(AuditAction)) is None


def test_global_settings_write_permission_is_admin_only(settings_store) -> None:
    _factory, _user_id, _settings = settings_store

    assert has_permission("admin", Permission.SETTINGS_WRITE) is True
    assert has_permission("operator", Permission.SETTINGS_WRITE) is False
    assert has_permission("viewer", Permission.SETTINGS_WRITE) is False


def test_unknown_setting_is_rejected_without_mass_assignment(settings_store) -> None:
    factory, user_id, _settings = settings_store

    with factory() as database:
        with pytest.raises(service.UnknownSettingError):
            service.upsert_application_setting(database, user_id, "DATABASE_URL", "sqlite://")
        assert database.scalar(select(service.ApplicationSetting)) is None
