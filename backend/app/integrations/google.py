from urllib.parse import urlencode

import httpx

from .base import (
    ConnectionIdentity,
    IntegrationAdapter,
    OAuthTokenSet,
    normalized_scopes,
    optional_expires_in,
    optional_refresh_token,
    provider_form,
    provider_request,
    required_token,
)


class GmailAdapter(IntegrationAdapter):
    provider_id = "gmail"
    display_name = "Gmail"
    client_id_credential_key = "integration.google.client_id"
    client_secret_credential_key = "integration.google.client_secret"
    required_scopes = ("https://www.googleapis.com/auth/gmail.send", "openid", "email")

    def build_authorization_url(self, client_id: str, redirect_uri: str, state: str) -> str:
        return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
            {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": " ".join(self.required_scopes),
                "access_type": "offline",
                "prompt": "consent",
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
            "https://oauth2.googleapis.com/token",
            client=client,
            code=code,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            grant_type="authorization_code",
        )
        return OAuthTokenSet(
            access_token=required_token(payload),
            refresh_token=optional_refresh_token(payload),
            expires_in=optional_expires_in(payload),
            scopes=normalized_scopes(payload.get("scope")) or self.required_scopes,
        )

    def identify(self, access_token: str, *, client: httpx.Client | None = None) -> ConnectionIdentity:
        payload = provider_request(
            "GET",
            "https://openidconnect.googleapis.com/v1/userinfo",
            client=client,
            headers={"authorization": f"Bearer {access_token}"},
        )
        subject = payload.get("sub")
        email = payload.get("email")
        if not isinstance(subject, str) or not isinstance(email, str):
            raise IntegrationProviderError("integration_provider_invalid_response")
        return ConnectionIdentity(subject, email, self.required_scopes)

    def refresh(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        *,
        client: httpx.Client | None = None,
    ) -> OAuthTokenSet:
        payload = provider_form(
            "POST",
            "https://oauth2.googleapis.com/token",
            client=client,
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            grant_type="refresh_token",
        )
        return OAuthTokenSet(
            access_token=required_token(payload),
            refresh_token=optional_refresh_token(payload) or refresh_token,
            expires_in=optional_expires_in(payload),
            scopes=normalized_scopes(payload.get("scope")) or self.required_scopes,
        )

    def revoke(self, access_token: str, *, client: httpx.Client | None = None) -> None:
        provider_form("POST", "https://oauth2.googleapis.com/revoke", client=client, token=access_token)
