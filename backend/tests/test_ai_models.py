from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import os

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.db.session import create_session_factory
from app.models.base import Base
from app.models.entities import AIModelConfig, AuditAction, UserAccount
from app.services import ai_models, ai_providers


os.environ.setdefault("KUBEPILOT_WORKER_ENABLED", "false")


CAPABILITIES = {
    "streaming": True,
    "tools": True,
    "reasoning": False,
    "vision": False,
    "large_context": True,
}


@pytest.fixture()
def model_store(tmp_path: Path) -> SimpleNamespace:
    engine = create_engine(f"sqlite:///{tmp_path / 'models.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    user_id = uuid4()
    with factory() as database:
        database.add(UserAccount(id=user_id, email="admin@example.com", password_hash="hash", role="admin"))
        database.commit()
    settings = Settings(
        auth_secret="a" * 32,
        database_url=f"sqlite:///{tmp_path / 'models.db'}",
        encryption_key=Fernet.generate_key().decode("ascii"),
        provider_allowed_hosts=("ollama",),
    )
    return SimpleNamespace(factory=factory, user_id=user_id, settings=settings)


def _create(database, store, **changes):
    values = {
        "provider_id": "ollama",
        "external_model_id": "llama3.2:latest",
        "friendly_name": "Llama 3.2",
        "enabled": False,
        "capabilities": CAPABILITIES,
    }
    values.update(changes)
    return ai_models.create_model(database, store.user_id, **values)


def _client_factory(handler):
    transport = httpx.MockTransport(handler)
    return lambda **kwargs: httpx.Client(transport=transport, **kwargs)


def _configure_ollama(database, store):
    ai_providers.save_provider(
        database,
        store.settings,
        store.user_id,
        "ollama",
        "http://ollama:11434",
        "unchanged",
        None,
    )


def test_model_create_lists_trimmed_values_and_rejects_duplicates(model_store) -> None:
    with model_store.factory() as database:
        created = _create(
            database,
            model_store,
            external_model_id="  llama3.2:latest  ",
            friendly_name="  Llama 3.2  ",
        )
        assert created["external_model_id"] == "llama3.2:latest"
        assert created["friendly_name"] == "Llama 3.2"
        assert created["availability"] == "unknown"
        assert created["enabled"] is False
        assert created["is_default"] is False
        assert created["capabilities"] == CAPABILITIES
        assert ai_models.list_models(database)[0]["id"] == created["id"]

        with pytest.raises(ai_models.AIModelConflictError):
            _create(database, model_store)
        audits = database.scalars(select(AuditAction)).all()
        assert [audit.action for audit in audits] == ["ai_model.create"]


def test_model_validation_rejects_unknown_provider_and_blank_identity(model_store) -> None:
    with model_store.factory() as database:
        with pytest.raises(ai_models.AIModelValidationError):
            _create(database, model_store, provider_id="arbitrary")
        with pytest.raises(ai_models.AIModelValidationError):
            _create(database, model_store, external_model_id="   ")
        assert database.scalar(select(AIModelConfig)) is None


def test_default_changes_are_atomic_and_protect_current_default(model_store) -> None:
    with model_store.factory() as database:
        first = _create(database, model_store, enabled=True)
        second = _create(
            database,
            model_store,
            external_model_id="qwen2.5:latest",
            friendly_name="Qwen 2.5",
            enabled=True,
        )
        for model in database.scalars(select(AIModelConfig)).all():
            model.availability = "available"
        database.commit()

        ai_models.set_default_model(database, model_store.user_id, first["id"])
        selected = ai_models.set_default_model(database, model_store.user_id, second["id"])
        assert selected["is_default"] is True
        assert database.get(AIModelConfig, first["id"]).is_default is False

        with pytest.raises(ai_models.DefaultModelConflictError):
            ai_models.update_model(
                database,
                model_store.user_id,
                second["id"],
                provider_id="ollama",
                external_model_id="qwen2.5:latest",
                friendly_name="Qwen 2.5",
                enabled=False,
                capabilities=CAPABILITIES,
            )
        with pytest.raises(ai_models.DefaultModelConflictError):
            ai_models.delete_model(database, model_store.user_id, second["id"])


def test_database_rejects_multiple_global_defaults(model_store) -> None:
    with model_store.factory() as database:
        first = AIModelConfig(provider_id="ollama", external_model_id="one", friendly_name="One", is_default=True)
        second = AIModelConfig(provider_id="ollama", external_model_id="two", friendly_name="Two", is_default=True)
        database.add_all([first, second])
        with pytest.raises(IntegrityError):
            database.commit()


def test_identity_change_resets_availability(model_store) -> None:
    with model_store.factory() as database:
        created = _create(database, model_store)
        model = database.get(AIModelConfig, created["id"])
        model.availability = "available"
        model.availability_message = "old"
        database.commit()

        updated = ai_models.update_model(
            database,
            model_store.user_id,
            created["id"],
            provider_id="ollama",
            external_model_id="llama3.3:latest",
            friendly_name="Llama 3.3",
            enabled=True,
            capabilities=CAPABILITIES,
        )
        assert updated["availability"] == "unknown"
        assert updated["availability_message"] is None
        assert updated["availability_checked_at"] is None


def test_availability_check_and_selector_contract(model_store) -> None:
    with model_store.factory() as database:
        _configure_ollama(database, model_store)
        created = _create(database, model_store, enabled=True)
        available = ai_models.check_model_availability(
            database,
            model_store.settings,
            model_store.user_id,
            created["id"],
            client_factory=_client_factory(
                lambda request: httpx.Response(200, json={"models": [{"name": "llama3.2:latest"}]})
            ),
        )
        assert available["availability"] == "available"
        eligible = ai_models.list_eligible_models(database)
        assert len(eligible) == 1
        assert eligible[0] == {
            "id": created["id"],
            "provider_id": "ollama",
            "provider_name": "Ollama",
            "external_model_id": "llama3.2:latest",
            "friendly_name": "Llama 3.2",
            "capabilities": CAPABILITIES,
            "is_default": False,
        }
        ai_models.set_default_model(database, model_store.user_id, created["id"])

        unavailable = ai_models.check_model_availability(
            database,
            model_store.settings,
            model_store.user_id,
            created["id"],
            client_factory=_client_factory(
                lambda request: httpx.Response(200, json={"models": [{"name": "another-model"}]})
            ),
        )
        assert unavailable["availability"] == "unavailable"
        assert unavailable["is_default"] is True
        assert ai_models.list_eligible_models(database) == []


def test_failed_catalog_check_is_unknown_and_safe(model_store) -> None:
    with model_store.factory() as database:
        _configure_ollama(database, model_store)
        created = _create(database, model_store, enabled=True)
        checked = ai_models.check_model_availability(
            database,
            model_store.settings,
            model_store.user_id,
            created["id"],
            client_factory=_client_factory(lambda request: httpx.Response(503, text="secret upstream body")),
        )
        assert checked["availability"] == "unknown"
        assert checked["availability_message"] == "The provider rejected the model catalog request."
        assert "secret upstream body" not in str(checked)


@pytest.mark.parametrize(
    ("provider_id", "base_url", "payload", "expected"),
    [
        ("openai", "https://api.openai.com/v1", {"data": [{"id": "gpt-4.1-mini"}]}, {"gpt-4.1-mini"}),
        ("openrouter", "https://openrouter.ai/api/v1", {"data": [{"id": "anthropic/claude-sonnet"}]}, {"anthropic/claude-sonnet"}),
        ("ollama", "http://ollama:11434", {"models": [{"model": "qwen2.5:latest"}]}, {"qwen2.5:latest"}),
    ],
)
def test_provider_catalog_adapters_normalize_allowlisted_model_ids(
    model_store,
    provider_id,
    base_url,
    payload,
    expected,
) -> None:
    with model_store.factory() as database:
        ai_providers.save_provider(
            database,
            model_store.settings,
            model_store.user_id,
            provider_id,
            base_url,
            "replace" if provider_id != "ollama" else "unchanged",
            "sk-test" if provider_id != "ollama" else None,
        )
        result = ai_providers.fetch_provider_model_ids(
            database,
            model_store.settings,
            provider_id,
            client_factory=_client_factory(lambda request: httpx.Response(200, json=payload)),
        )
        assert result.status == "connected"
        assert result.model_ids == frozenset(expected)


def test_malformed_catalog_items_fail_closed(model_store) -> None:
    with model_store.factory() as database:
        _configure_ollama(database, model_store)
        result = ai_providers.fetch_provider_model_ids(
            database,
            model_store.settings,
            "ollama",
            client_factory=_client_factory(lambda request: httpx.Response(200, json={"models": ["not-an-object"]})),
        )
        assert result.status == "failed"
        assert result.model_ids == frozenset()


def test_selector_excludes_available_model_when_provider_is_not_configured(model_store) -> None:
    with model_store.factory() as database:
        created = _create(database, model_store, enabled=True)
        database.get(AIModelConfig, created["id"]).availability = "available"
        database.commit()
        assert ai_models.list_eligible_models(database) == []


@pytest.fixture()
def model_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    database_url = f"sqlite:///{tmp_path / 'models-api.db'}"
    monkeypatch.setenv("KUBEPILOT_AUTH_SECRET", "x" * 32)
    monkeypatch.setenv("KUBEPILOT_DATABASE_URL", database_url)
    monkeypatch.setenv("KUBEPILOT_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("KUBEPILOT_ADMIN_PASSWORD", "kubepilot")
    monkeypatch.setenv("KUBEPILOT_WORKER_ENABLED", "false")

    from app.main import create_app

    settings = Settings.from_env()
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    return SimpleNamespace(
        settings=settings,
        factory=create_session_factory(settings),
        client=TestClient(create_app()),
    )


def _login(client: TestClient, email: str, password: str) -> dict:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def _cookie(session: dict) -> dict[str, str]:
    return {"cookie": f"kubepilot_session={session['cookie']}"}


def test_model_api_is_admin_only_and_returns_stable_conflicts(model_api) -> None:
    payload = {
        "provider_id": "ollama",
        "external_model_id": "llama3.2:latest",
        "friendly_name": "Llama 3.2",
        "enabled": False,
        "capabilities": CAPABILITIES,
    }
    with model_api.client as client:
        admin = _login(client, "admin@example.com", "kubepilot")
        admin_headers = _cookie(admin)
        created = client.post("/api/v1/settings/models", headers=admin_headers, json=payload)
        assert created.status_code == 201, created.text
        assert created.json()["external_model_id"] == "llama3.2:latest"
        assert client.get("/api/v1/settings/models", headers=admin_headers).json()["models"][0]["id"] == created.json()["id"]

        duplicate = client.post("/api/v1/settings/models", headers=admin_headers, json=payload)
        assert duplicate.status_code == 409
        assert duplicate.json()["code"] == "model_conflict"

        user = client.post(
            "/api/v1/users",
            headers=admin_headers,
            json={"email": "viewer@example.com", "password": "correct-horse-00", "role": "viewer"},
        )
        assert user.status_code == 201, user.text
        viewer = _login(client, "viewer@example.com", "correct-horse-00")
        viewer_headers = _cookie(viewer)
        assert client.get("/api/v1/settings/models", headers=viewer_headers).status_code == 403
        eligible = client.get("/api/v1/assistant/models", headers=viewer_headers)
        assert eligible.status_code == 200
        assert eligible.json() == {"models": []}
