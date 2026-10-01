from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from pydantic import ValidationError

from app.api.v1.routes import _signed_cookie
from app.api.v1.conversation_schemas import ConversationCreateRequest
from app.core.audit import AuditEvent
from app.core.config import Settings
from app.main import create_app
from app.models.base import Base
from app.models.entities import AIModelConfig, AssistantConversation, AssistantConversationPart, AssistantProposal, AuditAction, ClusterConnection, Session, UserAccount


@pytest.fixture
def conversation_api(tmp_path, monkeypatch):
    settings = Settings(auth_secret="x" * 32, database_url=f"sqlite:///{tmp_path / 'conversations.db'}", worker_enabled=False)
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as database:
        operator = UserAccount(email="operator@example.com", password_hash="unused", role="operator")
        admin = UserAccount(email="admin@example.com", password_hash="unused", role="admin")
        cluster = ClusterConnection(name="primary", endpoint="private", kubeconfig_ref="in-cluster", status="active")
        database.add_all([operator, admin, cluster])
        database.flush()
        cookies = {}
        for user in (operator, admin):
            expiry = datetime.now(timezone.utc) + timedelta(hours=1)
            cookie, token_hash = _signed_cookie(user.email, int(expiry.timestamp() * 1000), settings.auth_secret)
            database.add(Session(user_id=user.id, token_hash=token_hash, expires_at=expiry))
            cookies[user.role] = cookie
        database.commit()
    app = create_app()
    app.state.settings = settings
    monkeypatch.setenv("KUBEPILOT_AUTH_SECRET", settings.auth_secret)
    monkeypatch.setenv("KUBEPILOT_DATABASE_URL", settings.database_url)
    monkeypatch.setenv("KUBEPILOT_WORKER_ENABLED", "false")
    with TestClient(app) as client:
        client.cookies.set("kubepilot_session", cookies["operator"])
        yield SimpleNamespace(client=client, db=factory, engine=engine, cookies=cookies, operator=operator, admin=admin, cluster=cluster)
    engine.dispose()


def conversation_body():
    return {
        "mode": "direct",
        "model_id": None,
        "agent_id": None,
        "context": {"cluster": "primary", "namespace": "default"},
    }


def test_conversation_schema_accepts_json_uuid_strings_but_rejects_invalid_ids():
    model_id = str(uuid4())
    parsed = ConversationCreateRequest.model_validate({**conversation_body(), "model_id": model_id})
    assert parsed.model_id == UUID(model_id)

    with pytest.raises(ValidationError):
        ConversationCreateRequest.model_validate({**conversation_body(), "model_id": "not-a-uuid"})


def test_user_conversation_round_trip_is_sanitized_and_ordered(conversation_api):
    created = conversation_api.client.post("/api/v1/assistant/conversations", json=conversation_body())
    assert created.status_code == 201, created.text
    conversation_id = created.json()["id"]

    saved = conversation_api.client.put(
        f"/api/v1/assistant/conversations/{conversation_id}/messages",
        json={
            **conversation_body(),
            "messages": [
                {"id": "user", "role": "user", "parts": [{"type": "text", "text": "Show health password=NEVER-SAVE"}]},
                {"id": "assistant", "role": "assistant", "parts": [{"type": "text", "text": "The workload is healthy."}, {"type": "tool-inspect", "output": {"data": "NEVER-SAVE", "status": "pending"}}]},
            ],
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["title"] == "Show health password=[REDACTED]"
    assert len(saved.json()["parts"]) == 3
    assert [part["sequence"] for part in saved.json()["parts"]] == [0, 1, 2]
    assert "NEVER-SAVE" not in saved.text
    assert saved.json()["parts"][2]["payload"].get("output") == {"status": "pending"}

    detail = conversation_api.client.get(f"/api/v1/assistant/conversations/{conversation_id}")
    assert detail.status_code == 200
    assert detail.json()["owner"] is None
    assert conversation_api.client.get("/api/v1/assistant/conversations?search=health").json()["total"] == 1


def test_create_accepts_selected_model_id_from_json(conversation_api):
    with conversation_api.db() as database:
        model = AIModelConfig(provider_id="openai", external_model_id="gpt-test", friendly_name="GPT Test")
        database.add(model)
        database.commit()
        model_id = str(model.id)

    response = conversation_api.client.post(
        "/api/v1/assistant/conversations",
        json={**conversation_body(), "model_id": model_id},
    )

    assert response.status_code == 201, response.text
    assert response.json()["model_id"] == model_id


def test_user_scope_and_admin_management_are_separate_and_audited(conversation_api):
    created = conversation_api.client.post("/api/v1/assistant/conversations", json=conversation_body()).json()
    conversation_id = created["id"]

    conversation_api.client.cookies.set("kubepilot_session", conversation_api.cookies["admin"])
    listed = conversation_api.client.get("/api/v1/assistant/conversations")
    assert listed.status_code == 200
    assert listed.json()["conversations"][0]["owner"]["email"] == "operator@example.com"
    opened = conversation_api.client.get(f"/api/v1/assistant/conversations/{conversation_id}")
    assert opened.status_code == 200
    assert opened.json()["owner"]["email"] == "operator@example.com"
    renamed = conversation_api.client.patch(f"/api/v1/assistant/conversations/{conversation_id}", json={"title": "Admin review"})
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Admin review"

    retention = conversation_api.client.get("/api/v1/assistant/conversations/retention")
    assert retention.json() == {"retention_days": 30}
    assert conversation_api.client.put("/api/v1/assistant/conversations/retention", json={"retention_days": 0}).status_code == 422
    assert conversation_api.client.put("/api/v1/assistant/conversations/retention", json={"retention_days": 90}).json() == {"retention_days": 90}

    with conversation_api.db() as database:
        row = database.get(AssistantConversation, UUID(conversation_id))
        row.updated_at = datetime.now(timezone.utc) - timedelta(days=100)
        database.commit()
    purged = conversation_api.client.post("/api/v1/assistant/conversations/purge")
    assert purged.status_code == 200
    assert purged.json()["deleted"] == 1
    with conversation_api.db() as database:
        actions = list(database.scalars(select(AuditAction).where(AuditAction.action.in_({
            AuditEvent.ASSISTANT_CONVERSATION_LISTED,
            AuditEvent.ASSISTANT_CONVERSATION_VIEWED,
            AuditEvent.ASSISTANT_CONVERSATION_RENAMED,
            AuditEvent.ASSISTANT_CONVERSATION_RETENTION_UPDATED,
            AuditEvent.ASSISTANT_CONVERSATION_RETENTION_VIEWED,
            AuditEvent.ASSISTANT_CONVERSATION_PURGED,
        }))))
        assert {action.action for action in actions} == {
            AuditEvent.ASSISTANT_CONVERSATION_LISTED,
            AuditEvent.ASSISTANT_CONVERSATION_VIEWED,
            AuditEvent.ASSISTANT_CONVERSATION_RENAMED,
            AuditEvent.ASSISTANT_CONVERSATION_RETENTION_UPDATED,
            AuditEvent.ASSISTANT_CONVERSATION_RETENTION_VIEWED,
            AuditEvent.ASSISTANT_CONVERSATION_PURGED,
        }
        assert all("conversation" not in (action.context or "") for action in actions)


def test_pending_proposal_reference_is_metadata_only(conversation_api):
    with conversation_api.db() as database:
        proposal = AssistantProposal(
            actor_id=conversation_api.operator.id,
            session_id=uuid4(),
            cluster_id=conversation_api.cluster.id,
            arguments={"action": "restart", "name": "web"},
            precondition={"uid": "uid"},
            status="pending",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
        database.add(proposal)
        database.commit()
        proposal_id = str(proposal.id)

    created = conversation_api.client.post("/api/v1/assistant/conversations", json=conversation_body()).json()
    saved = conversation_api.client.put(
        f"/api/v1/assistant/conversations/{created['id']}/messages",
        json={
            **conversation_body(),
            "messages": [{"id": "assistant", "role": "assistant", "parts": [{"type": "tool-propose", "output": {"proposal_id": proposal_id, "status": "pending"}}]}],
        },
    )
    assert saved.status_code == 200
    assert saved.json()["parts"][0]["proposal_id"] == proposal_id
    assert conversation_api.client.get(f"/api/v1/assistant/proposals/{proposal_id}").status_code == 404
