from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
import json
from typing import Any, Literal
from urllib.parse import urljoin
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import ConfigurationError, Settings
from app.models.entities import AIModelConfig, ApplicationCredential, ApplicationSetting
from app.services.ai_providers import ProviderDefinition, UnknownProviderError, get_provider
from app.services.credential_encryption import CredentialEncryption
from app.services.provider_url_policy import ProviderURLPolicy, ProviderURLPolicyError


MAX_INFERENCE_REQUEST_BYTES = 256 * 1024
MAX_STREAM_BYTES = 2 * 1024 * 1024
MAX_STREAM_CHUNK_BYTES = 256 * 1024
INFERENCE_TIMEOUT = httpx.Timeout(connect=10.0, read=110.0, write=10.0, pool=10.0)


class AIRuntimeError(RuntimeError):
    status_code = 503
    code = "ai_provider_unavailable"


class AINotConfiguredError(AIRuntimeError):
    code = "ai_not_configured"


class AIModelUnavailableError(AIRuntimeError):
    code = "ai_model_unavailable"


class AIToolCapabilityError(AIRuntimeError):
    status_code = 422
    code = "ai_model_tool_capability_mismatch"


class AIProviderAuthenticationError(AIRuntimeError):
    status_code = 502
    code = "ai_provider_authentication_failed"


class AIRateLimitError(AIRuntimeError):
    status_code = 429
    code = "ai_rate_limited"


class AIProviderTimeoutError(AIRuntimeError):
    status_code = 504
    code = "ai_provider_timeout"


@dataclass(frozen=True)
class RuntimeModel:
    model_id: UUID
    provider: ProviderDefinition
    external_model_id: str
    base_url: str
    api_key: str | None
    supports_tools: bool
    supports_reasoning: bool


AsyncClientFactory = Callable[..., httpx.AsyncClient]


class ProviderStream(AsyncIterator[bytes]):
    def __init__(self, response: httpx.Response, client: httpx.AsyncClient) -> None:
        self._response = response
        self._client = client
        self._iterator = response.aiter_bytes()
        self._total = 0
        self._closed = False

    def __aiter__(self) -> "ProviderStream":
        return self

    async def __anext__(self) -> bytes:
        try:
            while True:
                chunk = await self._iterator.__anext__()
                if chunk:
                    break
            self._total += len(chunk)
            if len(chunk) > MAX_STREAM_CHUNK_BYTES or self._total > MAX_STREAM_BYTES:
                raise AIRuntimeError("The AI provider returned an oversized streaming response.")
            return chunk
        except StopAsyncIteration:
            await self.aclose()
            raise
        except httpx.TimeoutException as error:
            await self.aclose()
            raise AIProviderTimeoutError("The AI provider timed out.") from error
        except httpx.HTTPError as error:
            await self.aclose()
            raise AIRuntimeError("The AI provider stream was interrupted.") from error
        except Exception:
            await self.aclose()
            raise

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._response.aclose()
        await self._client.aclose()


def resolve_runtime_model(
    database: Session,
    settings: Settings,
    model_id: Literal["default"] | UUID = "default",
) -> RuntimeModel:
    selecting_default = model_id == "default"
    model = (
        database.scalar(select(AIModelConfig).where(AIModelConfig.is_default.is_(True)))
        if selecting_default
        else database.get(AIModelConfig, model_id)
    )
    if model is None:
        if selecting_default:
            raise AINotConfiguredError("Configure an eligible default AI model in Settings.")
        raise AIModelUnavailableError("The selected AI model is not currently available.")
    label = "default" if selecting_default else "selected"
    if not model.enabled or model.availability != "available":
        raise AIModelUnavailableError(f"The {label} AI model is not currently available.")
    if not model.supports_streaming:
        raise AIModelUnavailableError(f"The {label} AI model does not support the current Assistant runtime.")

    try:
        provider = get_provider(model.provider_id)
    except UnknownProviderError as error:
        raise AIModelUnavailableError(f"The {label} AI model uses an unsupported provider.") from error

    provider_setting = database.scalar(
        select(ApplicationSetting).where(ApplicationSetting.key == provider.setting_key)
    )
    raw_setting = provider_setting.value_json if provider_setting is not None else None
    raw_base_url = raw_setting.get("base_url") if isinstance(raw_setting, dict) else None
    if not isinstance(raw_base_url, str) or not raw_base_url.strip():
        raise AINotConfiguredError(f"Configure the {label} model's provider in Settings.")
    try:
        base_url = ProviderURLPolicy.from_settings(settings).validate(raw_base_url.strip())
    except ProviderURLPolicyError as error:
        raise AINotConfiguredError(f"The {label} model's provider URL is not allowed.") from error

    api_key = None
    if provider.credential_key is not None:
        credential = database.scalar(
            select(ApplicationCredential).where(
                ApplicationCredential.credential_key == provider.credential_key
            )
        )
        if credential is None:
            raise AINotConfiguredError(f"Configure the {label} model's provider credential in Settings.")
        try:
            api_key = CredentialEncryption.from_settings(settings).decrypt(credential.ciphertext)
        except (ConfigurationError, TypeError, ValueError) as error:
            raise AINotConfiguredError(f"The {label} model's provider credential is unavailable.") from error

    return RuntimeModel(
        model.id,
        provider,
        model.external_model_id,
        base_url,
        api_key,
        bool(model.supports_tools),
        bool(model.supports_reasoning),
    )


async def open_chat_stream(
    database: Session,
    settings: Settings,
    payload: dict[str, Any],
    *,
    client_factory: AsyncClientFactory | None = None,
    runtime_model: RuntimeModel | None = None,
) -> tuple[ProviderStream, str]:
    model_id = payload.get("model", "default")
    if model_id != "default" and not isinstance(model_id, UUID):
        raise AIModelUnavailableError("The selected AI model is not currently available.")
    runtime = runtime_model or resolve_runtime_model(database, settings, model_id)
    outbound = _provider_payload(payload, runtime)
    encoded = json.dumps(outbound, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_INFERENCE_REQUEST_BYTES:
        raise AIModelUnavailableError("The AI request is too large.")

    headers = {"accept": "text/event-stream", "content-type": "application/json"}
    if runtime.api_key:
        headers["authorization"] = f"Bearer {runtime.api_key}"
    url = urljoin(runtime.base_url.rstrip("/") + "/", runtime.provider.chat_path)
    try:
        ProviderURLPolicy.from_settings(settings).validate(url)
    except ProviderURLPolicyError as error:
        raise AINotConfiguredError("The default model's provider URL is not allowed.") from error

    factory = client_factory or httpx.AsyncClient
    client = factory(follow_redirects=False, timeout=INFERENCE_TIMEOUT)
    try:
        request = client.build_request("POST", url, headers=headers, content=encoded)
        response = await client.send(request, stream=True)
    except httpx.TimeoutException as error:
        await client.aclose()
        raise AIProviderTimeoutError("The AI provider timed out.") from error
    except (httpx.HTTPError, OSError) as error:
        await client.aclose()
        raise AIRuntimeError("The AI provider could not be reached.") from error

    if not 200 <= response.status_code < 300:
        status_code = response.status_code
        await response.aclose()
        await client.aclose()
        if status_code in {400, 422}:
            raise AIModelUnavailableError(
                "The selected AI model rejected the Assistant request. Check the model's streaming, tool, and reasoning capabilities in Settings."
            )
        if status_code in {401, 403}:
            raise AIProviderAuthenticationError("The AI provider rejected its configured credential.")
        if status_code == 429:
            raise AIRateLimitError("The AI provider rate limit was reached.")
        if status_code == 404:
            raise AIModelUnavailableError("The configured AI model was not found by its provider.")
        if 300 <= status_code < 400:
            raise AIRuntimeError("The AI provider returned a redirect, which is not allowed.")
        raise AIRuntimeError("The AI provider could not complete the request.")

    content_type = response.headers.get("content-type", "")
    if "text/event-stream" not in content_type.lower():
        await response.aclose()
        await client.aclose()
        raise AIRuntimeError("The AI provider returned an invalid streaming response.")

    return ProviderStream(response, client), content_type


def _provider_payload(payload: dict[str, Any], runtime: RuntimeModel) -> dict[str, Any]:
    outbound = dict(payload)
    outbound["model"] = runtime.external_model_id
    outbound["stream"] = True
    if not runtime.supports_tools:
        tool_choice = outbound.get("tool_choice")
        if outbound.get("tools") or (tool_choice is not None and tool_choice != "none"):
            raise AIToolCapabilityError("The selected AI model does not support Assistant tools.")
        outbound.pop("tools", None)
        outbound.pop("tool_choice", None)
        outbound.pop("parallel_tool_calls", None)
    if runtime.provider.provider_id == "openrouter":
        outbound.pop("stream_options", None)
    else:
        outbound["stream_options"] = {"include_usage": True}
    if runtime.supports_reasoning:
        if outbound.get("max_completion_tokens") is None and outbound.get("max_tokens") is not None:
            outbound["max_completion_tokens"] = outbound["max_tokens"]
        for key in ("max_tokens", "temperature", "top_p", "frequency_penalty", "presence_penalty"):
            outbound.pop(key, None)
    if runtime.provider.provider_id == "openai" and runtime.supports_reasoning and outbound.get("tools"):
        outbound.setdefault("reasoning_effort", "none")
    return outbound
