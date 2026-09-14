from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import ConfigurationError, Settings
from app.core.rbac import Permission, has_permission
from app.models.base import Base
from app.models.entities import ApplicationCredential, AuditAction, UserAccount
from app.services import application_settings as service


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
        {"provider.api_key": service.CredentialDefinition("provider.api_key")},
    )
    settings = Settings(
        auth_secret="a" * 32,
        database_url="sqlite://",
        encryption_key=Fernet.generate_key().decode("ascii"),
    )
    return factory, user_id, settings


def test_credential_persists_ciphertext_and_redacted_audit(settings_store) -> None:
    factory, user_id, settings = settings_store
    secret = "sk-live-value"

    with factory() as database:
        result = service.replace_credential(database, settings, user_id, "provider.api_key", secret)
        assert result["credential_key"] == "provider.api_key"
        assert result["configured"] is True
        assert "value" not in result
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


def test_missing_encryption_key_fails_before_credential_persistence(settings_store) -> None:
    factory, user_id, settings = settings_store
    unavailable = Settings(auth_secret=settings.auth_secret, database_url=settings.database_url)

    with factory() as database:
        with pytest.raises(ConfigurationError) as error:
            service.replace_credential(database, unavailable, user_id, "provider.api_key", "secret")
        assert "KUBEPILOT_ENCRYPTION_KEY" in str(error.value)
        assert database.scalar(select(ApplicationCredential)) is None


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
