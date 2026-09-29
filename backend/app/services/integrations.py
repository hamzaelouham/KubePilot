from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as SQLAlchemySession

from app.core.audit import AuditEvent, record_audit
from app.core.config import ConfigurationError, Settings
from app.integrations import CATALOG_ONLY_PROVIDER_IDS, SUPPORTED_PROVIDER_IDS, get_adapter
from app.integrations.base import IntegrationProviderError, OAuthTokenSet
from app.models.entities import ApplicationCredential, IntegrationConnection, IntegrationOAuthState
from app.services.application_settings import read_credential_value
from app.services.credential_encryption import CredentialEncryption


STATE_TTL = timedelta(minutes=10)
REFRESH_SKEW = timedelta(minutes=1)
SLACK_BOT_TOKEN_CREDENTIAL_KEY = "integration.slack.bot_token"

CATALOG = (
    ("slack", "Slack", True),
    ("gmail", "Gmail", True),
    ("outlook", "Microsoft Outlook", True),
    ("teams", "Microsoft Teams", False),
    ("github", "GitHub", False),
    ("webhooks", "Webhooks", False),
)


class IntegrationServiceError(RuntimeError):
    status_code = 422

    def __init__(self, code: str, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        if status_code is not None:
            self.status_code = status_code


def list_connection_metadata(database: SQLAlchemySession) -> list[dict[str, Any]]:
    rows = {
        row.provider: row
        for row in database.scalars(select(IntegrationConnection)).all()
    }
    configured_keys = {
        row.credential_key
        for row in database.scalars(select(ApplicationCredential)).all()
    }
    result: list[dict[str, Any]] = []
    for provider_id, name, supported in CATALOG:
        row = rows.get(provider_id)
        if not supported:
            result.append(_metadata(provider_id, name, False, None, configured=False))
            continue
        adapter = get_adapter(provider_id)
        manual_token_configured = _manual_token_configured(database, provider_id)
        oauth_configured = (
            adapter.client_id_credential_key in configured_keys
            and adapter.client_secret_credential_key in configured_keys
        )
        result.append(
            _metadata(
                provider_id,
                name,
                True,
                row,
                configured=manual_token_configured or oauth_configured,
                manual_token_configured=manual_token_configured,
            )
        )
    return result


def begin_authorization(
    database: SQLAlchemySession,
    settings: Settings,
    actor_id: UUID,
    provider_id: str,
) -> dict[str, Any]:
    adapter = _adapter(provider_id)
    if not settings.public_url:
        raise IntegrationServiceError(
            "integration_public_url_missing",
            "The public callback URL is not configured",
            status_code=503,
        )
    client_id, client_secret = _client_credentials(database, settings, adapter)
    raw_state = secrets.token_urlsafe(32)
    state = IntegrationOAuthState(
        state_digest=_digest_state(raw_state),
        provider=provider_id,
        actor_id=actor_id,
        expires_at=_now() + STATE_TTL,
    )
    database.add(state)
    row = _get_connection(database, provider_id)
    if row is None:
        database.add(IntegrationConnection(provider=provider_id, created_by_id=actor_id, status="authorizing"))
    elif row.status != "connected":
        row.status = "authorizing"
        row.last_error_code = None
        row.updated_by_id = actor_id
        row.updated_at = _now()
    redirect_uri = _redirect_uri(settings, provider_id)
    authorization_url = adapter.build_authorization_url(client_id, redirect_uri, raw_state)
    record_audit(
        database,
        AuditEvent.INTEGRATION_AUTHORIZATION_STARTED,
        actor_id,
        "integration_connection",
        provider_id,
        result="requested",
        context={"provider": provider_id},
    )
    database.commit()
    return {"provider_id": provider_id, "authorization_url": authorization_url, "expires_at": state.expires_at}


def connect_manual_token(
    database: SQLAlchemySession,
    settings: Settings,
    actor_id: UUID,
    provider_id: str,
) -> dict[str, Any]:
    if provider_id != "slack":
        raise IntegrationServiceError(
            "integration_manual_not_supported",
            "Manual token connection is supported only for Slack",
            status_code=422,
        )

    adapter = _adapter(provider_id)
    try:
        access_token = read_credential_value(database, settings, SLACK_BOT_TOKEN_CREDENTIAL_KEY)
        if not access_token:
            raise IntegrationServiceError(
                "integration_not_configured",
                "The Slack Bot User OAuth token is not configured",
            )
        identity = adapter.identify(access_token)
        _store_connection(
            database,
            settings,
            actor_id,
            provider_id,
            OAuthTokenSet(access_token, None, None, identity.scopes),
            identity,
        )
    except IntegrationServiceError as error:
        _record_manual_failure(database, actor_id, provider_id, error.code)
        raise
    except (ConfigurationError, IntegrationProviderError) as provider_error:
        database.rollback()
        error_code = _provider_error_code(provider_error)
        _record_manual_failure(database, actor_id, provider_id, error_code)
        raise IntegrationServiceError(error_code, "The Slack Bot Token could not be verified") from provider_error

    record_audit(
        database,
        AuditEvent.INTEGRATION_CONNECTED,
        actor_id,
        "integration_connection",
        provider_id,
        result="success",
        context={"provider": provider_id, "status": "connected", "mode": "manual_token"},
    )
    database.commit()
    row = database.scalar(select(IntegrationConnection).where(IntegrationConnection.provider == provider_id))
    return _metadata(
        provider_id,
        adapter.display_name,
        True,
        row,
        configured=True,
        manual_token_configured=True,
    )


def complete_authorization(
    database: SQLAlchemySession,
    settings: Settings,
    provider_id: str,
    state_value: str,
    code: str | None,
    error: str | None,
) -> dict[str, Any]:
    adapter = _adapter(provider_id)
    state = database.scalar(
        select(IntegrationOAuthState).where(
            IntegrationOAuthState.state_digest == _digest_state(state_value)
        )
    )
    if state is None or state.provider != provider_id:
        raise IntegrationServiceError("integration_state_invalid", "The integration authorization state is invalid", status_code=400)
    actor_id = state.actor_id
    if state.consumed_at is not None:
        _audit_callback_failure(database, actor_id, provider_id, "integration_state_invalid")
        raise IntegrationServiceError("integration_state_invalid", "The integration authorization state was already used", status_code=400)
    if _as_utc(state.expires_at) <= _now():
        state.consumed_at = _now()
        _audit_callback_failure(database, actor_id, provider_id, "integration_state_expired")
        database.commit()
        raise IntegrationServiceError("integration_state_expired", "The integration authorization state expired", status_code=400)

    state.consumed_at = _now()
    if error or not code:
        _audit_callback_failure(database, actor_id, provider_id, "integration_callback_denied")
        raise IntegrationServiceError("integration_callback_denied", "The provider denied the integration authorization", status_code=400)

    try:
        client_id, client_secret = _client_credentials(database, settings, adapter)
        tokens = adapter.exchange_code(
            client_id,
            client_secret,
            code,
            _redirect_uri(settings, provider_id),
        )
        _require_scopes(adapter.required_scopes, tokens)
        identity = adapter.identify(tokens.access_token)
        _store_connection(database, settings, actor_id, provider_id, tokens, identity)
    except IntegrationServiceError as service_error:
        _audit_callback_failure(database, actor_id, provider_id, service_error.code)
        raise
    except (ConfigurationError, IntegrationProviderError) as provider_error:
        error_code = _provider_error_code(provider_error)
        _audit_callback_failure(database, actor_id, provider_id, error_code)
        raise IntegrationServiceError(error_code, "The integration could not be connected") from provider_error

    record_audit(
        database,
        AuditEvent.INTEGRATION_CONNECTED,
        actor_id,
        "integration_connection",
        provider_id,
        result="success",
        context={"provider": provider_id, "status": "connected"},
    )
    database.commit()
    row = database.scalar(select(IntegrationConnection).where(IntegrationConnection.provider == provider_id))
    return _metadata(
        provider_id,
        adapter.display_name,
        True,
        row,
        configured=True,
        manual_token_configured=_manual_token_configured(database, provider_id),
    )


def test_connection(
    database: SQLAlchemySession,
    settings: Settings,
    actor_id: UUID,
    provider_id: str,
) -> dict[str, Any]:
    adapter = _adapter(provider_id)
    row = _get_connection(database, provider_id)
    if row is None or not row.access_token_ciphertext:
        raise IntegrationServiceError("integration_not_connected", "The integration is not connected", status_code=404)
    try:
        access_token = _usable_access_token(database, settings, row, adapter)
        identity = adapter.identify(access_token)
        row.status = "connected"
        row.external_account_id = identity.external_account_id
        row.external_account_label = identity.external_account_label
        row.granted_scopes = list(identity.scopes)
        row.last_error_code = None
        row.last_tested_at = _now()
        row.updated_at = _now()
        record_audit(
            database,
            AuditEvent.INTEGRATION_TEST_SUCCEEDED,
            actor_id,
            "integration_connection",
            provider_id,
            result="success",
            context={"provider": provider_id, "status": "connected"},
        )
        database.commit()
    except (ConfigurationError, IntegrationProviderError) as provider_error:
        error_code = _provider_error_code(provider_error)
        row.status = "error"
        row.last_error_code = error_code
        row.last_tested_at = _now()
        row.updated_at = _now()
        record_audit(
            database,
            AuditEvent.INTEGRATION_TEST_FAILED,
            actor_id,
            "integration_connection",
            provider_id,
            result="failure",
            context={"provider": provider_id, "error_code": error_code},
        )
        database.commit()
        raise IntegrationServiceError(error_code, "The integration connection test failed") from provider_error
    return _metadata(
        provider_id,
        adapter.display_name,
        True,
        row,
        configured=True,
        manual_token_configured=_manual_token_configured(database, provider_id),
    )


def disconnect(
    database: SQLAlchemySession,
    settings: Settings,
    actor_id: UUID,
    provider_id: str,
) -> dict[str, Any]:
    adapter = _adapter(provider_id)
    row = _get_connection(database, provider_id)
    if row is None:
        return _metadata(
            provider_id,
            adapter.display_name,
            True,
            None,
            configured=_configured(database, adapter),
            manual_token_configured=_manual_token_configured(database, provider_id),
        )

    revoke_error: str | None = None
    if row.access_token_ciphertext:
        try:
            access_token = CredentialEncryption.from_settings(settings).decrypt(row.access_token_ciphertext)
            if not _is_manual_slack_connection(database, settings, provider_id, access_token):
                adapter.revoke(access_token)
        except (ConfigurationError, IntegrationProviderError) as provider_error:
            revoke_error = _provider_error_code(provider_error)
    row.status = "revoked"
    row.access_token_ciphertext = None
    row.refresh_token_ciphertext = None
    row.access_token_expires_at = None
    row.last_error_code = revoke_error
    row.updated_by_id = actor_id
    row.updated_at = _now()
    record_audit(
        database,
        AuditEvent.INTEGRATION_DISCONNECTED,
        actor_id,
        "integration_connection",
        provider_id,
        result="failure" if revoke_error else "success",
        context={"provider": provider_id, "status": "revoked", **({"error_code": revoke_error} if revoke_error else {})},
    )
    database.commit()
    return _metadata(
        provider_id,
        adapter.display_name,
        True,
        row,
        configured=_configured(database, adapter),
        manual_token_configured=_manual_token_configured(database, provider_id),
    )


def _store_connection(
    database: SQLAlchemySession,
    settings: Settings,
    actor_id: UUID,
    provider_id: str,
    tokens: OAuthTokenSet,
    identity: Any,
) -> None:
    encryption = CredentialEncryption.from_settings(settings)
    row = _get_connection(database, provider_id)
    if row is None:
        row = IntegrationConnection(provider=provider_id, created_by_id=actor_id)
        database.add(row)
    row.status = "connected"
    row.external_account_id = identity.external_account_id
    row.external_account_label = identity.external_account_label
    row.granted_scopes = list(identity.scopes)
    row.access_token_ciphertext = encryption.encrypt(tokens.access_token)
    row.refresh_token_ciphertext = encryption.encrypt(tokens.refresh_token) if tokens.refresh_token else None
    row.access_token_expires_at = _expires_at(tokens.expires_in)
    row.last_error_code = None
    row.updated_by_id = actor_id
    row.updated_at = _now()


def _usable_access_token(database, settings, row, adapter) -> str:
    encryption = CredentialEncryption.from_settings(settings)
    access_token = encryption.decrypt(row.access_token_ciphertext)
    if row.access_token_expires_at is None or _as_utc(row.access_token_expires_at) > _now() + REFRESH_SKEW:
        return access_token
    if not row.refresh_token_ciphertext:
        raise IntegrationProviderError("integration_connection_expired")
    client_id, client_secret = _client_credentials(database, settings, adapter)
    refresh_token = encryption.decrypt(row.refresh_token_ciphertext)
    tokens = adapter.refresh(client_id, client_secret, refresh_token)
    row.access_token_ciphertext = encryption.encrypt(tokens.access_token)
    row.refresh_token_ciphertext = encryption.encrypt(tokens.refresh_token) if tokens.refresh_token else row.refresh_token_ciphertext
    row.access_token_expires_at = _expires_at(tokens.expires_in)
    database.flush()
    return tokens.access_token


def get_usable_access_token(database, settings, row, adapter) -> str:
    """Resolve a connection token without exposing encryption outside this service boundary."""
    return _usable_access_token(database, settings, row, adapter)


def _client_credentials(database, settings, adapter) -> tuple[str, str]:
    client_id = read_credential_value(database, settings, adapter.client_id_credential_key)
    client_secret = read_credential_value(database, settings, adapter.client_secret_credential_key)
    if not client_id or not client_secret:
        raise IntegrationServiceError("integration_not_configured", "Provider application credentials are not configured")
    return client_id, client_secret


def _adapter(provider_id):
    try:
        return get_adapter(provider_id)
    except IntegrationProviderError as error:
        raise IntegrationServiceError(error.code, str(error), status_code=422) from error


def _get_connection(database, provider_id):
    return database.scalar(select(IntegrationConnection).where(IntegrationConnection.provider == provider_id))


def _configured(database, adapter) -> bool:
    keys = {row.credential_key for row in database.scalars(select(ApplicationCredential)).all()}
    oauth_configured = adapter.client_id_credential_key in keys and adapter.client_secret_credential_key in keys
    return oauth_configured or (
        adapter.provider_id == "slack" and SLACK_BOT_TOKEN_CREDENTIAL_KEY in keys
    )


def _manual_token_configured(database, provider_id: str) -> bool:
    if provider_id != "slack":
        return False
    return database.scalar(
        select(ApplicationCredential).where(
            ApplicationCredential.credential_key == SLACK_BOT_TOKEN_CREDENTIAL_KEY
        )
    ) is not None


def _is_manual_slack_connection(
    database: SQLAlchemySession,
    settings: Settings,
    provider_id: str,
    access_token: str,
) -> bool:
    if provider_id != "slack":
        return False
    try:
        configured_token = read_credential_value(database, settings, SLACK_BOT_TOKEN_CREDENTIAL_KEY)
    except ConfigurationError:
        return False
    return bool(configured_token) and secrets.compare_digest(configured_token, access_token)


def _record_manual_failure(database, actor_id: UUID, provider_id: str, error_code: str) -> None:
    record_audit(
        database,
        AuditEvent.INTEGRATION_MANUAL_CONNECTION_FAILED,
        actor_id,
        "integration_connection",
        provider_id,
        result="failure",
        context={"provider": provider_id, "error_code": error_code},
    )
    database.commit()


def _metadata(provider_id, name, supported, row, *, configured, manual_token_configured=False):
    return {
        "provider_id": provider_id,
        "name": name,
        "supported": supported,
        "configured": configured,
        "manual_token_configured": manual_token_configured,
        "status": row.status if row is not None else "not_connected" if supported else "not_supported",
        "external_account_label": row.external_account_label if row is not None else None,
        "granted_scopes": row.granted_scopes if row is not None else [],
        "last_tested_at": row.last_tested_at if row is not None else None,
        "last_error_code": row.last_error_code if row is not None else None,
    }


def _require_scopes(required, tokens: OAuthTokenSet) -> None:
    if not set(required).issubset(tokens.scopes):
        raise IntegrationServiceError("integration_scope_denied", "The provider did not grant the required permissions", status_code=422)


def _provider_error_code(error: ConfigurationError | IntegrationProviderError) -> str:
    if isinstance(error, ConfigurationError):
        return "integration_encryption_unavailable"
    return error.code


def _audit_callback_failure(database, actor_id, provider_id, error_code) -> None:
    row = _get_connection(database, provider_id)
    if row is not None and row.status != "connected":
        row.status = "error"
        row.last_error_code = error_code
        row.updated_by_id = actor_id
        row.updated_at = _now()
    record_audit(
        database,
        AuditEvent.INTEGRATION_AUTHORIZATION_FAILED,
        actor_id,
        "integration_connection",
        provider_id,
        result="failure",
        context={"provider": provider_id, "error_code": error_code},
    )
    database.commit()


def _redirect_uri(settings: Settings, provider_id: str) -> str:
    if not settings.public_url:
        raise IntegrationServiceError("integration_public_url_missing", "The public callback URL is not configured", status_code=503)
    return f"{settings.public_url}/api/settings/integrations/{provider_id}/callback"


def _digest_state(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _expires_at(expires_in: int | None) -> datetime | None:
    return _now() + timedelta(seconds=expires_in) if expires_in else None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
