"""Agent CRUD exercises the real router, sessions, DB, and audit transaction."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.api.v1.routes import _signed_cookie
from app.core.config import Settings
from app.core.dependencies import get_database_session
from app.main import create_app
from app.models.base import Base
from app.models.entities import AIAgent, AIModelConfig, AuditAction, Session, UserAccount

PATH = "/api/v1/assistant/agents"


@pytest.fixture
def api(tmp_path):
    settings = Settings(auth_secret="x" * 32, database_url=f"sqlite:///{tmp_path / 'agents.db'}", worker_enabled=False)
    engine = create_engine(settings.database_url)
    event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        user = UserAccount(email="admin@example.com", password_hash="unused", role="admin")
        model = AIModelConfig(provider_id="openai", external_model_id="test", friendly_name="Test model", enabled=True, availability="available")
        db.add_all([user, model]); db.flush()
        expires = datetime.now(timezone.utc) + timedelta(hours=1)
        cookie, token_hash = _signed_cookie(user.email, int(expires.timestamp() * 1000), settings.auth_secret)
        session = Session(user_id=user.id, token_hash=token_hash, expires_at=expires)
        db.add(session); db.commit()
    app = create_app()
    app.state.settings = settings

    def database():
        with factory() as db:
            yield db

    app.dependency_overrides[get_database_session] = database
    client = TestClient(app, raise_server_exceptions=False)
    client.cookies.set("kubepilot_session", cookie)
    yield SimpleNamespace(client=client, db=factory, user=user, model=model, session=session)
    client.close(); engine.dispose()


def payload(api, **changes):
    return dict(name="Investigator", description="Inspect workload health", instructions="Read evidence.\nExplain findings.", model_id=str(api.model.id), enabled=False) | changes


def create(api, **changes):
    response = api.client.post(PATH, json=payload(api, **changes))
    assert response.status_code == 201, response.text
    return response.json()


def test_persisted_crud_safe_audit_and_case_sensitive_names(api):
    row = create(api, name="  Investigator  ")
    assert row["name"] == "Investigator"
    assert row["created_by_id"] == str(api.user.id)
    with api.db() as db:
        assert db.get(AIAgent, UUID(row["id"])).instructions == payload(api)["instructions"]
    assert api.client.post(PATH, json=payload(api)).status_code == 409
    create(api, name="investigator")
    path = f'{PATH}/{row["id"]}'
    assert api.client.get(path).json()["model"]["friendly_name"] == "Test model"
    response = api.client.put(path, json=payload(api, enabled=True, name="Updated"))
    assert response.status_code == 200 and response.json()["enabled"]
    assert len(api.client.get(PATH).json()["agents"]) == 2
    assert api.client.delete(path).json() == {"id": row["id"]}
    assert api.client.delete(path).status_code == 404
    with api.db() as db:
        audits = db.scalars(select(AuditAction)).all()
        assert len(audits) == 4
        assert all(a.action.startswith("assistant.agent.") for a in audits)
        assert "Read evidence" not in str([a.context for a in audits])


@pytest.mark.parametrize("role", ["viewer", "operator"])
def test_non_admin_reads_but_cannot_mutate(api, role):
    row = create(api)
    with api.db() as db:
        db.get(UserAccount, api.user.id).role = role; db.commit()
    assert api.client.get(PATH).status_code == 200
    assert api.client.get(f'{PATH}/{row["id"]}').status_code == 200
    assert api.client.post(PATH, json=payload(api)).status_code == 403
    assert api.client.put(f'{PATH}/{row["id"]}', json=payload(api)).status_code == 403
    assert api.client.delete(f'{PATH}/{row["id"]}').status_code == 403


@pytest.mark.parametrize("changes", [{"name": " "}, {"instructions": " "}, {"description": ""}, {"model_id": str(uuid4())}, {"created_by_id": str(uuid4())}, {"enabled": "true"}, {"name": "a" * 129}, {"instructions": "a\x00b"}, {"model_id": None}])
def test_invalid_or_forged_input(api, changes):
    assert api.client.post(PATH, json=payload(api, **changes)).status_code == 422
    assert api.client.get(PATH).json() == {"agents": []}


def test_model_outage_and_removal_do_not_delete_definition(api):
    row = create(api, enabled=True)
    path = f'{PATH}/{row["id"]}'
    with api.db() as db:
        db.get(AIModelConfig, api.model.id).availability = "unavailable"; db.commit()
    assert api.client.put(path, json=payload(api, enabled=True, instructions="Edited")).status_code == 200
    assert api.client.put(path, json=payload(api, enabled=False)).status_code == 200
    assert api.client.put(path, json=payload(api, enabled=True)).status_code == 422
    with api.db() as db:
        db.delete(db.get(AIModelConfig, api.model.id)); db.commit()
    missing = api.client.get(path).json()
    assert missing["model"] is None and missing["model_id"] is None
    assert api.client.put(path, json=payload(api, model_id=None, enabled=False)).status_code == 200
    assert api.client.put(path, json=payload(api, model_id=None, enabled=True)).status_code == 422
    assert api.client.delete(path).status_code == 200


def test_transaction_rolls_back_when_audit_fails(api, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("audit unavailable")
    monkeypatch.setattr("app.services.agents.record_audit", broken)
    assert api.client.post(PATH, json=payload(api)).status_code == 500
    assert api.client.get(PATH).json() == {"agents": []}


def test_missing_restricted_and_expired_sessions(api):
    with api.db() as db:
        db.get(Session, api.session.id).restricted = True; db.commit()
    assert api.client.get(PATH).status_code == 403
    with api.db() as db:
        db.get(Session, api.session.id).expires_at = datetime.now(timezone.utc) - timedelta(hours=1); db.commit()
    assert api.client.get(PATH).status_code == 401
    api.client.cookies.clear()
    assert api.client.get(PATH).status_code == 401


def test_body_limit_and_invalid_identifier(api):
    assert api.client.post(PATH, json=payload(api, instructions="a" * 256_001)).status_code == 413
    assert api.client.get(PATH + "/not-a-uuid").status_code == 422
    assert api.client.get(PATH + "/" + str(uuid4())).status_code == 404
