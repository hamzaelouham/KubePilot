import pytest
from cryptography.fernet import Fernet


@pytest.fixture(autouse=True)
def test_encryption_key(monkeypatch):
    """Test-only key; tests for absent/invalid keys override it explicitly."""
    monkeypatch.setenv("KUBEPILOT_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("KUBEPILOT_LOCAL_DEVELOPMENT", "true")
