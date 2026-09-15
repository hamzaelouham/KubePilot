import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from cryptography.fernet import Fernet
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.db.session import create_session_factory
from app.models.base import Base
from app.models.entities import AIModelConfig, ApplicationCredential, ApplicationSetting, UserAccount
from app.services.ai_providers import PROVIDER_DEFINITIONS
from app.services.ai_runtime import (
    AIModelUnavailableError,
    AINotConfiguredError,
    AIProviderAuthenticationError,
    AIRateLimitError,
    AIRuntimeError,
    AIProviderTimeoutError,
    MAX_STREAM_CHUNK_BYTES,
    open_chat_stream,
    resolve_runtime_model,
)
from app.services.credential_encryption import CredentialEncryption


@pytest.fixture()
def runtime_store(tmp_path: Path) -> SimpleNamespace:
    database_url = f"sqlite:///{tmp_path / 'runtime.db'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    settings = Settings(
        auth_secret="a" * 32,
        database_url=database_url,
        encryption_key=Fernet.generate_key().decode("ascii"),
        provider_allowed_hosts=("openai.test", "openrouter.test", "ollama.test"),
    )
    with factory() as database:
        database.add(UserAccount(id=uuid4(), email="admin@example.com", password_hash="hash", role="admin"))
        database.commit()
    return SimpleNamespace(factory=factory, settings=settings)


def _configure(runtime_store, provider_id: str = "ollama"):
    definition = PROVIDER_DEFINITIONS[provider_id]
    external_model_id = {
        "openai": "gpt-test",
        "openrouter": "vendor/model-test",
        "ollama": "llama-test:latest",
    }[provider_id]
    base_url = {
        "openai": "http://openai.test/v1",
        "openrouter": "http://openrouter.test/api/v1",
        "ollama": "http://ollama.test:11434",
    }[provider_id]
    with runtime_store.factory() as database:
        database.add(
            ApplicationSetting(key=definition.setting_key, value_json={"base_url": base_url})
        )
        if definition.credential_key:
            database.add(
                ApplicationCredential(
                    credential_key=definition.credential_key,
                    ciphertext=CredentialEncryption.from_settings(runtime_store.settings).encrypt("secret-provider-key"),
                )
            )
        database.add(
            AIModelConfig(
                provider_id=provider_id,
                external_model_id=external_model_id,
                friendly_name="Runtime model",
                enabled=True,
                is_default=True,
                supports_streaming=True,
                supports_tools=True,
                availability="available",
            )
        )
        database.commit()
    return external_model_id


def _payload(**changes):
    value = {
        "model": "default",
        "messages": [{"role": "user", "content": "Inspect the cluster"}],
        "stream": True,
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "inspectResource",
                    "description": "Inspect one resource",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ],
    }
    value.update(changes)
    return value


def _run(coro):
    return asyncio.run(coro)


async def _consume(stream):
    return b"".join([chunk async for chunk in stream])


def test_runtime_model_requires_eligible_configured_default(runtime_store) -> None:
    with runtime_store.factory() as database:
        with pytest.raises(AINotConfiguredError):
            resolve_runtime_model(database, runtime_store.settings)

    _configure(runtime_store)
    with runtime_store.factory() as database:
        model = database.query(AIModelConfig).one()
        model.supports_tools = False
        database.commit()
        with pytest.raises(AIModelUnavailableError):
            resolve_runtime_model(database, runtime_store.settings)


@pytest.mark.parametrize(
    ("provider_id", "expected_path", "expects_auth"),
    [
        ("openai", "/v1/chat/completions", True),
        ("openrouter", "/api/v1/chat/completions", True),
        ("ollama", "/v1/chat/completions", False),
    ],
)
def test_direct_adapters_replace_identity_and_keep_credentials_server_side(
    runtime_store, provider_id, expected_path, expects_auth
) -> None:
    external_model_id = _configure(runtime_store, provider_id)
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\ndata: [DONE]\n\n',
        )

    transport = httpx.MockTransport(handler)
    factory = lambda **kwargs: httpx.AsyncClient(transport=transport, **kwargs)
    with runtime_store.factory() as database:
        stream, content_type = _run(
            open_chat_stream(
                database,
                runtime_store.settings,
                _payload(model="default"),
                client_factory=factory,
            )
        )
        content = _run(_consume(stream))

    assert httpx.URL(seen["url"]).path == expected_path
    assert seen["body"]["model"] == external_model_id
    assert seen["body"]["stream"] is True
    assert seen["authorization"] == ("Bearer secret-provider-key" if expects_auth else None)
    assert "secret-provider-key" not in content.decode()
    assert "text/event-stream" in content_type
    assert content.endswith(b"data: [DONE]\n\n")


@pytest.mark.parametrize(
    ("status", "error_type"),
    [(401, AIProviderAuthenticationError), (403, AIProviderAuthenticationError), (404, AIModelUnavailableError), (429, AIRateLimitError), (500, AIRuntimeError), (302, AIRuntimeError)],
)
def test_provider_statuses_are_normalized_without_raw_body(runtime_store, status, error_type) -> None:
    _configure(runtime_store)

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text="upstream secret detail", headers={"location": "http://attacker.test"})

    factory = lambda **kwargs: httpx.AsyncClient(transport=httpx.MockTransport(handler), **kwargs)
    with runtime_store.factory() as database:
        with pytest.raises(error_type) as error:
            _run(open_chat_stream(database, runtime_store.settings, _payload(), client_factory=factory))
    assert "upstream secret detail" not in str(error.value)


def test_non_event_stream_is_rejected(runtime_store) -> None:
    _configure(runtime_store)
    factory = lambda **kwargs: httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={"secret": "detail"})),
        **kwargs,
    )
    with runtime_store.factory() as database:
        with pytest.raises(AIRuntimeError, match="invalid streaming response"):
            _run(open_chat_stream(database, runtime_store.settings, _payload(), client_factory=factory))


def test_timeout_and_oversized_stream_are_safe_and_close_resources(runtime_store) -> None:
    _configure(runtime_store)

    async def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("secret timeout detail", request=request)

    timeout_factory = lambda **kwargs: httpx.AsyncClient(
        transport=httpx.MockTransport(timeout_handler), **kwargs
    )
    with runtime_store.factory() as database:
        with pytest.raises(AIProviderTimeoutError, match="timed out") as error:
            _run(open_chat_stream(database, runtime_store.settings, _payload(), client_factory=timeout_factory))
    assert "secret timeout detail" not in str(error.value)

    oversized_factory = lambda **kwargs: httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=b"x" * (MAX_STREAM_CHUNK_BYTES + 1),
            )
        ),
        **kwargs,
    )
    with runtime_store.factory() as database:
        stream, _content_type = _run(
            open_chat_stream(database, runtime_store.settings, _payload(), client_factory=oversized_factory)
        )
        with pytest.raises(AIRuntimeError, match="oversized streaming response"):
            _run(_consume(stream))
        assert stream._closed is True


@pytest.fixture()
def runtime_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    database_url = f"sqlite:///{tmp_path / 'runtime-api.db'}"
    monkeypatch.setenv("KUBEPILOT_AUTH_SECRET", "x" * 32)
    monkeypatch.setenv("KUBEPILOT_DATABASE_URL", database_url)
    monkeypatch.setenv("KUBEPILOT_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("KUBEPILOT_ADMIN_PASSWORD", "kubepilot")
    monkeypatch.setenv("KUBEPILOT_WORKER_ENABLED", "false")

    from app.main import create_app

    settings = Settings.from_env()
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    create_session_factory(settings)
    app = create_app()
    app.state.settings = settings
    return TestClient(app)


def test_inference_endpoint_reauthenticates_and_rejects_model_override(runtime_api) -> None:
    assert runtime_api.post("/api/v1/assistant/inference/chat/completions", json=_payload()).status_code == 401
    login = runtime_api.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "kubepilot"})
    assert login.status_code == 200
    headers = {"cookie": f"kubepilot_session={login.json()['cookie']}"}
    response = runtime_api.post(
        "/api/v1/assistant/inference/chat/completions",
        headers=headers,
        json=_payload(model="attacker/model", endpoint="http://attacker.test", authorization="secret"),
    )
    assert response.status_code == 422
    assert response.json() == {"code": "invalid_ai_request", "message": "The AI request is invalid."}
