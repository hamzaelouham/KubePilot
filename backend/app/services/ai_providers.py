from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Callable, Literal, Protocol
from urllib.parse import urljoin
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session as SQLAlchemySession

from app.core.audit import AuditEvent, record_audit
from app.core.config import ConfigurationError, Settings
from app.models.entities import ApplicationCredential, ApplicationSetting
from app.services import application_settings
from app.services.credential_encryption import CredentialEncryption
from app.services.provider_url_policy import ProviderURLPolicy, ProviderURLPolicyError


ProviderConnectionStatus = Literal["configured", "not_configured"]
ConnectionTestStatus = Literal["connected", "not_configured", "blocked", "failed"]

_MAX_REDIRECTS = 3
_MAX_RESPONSE_BYTES = 64 * 1024
_REQUEST_TIMEOUT_SECONDS = 10.0


class ProviderServiceError(RuntimeError):
    status_code = 422
    code = "provider_error"


class UnknownProviderError(ProviderServiceError):
    status_code = 404
    code = "provider_not_found"


class InvalidProviderConfigurationError(ProviderServiceError):
    code = "invalid_provider_configuration"


@dataclass(frozen=True)
class ProviderDefinition:
    provider_id: str
    name: str
    setting_key: str
    credential_key: str | None
    capability_path: str
    capability_field: str
    chat_path: str

    @property
    def credential_required(self) -> bool:
        return self.credential_key is not None


PROVIDER_DEFINITIONS: dict[str, ProviderDefinition] = {
    "openai": ProviderDefinition(
        provider_id="openai",
        name="OpenAI",
        setting_key="ai.provider.openai",
        credential_key="ai.provider.openai.api_key",
        capability_path="models",
        capability_field="data",
        chat_path="chat/completions",
    ),
    "openrouter": ProviderDefinition(
        provider_id="openrouter",
        name="OpenRouter",
        setting_key="ai.provider.openrouter",
        credential_key="ai.provider.openrouter.api_key",
        capability_path="models",
        capability_field="data",
        chat_path="chat/completions",
    ),
    "ollama": ProviderDefinition(
        provider_id="ollama",
        name="Ollama",
        setting_key="ai.provider.ollama",
        credential_key=None,
        capability_path="api/tags",
        capability_field="models",
        chat_path="v1/chat/completions",
    ),
}


class ProviderHTTPClient(Protocol):
    def stream(self, method: str, url: str, *, headers: dict[str, str]): ...


HTTPClientFactory = Callable[..., ProviderHTTPClient]


@dataclass(frozen=True)
class ConnectionTestResult:
    provider_id: str
    status: ConnectionTestStatus
    message: str


@dataclass(frozen=True)
class ProviderCatalogResult:
    provider_id: str
    status: ConnectionTestStatus
    message: str
    model_ids: frozenset[str] = frozenset()


def get_provider(provider_id: str) -> ProviderDefinition:
    definition = PROVIDER_DEFINITIONS.get(provider_id)
    if definition is None:
        raise UnknownProviderError("Provider is not registered")
    return definition


def register_provider_settings() -> None:
    """Expose provider keys through the centralized settings registries."""
    for definition in PROVIDER_DEFINITIONS.values():
        if definition.setting_key not in application_settings.SETTING_DEFINITIONS:
            application_settings.register_setting_definition(
                application_settings.SettingDefinition(definition.setting_key, default=None)
            )
        if definition.credential_key and definition.credential_key not in application_settings.CREDENTIAL_DEFINITIONS:
            application_settings.register_credential_definition(
                application_settings.CredentialDefinition(
                    key=definition.credential_key,
                    display_name=f"{definition.name} API key",
                    description=f"API key used by KubePilot to access {definition.name}.",
                    category="provider",
                )
            )


def list_providers(database: SQLAlchemySession) -> list[dict[str, Any]]:
    settings_by_key = {
        row.key: row
        for row in database.scalars(select(ApplicationSetting)).all()
        if row.key in {definition.setting_key for definition in PROVIDER_DEFINITIONS.values()}
    }
    credentials_by_key = {
        row.credential_key: row
        for row in database.scalars(select(ApplicationCredential)).all()
        if row.credential_key in {
            definition.credential_key
            for definition in PROVIDER_DEFINITIONS.values()
            if definition.credential_key
        }
    }
    return [
        _provider_summary(
            definition,
            settings_by_key.get(definition.setting_key),
            credentials_by_key.get(definition.credential_key) if definition.credential_key else None,
        )
        for definition in PROVIDER_DEFINITIONS.values()
    ]


def save_provider(
    database: SQLAlchemySession,
    settings: Settings,
    actor_id: UUID,
    provider_id: str,
    base_url: str,
    api_key_action: Literal["unchanged", "replace", "clear"],
    api_key: str | None,
) -> dict[str, Any]:
    definition = get_provider(provider_id)
    normalized_url = _validate_base_url(settings, base_url)
    _validate_credential_action(definition, api_key_action, api_key)

    ciphertext: str | None = None
    if api_key_action == "replace":
        try:
            ciphertext = CredentialEncryption.from_settings(settings).encrypt(api_key or "")
        except (ConfigurationError, TypeError, ValueError) as error:
            raise InvalidProviderConfigurationError("The provider credential could not be stored") from error

    try:
        setting = database.scalar(
            select(ApplicationSetting).where(ApplicationSetting.key == definition.setting_key)
        )
        if setting is None:
            setting = ApplicationSetting(
                key=definition.setting_key,
                value_json={"base_url": normalized_url},
                created_by_id=actor_id,
                updated_by_id=actor_id,
            )
            database.add(setting)
            setting_action = AuditEvent.SETTING_CREATED
        else:
            setting.value_json = {"base_url": normalized_url}
            setting.updated_by_id = actor_id
            setting.updated_at = _now()
            setting_action = AuditEvent.SETTING_UPDATED

        record_audit(
            database,
            setting_action,
            actor_id,
            "ai_provider",
            provider_id,
            result="succeeded",
            context={"provider_id": provider_id, "field": "configuration"},
        )

        credential = None
        if definition.credential_key:
            credential = database.scalar(
                select(ApplicationCredential).where(
                    ApplicationCredential.credential_key == definition.credential_key
                )
            )
            if api_key_action == "replace":
                if credential is None:
                    credential = ApplicationCredential(
                        credential_key=definition.credential_key,
                        ciphertext=ciphertext or "",
                        created_by_id=actor_id,
                        updated_by_id=actor_id,
                    )
                    database.add(credential)
                    credential_action = AuditEvent.CREDENTIAL_CREATED
                else:
                    credential.ciphertext = ciphertext or ""
                    credential.updated_by_id = actor_id
                    credential.updated_at = _now()
                    credential_action = AuditEvent.CREDENTIAL_REPLACED
                record_audit(
                    database,
                    credential_action,
                    actor_id,
                    "ai_provider",
                    provider_id,
                    result="succeeded",
                    context={"provider_id": provider_id, "field": "credential"},
                )
            elif api_key_action == "clear" and credential is not None:
                database.delete(credential)
                record_audit(
                    database,
                    AuditEvent.CREDENTIAL_DELETED,
                    actor_id,
                    "ai_provider",
                    provider_id,
                    result="succeeded",
                    context={"provider_id": provider_id, "field": "credential"},
                )

        database.commit()
        database.refresh(setting)
    except Exception:
        database.rollback()
        raise

    return _provider_summary(definition, setting, credential if api_key_action != "clear" else None)


def test_provider(
    database: SQLAlchemySession,
    settings: Settings,
    provider_id: str,
    *,
    client_factory: HTTPClientFactory | None = None,
) -> ConnectionTestResult:
    definition = get_provider(provider_id)
    setting = database.scalar(
        select(ApplicationSetting).where(ApplicationSetting.key == definition.setting_key)
    )
    credential = None
    if definition.credential_key:
        credential = database.scalar(
            select(ApplicationCredential).where(
                ApplicationCredential.credential_key == definition.credential_key
            )
        )
    if not _is_configured(definition, setting, credential):
        return ConnectionTestResult(provider_id, "not_configured", "Save the provider configuration before testing it.")

    base_url = setting.value_json.get("base_url") if isinstance(setting.value_json, dict) else None
    try:
        base_url = _validate_base_url(settings, base_url)
    except InvalidProviderConfigurationError:
        return ConnectionTestResult(provider_id, "blocked", "The saved provider URL is not allowed.")

    api_key = None
    if credential is not None:
        try:
            api_key = CredentialEncryption.from_settings(settings).decrypt(credential.ciphertext)
        except Exception:
            return ConnectionTestResult(provider_id, "failed", "The saved provider credential is unavailable.")

    headers = {"accept": "application/json"}
    if api_key:
        headers["authorization"] = f"Bearer {api_key}"
    factory = client_factory or httpx.Client
    try:
        with factory(follow_redirects=False, timeout=_REQUEST_TIMEOUT_SECONDS) as client:
            return _run_capability_test(
                client,
                definition,
                base_url,
                headers,
                ProviderURLPolicy.from_settings(settings),
            )
    except (httpx.HTTPError, OSError, TimeoutError):
        return ConnectionTestResult(provider_id, "failed", "The provider could not be reached.")


def fetch_provider_model_ids(
    database: SQLAlchemySession,
    settings: Settings,
    provider_id: str,
    *,
    client_factory: HTTPClientFactory | None = None,
) -> ProviderCatalogResult:
    """Fetch a bounded provider catalog without exposing credentials or payloads."""
    definition = get_provider(provider_id)
    setting = database.scalar(
        select(ApplicationSetting).where(ApplicationSetting.key == definition.setting_key)
    )
    credential = None
    if definition.credential_key:
        credential = database.scalar(
            select(ApplicationCredential).where(
                ApplicationCredential.credential_key == definition.credential_key
            )
        )
    if not _is_configured(definition, setting, credential):
        return ProviderCatalogResult(
            provider_id,
            "not_configured",
            "Save the provider configuration before checking model availability.",
        )

    base_url = setting.value_json.get("base_url") if isinstance(setting.value_json, dict) else None
    try:
        base_url = _validate_base_url(settings, base_url)
    except InvalidProviderConfigurationError:
        return ProviderCatalogResult(provider_id, "blocked", "The saved provider URL is not allowed.")

    api_key = None
    if credential is not None:
        try:
            api_key = CredentialEncryption.from_settings(settings).decrypt(credential.ciphertext)
        except Exception:
            return ProviderCatalogResult(
                provider_id,
                "failed",
                "The saved provider credential is unavailable.",
            )

    headers = {"accept": "application/json"}
    if api_key:
        headers["authorization"] = f"Bearer {api_key}"
    factory = client_factory or httpx.Client
    try:
        with factory(follow_redirects=False, timeout=_REQUEST_TIMEOUT_SECONDS) as client:
            return _run_catalog_query(
                client,
                definition,
                base_url,
                headers,
                ProviderURLPolicy.from_settings(settings),
            )
    except (httpx.HTTPError, OSError, TimeoutError):
        return ProviderCatalogResult(provider_id, "failed", "The provider could not be reached.")


def _run_catalog_query(
    client: ProviderHTTPClient,
    definition: ProviderDefinition,
    base_url: str,
    headers: dict[str, str],
    policy: ProviderURLPolicy,
) -> ProviderCatalogResult:
    url = urljoin(base_url.rstrip("/") + "/", definition.capability_path)
    for _ in range(_MAX_REDIRECTS + 1):
        with client.stream("GET", url, headers=headers) as response:
            content = b"".join(_bounded_chunks(response))
            status_code = response.status_code
            response_headers = response.headers

        if len(content) > _MAX_RESPONSE_BYTES:
            return ProviderCatalogResult(definition.provider_id, "failed", "The provider returned an oversized response.")
        if 300 <= status_code < 400:
            location = response_headers.get("location")
            if not location:
                return ProviderCatalogResult(definition.provider_id, "failed", "The provider returned an invalid redirect.")
            next_url = urljoin(url, location)
            try:
                policy.validate_redirect(next_url)
            except ProviderURLPolicyError:
                return ProviderCatalogResult(definition.provider_id, "blocked", "The provider redirect is not allowed.")
            url = next_url
            continue
        if not 200 <= status_code < 300:
            return ProviderCatalogResult(definition.provider_id, "failed", "The provider rejected the model catalog request.")
        try:
            payload = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, TypeError, ValueError):
            return ProviderCatalogResult(definition.provider_id, "failed", "The provider returned an invalid response.")
        items = payload.get(definition.capability_field) if isinstance(payload, dict) else None
        if not isinstance(items, list):
            return ProviderCatalogResult(definition.provider_id, "failed", "The provider returned an invalid response.")

        model_ids: set[str] = set()
        for item in items:
            if not isinstance(item, dict):
                continue
            keys = ("model", "name") if definition.provider_id == "ollama" else ("id",)
            for key in keys:
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    model_ids.add(value.strip())
                    break
        if items and not model_ids:
            return ProviderCatalogResult(definition.provider_id, "failed", "The provider returned an invalid response.")
        return ProviderCatalogResult(
            definition.provider_id,
            "connected",
            "The provider model catalog was retrieved.",
            frozenset(model_ids),
        )

    return ProviderCatalogResult(definition.provider_id, "failed", "The provider returned too many redirects.")


def _run_capability_test(
    client: ProviderHTTPClient,
    definition: ProviderDefinition,
    base_url: str,
    headers: dict[str, str],
    policy: ProviderURLPolicy,
) -> ConnectionTestResult:
    url = urljoin(base_url.rstrip("/") + "/", definition.capability_path)
    for _ in range(_MAX_REDIRECTS + 1):
        with client.stream("GET", url, headers=headers) as response:
            content = b"".join(_bounded_chunks(response))
            status_code = response.status_code
            response_headers = response.headers

        if len(content) > _MAX_RESPONSE_BYTES:
            return ConnectionTestResult(definition.provider_id, "failed", "The provider returned an oversized response.")
        if 300 <= status_code < 400:
            location = response_headers.get("location")
            if not location:
                return ConnectionTestResult(definition.provider_id, "failed", "The provider returned an invalid redirect.")
            next_url = urljoin(url, location)
            try:
                policy.validate_redirect(next_url)
            except ProviderURLPolicyError:
                return ConnectionTestResult(definition.provider_id, "blocked", "The provider redirect is not allowed.")
            url = next_url
            continue
        if not 200 <= status_code < 300:
            return ConnectionTestResult(definition.provider_id, "failed", "The provider rejected the connection test.")
        try:
            payload = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, TypeError, ValueError):
            return ConnectionTestResult(definition.provider_id, "failed", "The provider returned an invalid response.")
        if not isinstance(payload, dict) or not isinstance(payload.get(definition.capability_field), list):
            return ConnectionTestResult(definition.provider_id, "failed", "The provider returned an invalid response.")
        return ConnectionTestResult(definition.provider_id, "connected", "The provider connection test succeeded.")

    return ConnectionTestResult(definition.provider_id, "failed", "The provider returned too many redirects.")


def _bounded_chunks(response: Any):
    total = 0
    for chunk in response.iter_bytes():
        total += len(chunk)
        if total > _MAX_RESPONSE_BYTES:
            yield chunk[: _MAX_RESPONSE_BYTES + 1 - (total - len(chunk))]
            return
        yield chunk


def _provider_summary(
    definition: ProviderDefinition,
    setting: ApplicationSetting | None,
    credential: ApplicationCredential | None,
) -> dict[str, Any]:
    value = setting.value_json if setting is not None and isinstance(setting.value_json, dict) else {}
    configured = _is_configured(definition, setting, credential)
    return {
        "provider_id": definition.provider_id,
        "name": definition.name,
        "base_url": value.get("base_url"),
        "credential_required": definition.credential_required,
        "api_key_configured": credential is not None,
        "status": "configured" if configured else "not_configured",
        "updated_at": setting.updated_at if setting is not None else None,
    }


def _is_configured(
    definition: ProviderDefinition,
    setting: ApplicationSetting | None,
    credential: ApplicationCredential | None,
) -> bool:
    if setting is None or not isinstance(setting.value_json, dict) or not setting.value_json.get("base_url"):
        return False
    return not definition.credential_required or credential is not None


def _validate_base_url(settings: Settings, base_url: Any) -> str:
    if not isinstance(base_url, str) or not base_url.strip():
        raise InvalidProviderConfigurationError("A provider URL is required")
    try:
        return ProviderURLPolicy.from_settings(settings).validate(base_url.strip())
    except ProviderURLPolicyError as error:
        raise InvalidProviderConfigurationError(str(error)) from error


def _validate_credential_action(
    definition: ProviderDefinition,
    api_key_action: str,
    api_key: str | None,
) -> None:
    if api_key_action not in {"unchanged", "replace", "clear"}:
        raise InvalidProviderConfigurationError("Invalid provider credential action")
    if not definition.credential_required and api_key_action != "unchanged":
        raise InvalidProviderConfigurationError("This provider does not accept an API key")
    if api_key_action == "replace" and (not isinstance(api_key, str) or not api_key):
        raise InvalidProviderConfigurationError("An API key is required when replacing the credential")
    if api_key_action != "replace" and api_key is not None:
        raise InvalidProviderConfigurationError("An API key is only accepted when replacing the credential")


def _now():
    from datetime import datetime

    return datetime.now().astimezone()


register_provider_settings()
