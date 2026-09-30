from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlencode

import httpx


class IntegrationProviderError(RuntimeError):
    """Safe, normalized provider failure that can cross the API boundary."""

    def __init__(
        self,
        code: str,
        message: str = "The integration provider request failed",
        *,
        retryable: bool = False,
        outcome_unknown: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.outcome_unknown = outcome_unknown


@dataclass(frozen=True)
class OAuthTokenSet:
    access_token: str
    refresh_token: str | None
    expires_in: int | None
    scopes: tuple[str, ...]


@dataclass(frozen=True)
class ConnectionIdentity:
    external_account_id: str
    external_account_label: str
    scopes: tuple[str, ...]


@dataclass(frozen=True)
class DeliveryReceipt:
    receipt_id: str | None = None


class IntegrationAdapter(Protocol):
    provider_id: str
    display_name: str
    client_id_credential_key: str
    client_secret_credential_key: str
    required_scopes: tuple[str, ...]

    def normalize_destination(self, destination: str) -> str: ...

    def validate_destination(self, destination: str) -> None: ...

    def build_authorization_url(self, client_id: str, redirect_uri: str, state: str) -> str: ...

    def exchange_code(
        self,
        client_id: str,
        client_secret: str,
        code: str,
        redirect_uri: str,
        *,
        client: httpx.Client | None = None,
    ) -> OAuthTokenSet: ...

    def identify(
        self,
        access_token: str,
        *,
        client: httpx.Client | None = None,
    ) -> ConnectionIdentity: ...

    def refresh(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        *,
        client: httpx.Client | None = None,
    ) -> OAuthTokenSet: ...

    def revoke(
        self,
        access_token: str,
        *,
        client: httpx.Client | None = None,
    ) -> None: ...

    def send(
        self,
        access_token: str,
        destination: str,
        subject: str | None,
        body: str,
        *,
        client: httpx.Client | None = None,
    ) -> DeliveryReceipt: ...


def provider_request(
    method: str,
    url: str,
    *,
    client: httpx.Client | None = None,
    allow_empty: bool = False,
    **kwargs: Any,
) -> dict[str, Any]:
    owned_client = client is None
    request_client = client or httpx.Client(timeout=15.0)
    try:
        try:
            response = request_client.request(method, url, **kwargs)
        except httpx.TimeoutException as error:
            raise IntegrationProviderError(
                "integration_provider_unavailable",
                retryable=False,
                outcome_unknown=True,
            ) from error
        except httpx.TransportError as error:
            raise IntegrationProviderError(
                "integration_provider_unavailable",
                retryable=True,
            ) from error
        if response.status_code >= 400:
            code = _status_error_code(response.status_code)
            raise IntegrationProviderError(
                code,
                retryable=response.status_code == 429 or response.status_code >= 500,
            )
        try:
            payload = response.json()
        except ValueError as error:
            if allow_empty and not response.content:
                return {}
            raise IntegrationProviderError("integration_provider_invalid_response") from error
        if not isinstance(payload, dict):
            raise IntegrationProviderError("integration_provider_invalid_response")
        return payload
    finally:
        if owned_client:
            request_client.close()


def provider_form(
    method: str,
    url: str,
    *,
    client: httpx.Client | None = None,
    **data: str,
) -> dict[str, Any]:
    return provider_request(method, url, client=client, data=data)


def normalized_scopes(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        values = value.split()
    elif isinstance(value, list):
        values = [item for item in value if isinstance(item, str)]
    else:
        values = []
    return tuple(sorted({item.strip() for item in values if item.strip()}))


def required_token(payload: dict[str, Any]) -> str:
    token = payload.get("access_token")
    if not isinstance(token, str) or not token:
        raise IntegrationProviderError("integration_provider_invalid_response")
    return token


def optional_refresh_token(payload: dict[str, Any]) -> str | None:
    token = payload.get("refresh_token")
    return token if isinstance(token, str) and token else None


def optional_expires_in(payload: dict[str, Any]) -> int | None:
    value = payload.get("expires_in")
    return value if isinstance(value, int) and value > 0 else None


def oauth_query(**values: str) -> str:
    return urlencode({key: value for key, value in values.items() if value})


def _status_error_code(status_code: int) -> str:
    if status_code in (401, 403):
        return "integration_provider_unauthorized"
    if status_code == 429:
        return "integration_provider_rate_limited"
    if status_code >= 500:
        return "integration_provider_unavailable"
    return "integration_provider_rejected"
