import pytest

from app.core.config import ConfigurationError, Settings
from app.services.credential_encryption import CredentialEncryption


def test_fernet_round_trip_does_not_use_plaintext() -> None:
    key = "w9vGz4Gm3WlP3k0Z5sYJfQ7X6oV8uT2rN1qM4pL6dK0="
    encryption = CredentialEncryption(key)

    ciphertext = encryption.encrypt("secret-value")

    assert ciphertext != "secret-value"
    assert encryption.decrypt(ciphertext) == "secret-value"


@pytest.mark.parametrize("key", [None, "not-a-fernet-key"])
def test_missing_or_invalid_key_fails_closed(key: str | None) -> None:
    with pytest.raises(ConfigurationError):
        CredentialEncryption(key)


def test_settings_reads_optional_bootstrap_crypto_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KUBEPILOT_AUTH_SECRET", "a" * 32)
    monkeypatch.setenv("KUBEPILOT_DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("KUBEPILOT_ENCRYPTION_KEY", "  generated-key  ")
    monkeypatch.setenv("KUBEPILOT_PROVIDER_ALLOWED_HOSTS", "ollama, service.cluster.local ")

    settings = Settings.from_env()

    assert settings.encryption_key == "generated-key"
    assert settings.provider_allowed_hosts == ("ollama", "service.cluster.local")
