import pytest

from app.core.config import Settings
from app.services.provider_url_policy import ProviderURLPolicy, ProviderURLPolicyError


def test_public_https_provider_url_is_allowed_without_network_access() -> None:
    policy = ProviderURLPolicy()

    assert policy.validate("https://api.openai.com/v1") == "https://api.openai.com/v1"


def test_allowlisted_internal_provider_host_is_allowed() -> None:
    policy = ProviderURLPolicy.from_hosts(("ollama", "ollama.kubepilot.svc.cluster.local"))

    assert policy.validate("http://ollama:11434") == "http://ollama:11434"


def test_policy_can_be_constructed_from_bootstrap_settings() -> None:
    settings = Settings(
        auth_secret="a" * 32,
        database_url="sqlite:///./test.db",
        provider_allowed_hosts=("ollama",),
    )

    assert ProviderURLPolicy.from_settings(settings).validate("http://ollama:11434") == "http://ollama:11434"


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:11434",
        "http://127.0.0.1:8000",
        "http://169.254.169.254/latest/meta-data",
        "http://service.cluster.local:11434",
        "ftp://api.openai.com/model",
        "https://user:password@api.openai.com/model",
        "https://api.openai.com/model?token=secret",
        "https://api.openai.com/model#fragment",
        "https://",
    ],
)
def test_unsafe_provider_urls_are_rejected(url: str) -> None:
    with pytest.raises(ProviderURLPolicyError):
        ProviderURLPolicy().validate(url)


def test_redirects_are_revalidated_and_cannot_bypass_allowlist() -> None:
    policy = ProviderURLPolicy.from_hosts(("ollama",))

    with pytest.raises(ProviderURLPolicyError):
        policy.validate_redirect("http://169.254.169.254/")
