import re
from urllib.parse import urlencode

import httpx

from .base import (
    ConnectionIdentity,
    DeliveryReceipt,
    IntegrationAdapter,
    OAuthTokenSet,
    normalized_scopes,
    optional_expires_in,
    optional_refresh_token,
    provider_form,
    provider_request,
    required_token,
)


class OutlookAdapter(IntegrationAdapter):
    provider_id = "outlook"
    display_name = "Microsoft Outlook"
    client_id_credential_key = "integration.microsoft.client_id"
    client_secret_credential_key = "integration.microsoft.client_secret"
    required_scopes = ("Mail.Send", "User.Read", "offline_access", "openid", "profile", "email")

    def normalize_destination(self, destination: str) -> str:
        return destination.strip().casefold()

    def validate_destination(self, destination: str) -> None:
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", destination):
            raise IntegrationProviderError("integration_delivery_invalid")

    def build_authorization_url(self, client_id: str, redirect_uri: str, state: str) -> str:
        return "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?" + urlencode(
            {
                "client_id": client_id,
                "response_type": "code",
                "redirect_uri": redirect_uri,
                "response_mode": "query",
                "scope": " ".join(self.required_scopes),
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
            "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            client=client,
            client_id=client_id,
            client_secret=client_secret,
            code=code,
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
            "https://graph.microsoft.com/v1.0/me",
            client=client,
            headers={"authorization": f"Bearer {access_token}"},
        )
        account_id = payload.get("id")
        label = payload.get("mail") or payload.get("userPrincipalName")
        if not isinstance(account_id, str) or not isinstance(label, str):
            raise IntegrationProviderError("integration_provider_invalid_response")
        return ConnectionIdentity(account_id, label, self.required_scopes)

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
            "https://login.microsoftonline.com/common/oauth2/v2.0/token",
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
        # Microsoft Graph has no portable token-revoke endpoint for this flow;
        # disconnect clears local tokens and future refreshes stop immediately.
        return None

    def send(
        self,
        access_token: str,
        destination: str,
        subject: str | None,
        body: str,
        *,
        client: httpx.Client | None = None,
    ) -> DeliveryReceipt:
        self.validate_destination(destination)
        provider_request(
            "POST",
            "https://graph.microsoft.com/v1.0/me/sendMail",
            client=client,
            allow_empty=True,
            headers={"authorization": f"Bearer {access_token}"},
            json={
                "message": {
                    "subject": subject or "KubePilot notification",
                    "body": {"contentType": "Text", "content": body},
                    "toRecipients": [{"emailAddress": {"address": destination}}],
                },
                "saveToSentItems": True,
            },
        )
        return DeliveryReceipt()
