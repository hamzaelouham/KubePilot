from urllib.parse import urlencode

import httpx

from .base import (
    ConnectionIdentity,
    IntegrationProviderError,
    OAuthTokenSet,
    IntegrationAdapter,
    normalized_scopes,
    optional_expires_in,
    optional_refresh_token,
    provider_form,
    provider_request,
    required_token,
)


class SlackAdapter(IntegrationAdapter):
    provider_id = "slack"
    display_name = "Slack"
    client_id_credential_key = "integration.slack.client_id"
    client_secret_credential_key = "integration.slack.client_secret"
    required_scopes = ("chat:write",)

    def build_authorization_url(self, client_id: str, redirect_uri: str, state: str) -> str:
        return "https://slack.com/oauth/v2/authorize?" + urlencode(
            {
                "client_id": client_id,
                "scope": ",".join(self.required_scopes),
                "redirect_uri": redirect_uri,
                "state": state,
            }
        )

    def exchange_code(
        self,
        client_id: str,
        client_secret: str,
        code: str,
        redirect_uri: str,
        *,
        client: httpx.Client | None = None,
    ) -> OAuthTokenSet:
        payload = provider_form(
            "POST",
            "https://slack.com/api/oauth.v2.access",
            client=client,
            client_id=client_id,
            client_secret=client_secret,
            code=code,
            redirect_uri=redirect_uri,
        )
        if payload.get("ok") is not True:
            raise IntegrationProviderError("integration_callback_denied")
        return OAuthTokenSet(
            access_token=required_token(payload),
            refresh_token=None,
            expires_in=None,
            scopes=normalized_scopes(payload.get("scope")) or self.required_scopes,
        )

    def identify(self, access_token: str, *, client: httpx.Client | None = None) -> ConnectionIdentity:
        payload = provider_request(
            "GET",
            "https://slack.com/api/auth.test",
            client=client,
            headers={"authorization": f"Bearer {access_token}"},
        )
        if payload.get("ok") is not True:
            raise IntegrationProviderError("integration_connection_invalid")
        team_id = payload.get("team_id")
        team_name = payload.get("team")
        if not isinstance(team_id, str) or not isinstance(team_name, str):
            raise IntegrationProviderError("integration_provider_invalid_response")
        return ConnectionIdentity(team_id, team_name, self.required_scopes)

    def refresh(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        *,
        client: httpx.Client | None = None,
    ) -> OAuthTokenSet:
        raise IntegrationProviderError("integration_refresh_unsupported")

    def revoke(self, access_token: str, *, client: httpx.Client | None = None) -> None:
        payload = provider_form(
            "POST",
            "https://slack.com/api/auth.revoke",
            client=client,
            token=access_token,
        )
        if payload.get("ok") is not True:
            raise IntegrationProviderError("integration_provider_rejected")
