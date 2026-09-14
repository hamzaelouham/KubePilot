from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.models.base import Base
from app.models.entities import ApplicationCredential, ApplicationSetting, AuditAction, UserAccount
from app.services import ai_providers
from app.services.credential_encryption import CredentialEncryption


@pytest.fixture()
def provider_store(tmp_path: Path) -> SimpleNamespace:
    engine = create_engine(f"sqlite:///{tmp_path / 'providers.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    user_id = uuid4()
    with factory() as database:
        database.add(UserAccount(id=user_id, email="admin@example.com", password_hash="hash", role="admin"))
        database.commit()
    settings = Settings(
        auth_secret="a" * 32,
        database_url=f"sqlite:///{tmp_path / 'providers.db'}",
        encryption_key=Fernet.generate_key().decode("ascii"),
        provider_allowed_hosts=("ollama",),
    )
    return SimpleNamespace(factory=factory, user_id=user_id, settings=settings)


def _client_factory(handler):
    transport = httpx.MockTransport(handler)
    return lambda **kwargs: httpx.Client(transport=transport, **kwargs)


def test_registry_is_allowlisted_and_stable() -> None:
    assert list(ai_providers.PROVIDER_DEFINITIONS) == ["openai", "openrouter", "ollama"]
    with pytest.raises(ai_providers.UnknownProviderError):
        ai_providers.get_provider("arbitrary")


def test_provider_save_encrypts_credentials_and_lists_redacted_metadata(provider_store) -> None:
    with provider_store.factory() as database:
        summary = ai_providers.save_provider(
            database,
            provider_store.settings,
            provider_store.user_id,
            "openai",
            "https://api.openai.com/v1",
            "replace",
            "sk-secret-value",
        )

        assert summary["status"] == "configured"
        assert summary["api_key_configured"] is True
        assert "sk-secret-value" not in str(summary)
        credential = database.scalar(select(ApplicationCredential))
        setting = database.scalar(select(ApplicationSetting))
        audits = database.scalars(select(AuditAction)).all()

        assert credential is not None
        assert credential.ciphertext != "sk-secret-value"
        assert setting is not None
        assert setting.value_json == {"base_url": "https://api.openai.com/v1"}
        assert CredentialEncryption.from_settings(provider_store.settings).decrypt(credential.ciphertext) == "sk-secret-value"
        assert all("sk-secret-value" not in (audit.context or "") for audit in audits)


def test_provider_save_preserves_and_clears_credential_atomically(provider_store) -> None:
    with provider_store.factory() as database:
        ai_providers.save_provider(
            database,
            provider_store.settings,
            provider_store.user_id,
            "openrouter",
            "https://openrouter.ai/api/v1",
            "replace",
            "sk-original",
        )
        preserved = ai_providers.save_provider(
            database,
            provider_store.settings,
            provider_store.user_id,
            "openrouter",
            "https://openrouter.ai/api/v1",
            "unchanged",
            None,
        )
        assert preserved["api_key_configured"] is True
        failed = ai_providers.test_provider(
            database,
            provider_store.settings,
            "openrouter",
            client_factory=_client_factory(lambda request: httpx.Response(503)),
        )
        assert failed.status == "failed"

        cleared = ai_providers.save_provider(
            database,
            provider_store.settings,
            provider_store.user_id,
            "openrouter",
            "https://openrouter.ai/api/v1",
            "clear",
            None,
        )
        assert cleared["status"] == "not_configured"
        assert database.scalar(select(ApplicationCredential)) is None


def test_provider_save_rejects_unsafe_url_and_fails_closed_without_encryption_key(provider_store) -> None:
    with provider_store.factory() as database:
        with pytest.raises(ai_providers.InvalidProviderConfigurationError):
            ai_providers.save_provider(
                database,
                provider_store.settings,
                provider_store.user_id,
                "ollama",
                "http://127.0.0.1:11434",
                "unchanged",
                None,
            )

        unavailable = Settings(auth_secret="a" * 32, database_url=provider_store.settings.database_url)
        with pytest.raises(ai_providers.InvalidProviderConfigurationError):
            ai_providers.save_provider(
                database,
                unavailable,
                provider_store.user_id,
                "openai",
                "https://api.openai.com/v1",
                "replace",
                "sk-secret-value",
            )
        assert database.scalar(select(ApplicationSetting)) is None
        assert database.scalar(select(ApplicationCredential)) is None


def test_provider_connection_test_success_and_malformed_response_are_safe(provider_store) -> None:
    with provider_store.factory() as database:
        ai_providers.save_provider(
            database,
            provider_store.settings,
            provider_store.user_id,
            "ollama",
            "http://ollama:11434",
            "unchanged",
            None,
        )

        success = ai_providers.test_provider(
            database,
            provider_store.settings,
            "ollama",
            client_factory=_client_factory(lambda request: httpx.Response(200, json={"models": []})),
        )
        assert success == ai_providers.ConnectionTestResult(
            "ollama", "connected", "The provider connection test succeeded."
        )

        malformed = ai_providers.test_provider(
            database,
            provider_store.settings,
            "ollama",
            client_factory=_client_factory(lambda request: httpx.Response(200, json={"unexpected": []})),
        )
        assert malformed.status == "failed"
        assert "unexpected" not in malformed.message


def test_provider_connection_test_blocks_unsafe_redirect(provider_store) -> None:
    with provider_store.factory() as database:
        ai_providers.save_provider(
            database,
            provider_store.settings,
            provider_store.user_id,
            "ollama",
            "https://ollama.example.test",
            "unchanged",
            None,
        )
        result = ai_providers.test_provider(
            database,
            provider_store.settings,
            "ollama",
            client_factory=_client_factory(
                lambda request: httpx.Response(302, headers={"location": "http://169.254.169.254/"})
            ),
        )
        assert result.status == "blocked"
        assert "169.254.169.254" not in result.message
