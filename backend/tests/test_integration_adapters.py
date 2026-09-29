import httpx
import pytest

from app.integrations.base import IntegrationProviderError
from app.integrations.google import GmailAdapter
from app.integrations.microsoft import OutlookAdapter
from app.integrations.registry import CATALOG_ONLY_PROVIDER_IDS, get_adapter
from app.integrations.slack import SlackAdapter


def mock_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_registry_supports_initial_providers_and_rejects_catalog_only() -> None:
    assert isinstance(get_adapter("slack"), SlackAdapter)
    assert isinstance(get_adapter("gmail"), GmailAdapter)
    assert isinstance(get_adapter("outlook"), OutlookAdapter)
    for provider in CATALOG_ONLY_PROVIDER_IDS + ("unknown",):
        with pytest.raises(IntegrationProviderError, match="not supported") as error:
            get_adapter(provider)
        assert error.value.code == "integration_not_supported"


def test_slack_authorization_url_keeps_state_and_requested_scope() -> None:
    url = SlackAdapter().build_authorization_url("client", "https://example.test/callback", "state-value")
    assert "client_id=client" in url
    assert "state=state-value" in url
    assert "scope=chat%3Awrite" in url


def test_google_exchange_normalizes_tokens_without_exposing_response_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "oauth2.googleapis.com"
        return httpx.Response(
            200,
            json={"access_token": "access", "refresh_token": "refresh", "expires_in": 3600, "scope": "email openid"},
        )

    tokens = GmailAdapter().exchange_code(
        "client",
        "secret",
        "code",
        "https://example.test/callback",
        client=mock_client(handler),
    )
    assert tokens.access_token == "access"
    assert tokens.refresh_token == "refresh"
    assert tokens.expires_in == 3600
    assert tokens.scopes == ("email", "openid")


def test_outlook_identity_uses_safe_graph_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer token"
        return httpx.Response(200, json={"id": "user-1", "mail": "admin@example.com"})

    identity = OutlookAdapter().identify("token", client=mock_client(handler))
    assert identity.external_account_id == "user-1"
    assert identity.external_account_label == "admin@example.com"
    assert "Mail.Send" in identity.scopes


def test_provider_http_failures_are_normalized_without_upstream_body() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="provider secret response")

    with pytest.raises(IntegrationProviderError) as error:
        SlackAdapter().identify("token", client=mock_client(handler))
    assert error.value.code == "integration_provider_unavailable"
    assert "provider secret" not in str(error.value)
