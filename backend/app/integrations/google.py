import base64
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


class GmailAdapter(IntegrationAdapter):
    provider_id = "gmail"
    display_name = "Gmail"
    client_id_credential_key = "integration.google.client_id"
    client_secret_credential_key = "integration.google.client_secret"
    required_scopes = ("https://www.googleapis.com/auth/gmail.send", "openid", "email")

    def validate_destination(self, destination: str) -> None:
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", destination):
            raise IntegrationProviderError("integration_delivery_invalid")

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
        message = (
            f"To: {destination}\r\n"
            f"Subject: {subject or 'KubePilot notification'}\r\n"
            "Content-Type: text/plain; charset=utf-8\r\n"
            "\r\n"
            f"{body}"
        )
        raw = base64.urlsafe_b64encode(message.encode("utf-8")).decode("ascii").rstrip("=")
        payload = provider_request(
            "POST",
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            client=client,
            headers={"authorization": f"Bearer {access_token}"},
            json={"raw": raw},
        )
        receipt_id = payload.get("id")
        return DeliveryReceipt(receipt_id if isinstance(receipt_id, str) else None)
