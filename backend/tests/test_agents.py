"""Agent CRUD exercises the real router, sessions, DB, and audit transaction."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.api.v1.routes import _signed_cookie
from app.api.v1 import agents as agents_api
from app.core.config import Settings
from app.core.dependencies import get_database_session
from app.main import create_app
from app.models.base import Base
from app.models.entities import (
    AIAgent,
    AIAgentNotificationDestination,
    AIAgentSkill,
    AIAgentSkillAssignment,
    AIModelConfig,
    AuditAction,
    IntegrationConnection,
    IntegrationDeliveryJob,
    Session,
    UserAccount,
)
from app.services.credential_encryption import CredentialEncryption
from app.services.agent_notifications import enqueue_agent_notification
from app.services.integration_delivery import DeliveryServiceError

PATH = "/api/v1/assistant/agents"
SKILLS = f"{PATH}/skills"


@pytest.fixture
def api(tmp_path):
    settings = Settings(
        auth_secret="x" * 32,
        database_url=f"sqlite:///{tmp_path / 'agents.db'}",
        encryption_key=Fernet.generate_key().decode("ascii"),
        worker_enabled=False,
    )
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
    yield SimpleNamespace(client=client, db=factory, engine=engine, user=user, model=model, session=session, settings=settings)
    client.close(); engine.dispose()


def payload(api, **changes):
    return dict(name="Investigator", description="Inspect workload health", instructions="Read evidence.\nExplain findings.", model_id=str(api.model.id), enabled=False) | changes


def create(api, **changes):
    response = api.client.post(PATH, json=payload(api, **changes))
    assert response.status_code == 201, response.text
    return response.json()


def notification_payload(**changes):
    return dict(provider_id="slack", label="Primary channel", destination="C123", enabled=True) | changes


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


def test_agent_notification_destinations_are_encrypted_scoped_and_testable(api):
    agent = create(api, name="Notification agent", enabled=True)
    encryption = CredentialEncryption.from_settings(api.settings)
    with api.db() as db:
        db.add(
            IntegrationConnection(
                provider="slack",
                status="connected",
                access_token_ciphertext=encryption.encrypt("access-token"),
                granted_scopes=["chat:write"],
            )
        )
        db.commit()

    path = f'{PATH}/{agent["id"]}/notifications'
    response = api.client.post(path, json=notification_payload())
    assert response.status_code == 201, response.text
    destination = response.json()
    assert destination["provider_id"] == "slack"
    assert destination["destination_hint"] != "C123"
    assert "C123" not in response.text

    with api.db() as db:
        stored = db.scalar(select(AIAgentNotificationDestination))
        assert stored is not None
        assert stored.destination_ciphertext != "C123"
        assert stored.destination_digest
        assert stored.agent_id == UUID(agent["id"])

    assert api.client.post(path, json=notification_payload()).status_code == 409
    updated = api.client.put(
        f'{path}/{destination["id"]}',
        json=notification_payload(destination="C456", enabled=False, label="Backup channel"),
    )
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False
    assert "C456" not in updated.text

    assert api.client.post(f'{path}/{destination["id"]}/test').status_code == 409
    reenabled = api.client.put(
        f'{path}/{destination["id"]}',
        json=notification_payload(destination="C456", enabled=True, label="Backup channel"),
    )
    assert reenabled.status_code == 200
    queued = api.client.post(f'{path}/{destination["id"]}/test')
    assert queued.status_code == 200, queued.text
    assert queued.json()["status"] == "queued"
    assert queued.json()["agent_id"] == agent["id"]
    with api.db() as db:
        job = db.scalar(select(IntegrationDeliveryJob))
        assert job is not None and job.agent_destination_id == UUID(destination["id"])
        assert "KubePilot agent notification test" not in (job.payload_ciphertext or "")


def test_agent_notification_destinations_reject_invalid_targets_and_non_admin_mutations(api):
    agent = create(api, name="Restricted notification agent")
    path = f'{PATH}/{agent["id"]}/notifications'
    assert api.client.post(path, json=notification_payload(destination="not-a-channel")).status_code == 422
    assert api.client.post(path, json=notification_payload(provider_id="teams")).status_code == 422

    with api.db() as db:
        db.get(UserAccount, api.user.id).role = "viewer"
        db.commit()
    assert api.client.get(path).status_code == 200
    assert api.client.post(path, json=notification_payload()).status_code == 403


def test_agent_notification_dispatch_is_idempotent_and_audited_without_content(api):
    agent = create(api, name="Dispatch agent", enabled=True)
    encryption = CredentialEncryption.from_settings(api.settings)
    with api.db() as db:
        db.add(
            IntegrationConnection(
                provider="slack",
                status="connected",
                access_token_ciphertext=encryption.encrypt("access-token"),
                granted_scopes=["chat:write"],
            )
        )
        db.commit()
    path = f'{PATH}/{agent["id"]}/notifications'
    destination = api.client.post(path, json=notification_payload()).json()
    with api.db() as db:
        first = enqueue_agent_notification(
            db,
            api.settings,
            actor_id=api.user.id,
            agent_id=UUID(agent["id"]),
            destination_id=UUID(destination["id"]),
            event_type="agent.alert",
            body="private notification body",
            idempotency_key="agent-alert-1",
        )
        second = enqueue_agent_notification(
            db,
            api.settings,
            actor_id=api.user.id,
            agent_id=UUID(agent["id"]),
            destination_id=UUID(destination["id"]),
            event_type="agent.alert",
            body="private notification body",
            idempotency_key="agent-alert-1",
        )
        assert first["deduplicated"] is False
        assert second["deduplicated"] is True
        assert first["delivery_id"] == second["delivery_id"]
        job = db.get(IntegrationDeliveryJob, first["delivery_id"])
        assert job is not None and job.agent_id == UUID(agent["id"])
        assert "private notification body" not in (job.payload_ciphertext or "")
        audits = db.scalars(select(AuditAction)).all()
        assert "private notification body" not in str([audit.context for audit in audits])


def test_agent_notification_test_maps_delivery_service_errors(api, monkeypatch):
    agent = create(api, name="Delivery race agent", enabled=True)
    destination_id = uuid4()

    def revoked_connection(*_args, **_kwargs):
        raise DeliveryServiceError(
            "integration_delivery_not_connected",
            "The integration is not connected",
            status_code=409,
        )

    monkeypatch.setattr(agents_api, "queue_test_delivery", revoked_connection)
    response = api.client.post(f'{PATH}/{agent["id"]}/notifications/{destination_id}/test')

    assert response.status_code == 409
    assert response.json() == {
        "code": "integration_delivery_not_connected",
        "message": "The integration is not connected",
    }


def test_agent_notification_listing_batches_connection_status_lookup(api):
    agent = create(api, name="Batch notification agent")
    path = f'{PATH}/{agent["id"]}/notifications'
    api.client.post(path, json=notification_payload(destination="C123"))
    api.client.post(path, json=notification_payload(destination="C456", label="Backup channel"))
    api.client.post(
        path,
        json=notification_payload(
            provider_id="gmail",
            label="Email recipient",
            destination="alerts@example.com",
        ),
    )

    statements: list[str] = []

    def capture(_connection, _cursor, statement, _parameters, _context, _executemany):
        if "integration_connections" in statement.lower():
            statements.append(statement)

    event.listen(api.engine, "before_cursor_execute", capture)
    try:
        response = api.client.get(path)
    finally:
        event.remove(api.engine, "before_cursor_execute", capture)

    assert response.status_code == 200, response.text
    assert len(response.json()["destinations"]) == 3
    assert len(statements) == 1


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


def skill_payload(**changes):
    return dict(
        name="Evidence reader",
        description="Read operational evidence",
        instructions="Inspect only the evidence supplied by trusted tools.",
    ) | changes


def test_skill_crud_safe_audit_and_assigned_count(api):
    response = api.client.post(SKILLS, json=skill_payload(name="  Evidence reader  "))
    assert response.status_code == 201, response.text
    row = response.json()
    assert row["name"] == "Evidence reader"
    assert row["created_by_id"] == str(api.user.id)
    assert row["assigned_agent_count"] == 0
    assert api.client.get(f'{SKILLS}/{row["id"]}').json()["instructions"].startswith("Inspect")
    updated = api.client.put(f'{SKILLS}/{row["id"]}', json=skill_payload(description="Updated evidence"))
    assert updated.status_code == 200 and updated.json()["description"] == "Updated evidence"
    assert api.client.get(SKILLS).json()["skills"][0]["assigned_agent_count"] == 0
    assert api.client.delete(f'{SKILLS}/{row["id"]}').json() == {"id": row["id"]}
    assert api.client.get(f'{SKILLS}/{row["id"]}').status_code == 404
    with api.db() as db:
        audits = db.scalars(select(AuditAction)).all()
        assert [audit.action for audit in audits] == [
            "assistant.agent_skill.create",
            "assistant.agent_skill.update",
            "assistant.agent_skill.delete",
        ]
        assert "Inspect only" not in str([audit.context for audit in audits])


@pytest.mark.parametrize("role", ["viewer", "operator"])
def test_non_admin_reads_but_cannot_mutate_skills(api, role):
    with api.db() as db:
        db.get(UserAccount, api.user.id).role = role
        db.commit()
    assert api.client.get(SKILLS).status_code == 200
    assert api.client.post(SKILLS, json=skill_payload()).status_code == 403


def test_skill_validation_conflict_and_assigned_delete_guard(api):
    row = api.client.post(SKILLS, json=skill_payload()).json()
    assert api.client.post(SKILLS, json=skill_payload()).status_code == 409
    assert api.client.post(SKILLS, json=skill_payload(name=" ")).status_code == 422
    agent = create(api, name="Skill user")
    with api.db() as db:
        db.add(AIAgentSkillAssignment(agent_id=UUID(agent["id"]), skill_id=UUID(row["id"]), position=0))
        db.commit()
    assert api.client.get(SKILLS).json()["skills"][0]["assigned_agent_count"] == 1
    response = api.client.delete(f'{SKILLS}/{row["id"]}')
    assert response.status_code == 409
    assert response.json()["code"] == "skill_in_use"


def test_skill_mutation_rolls_back_when_audit_fails(api, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr("app.services.agents.record_audit", broken)
    assert api.client.post(SKILLS, json=skill_payload()).status_code == 500
    assert api.client.get(SKILLS).json() == {"skills": []}


def test_agent_assignments_and_effective_capabilities_use_existing_rbac(api):
    with api.db() as db:
        db.get(AIModelConfig, api.model.id).supports_tools = True
        db.commit()
    skill = api.client.post(SKILLS, json=skill_payload()).json()
    row = create(api, name="Capability agent", skill_ids=[skill["id"]], tool_ids=["listResources", "proposeDelete"])
    assert row["skill_ids"] == [skill["id"]]
    assert row["tool_ids"] == ["listResources", "proposeDelete"]
    assert row["skills"][0]["name"] == "Evidence reader"
    capabilities = {item["id"]: item for item in row["capabilities"]}
    assert capabilities["listResources"]["status"] == "available"
    assert capabilities["proposeDelete"]["status"] == "available"
    assert capabilities["getEvents"]["status"] == "not_configured"

    assert api.client.post(PATH, json=payload(api, name="Duplicate assignment", skill_ids=[skill["id"], skill["id"]])).status_code == 422
    assert api.client.post(PATH, json=payload(api, name="Unknown tool", tool_ids=["not-a-tool"])).status_code == 422

    with api.db() as db:
        db.get(UserAccount, api.user.id).role = "viewer"
        db.commit()
    detail = api.client.get(f'{PATH}/{row["id"]}').json()
    capabilities = {item["id"]: item for item in detail["capabilities"]}
    assert capabilities["listResources"]["status"] == "available"
    assert capabilities["proposeDelete"]["status"] == "permission_denied"

    with api.db() as db:
        db.get(AIModelConfig, api.model.id).availability = "unavailable"
        db.commit()
    updated = api.client.get(f'{PATH}/{row["id"]}').json()
    assert updated["tool_ids"] == ["listResources", "proposeDelete"]
    assert {item["id"]: item for item in updated["capabilities"]}["listResources"]["status"] == "model_unavailable"


def test_templates_are_authenticated_safe_and_deterministic(api):
    first = api.client.get(f"{PATH}/templates")
    second = api.client.get(f"{PATH}/templates")
    assert first.status_code == 200
    assert first.json() == second.json()
    templates = first.json()["templates"]
    assert {template["id"] for template in templates} == {
        "workload-investigator",
        "cluster-observer",
        "helm-reviewer",
    }
    supported = {item["id"] for item in api.client.get(f"{PATH}/tools").json()["tools"]}
    assert all(set(template["tool_ids"]) <= supported for template in templates)
    assert all("credential" not in str(template).lower() for template in templates)
