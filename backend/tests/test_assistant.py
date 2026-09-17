"""Real HTTP/session/database approval boundaries; Kubernetes effects are fakes."""
import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.api.v1.routes import _signed_cookie
from app.api.v1 import assistant as assistant_api
from app.assistant.sanitize import diagnostic_projection, safe_text
from app.core.audit import AuditEvent
from app.core.config import Settings
from app.kubernetes.resource_management import ResourceManagementError
from app.main import create_app
from app.models.base import Base
from app.models.entities import AssistantProposal, AuditAction, ClusterConnection, Session, UserAccount
from app.services.ai_runtime import AINotConfiguredError, AIProviderTimeoutError


@pytest.fixture
def api(tmp_path, monkeypatch):
    settings = Settings(auth_secret="x" * 32, database_url=f"sqlite:///{tmp_path / 'assistant.db'}", worker_enabled=False)
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        user = UserAccount(email="ops@example.com", password_hash="unused", role="operator")
        cluster = ClusterConnection(name="primary", endpoint="private-endpoint", kubeconfig_ref="in-cluster", kubeconfig_content="NEVER-EXPOSE", status="active")
        db.add_all([user, cluster]); db.flush()
        expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        cookie, token_hash = _signed_cookie(user.email, int(expiry.timestamp() * 1000), settings.auth_secret)
        session = Session(user_id=user.id, token_hash=token_hash, expires_at=expiry)
        db.add(session); db.commit()
    app = create_app()
    app.state.settings = settings
    monkeypatch.setenv("KUBEPILOT_AUTH_SECRET", settings.auth_secret)
    monkeypatch.setenv("KUBEPILOT_DATABASE_URL", settings.database_url)
    monkeypatch.setenv("KUBEPILOT_WORKER_ENABLED", "false")
    effects = []
    current = SimpleNamespace(uid="object-uid", resource_version="12", deletion_timestamp=None)

    class Kubernetes:
        def read(self, kind, namespace, name):
            return SimpleNamespace(metadata=current, to_dict=lambda: {"metadata": {"name": name, "namespace": namespace, "uid": current.uid}, "spec": {"env": [{"value": "NEVER-EXPOSE"}]}, "status": {"phase": "Pending"}})

        def patch_deployment(self, namespace, name, body):
            effects.append(("patch", namespace, name, body))

        def delete(self, kind, namespace, name, uid):
            effects.append(("delete", namespace, name, uid))

        def bounded_resources(self, kind, namespace, limit):
            assert limit == 100
            return [self.read(kind, namespace, "web")], True

        def _call(self, kind, method, operation, **kwargs):
            assert method == "read_namespaced_pod_log"
            assert kwargs["previous"] and kwargs["container"] == "web"
            assert kwargs["tail_lines"] == 100 and kwargs["limit_bytes"] == 16000
            return "CrashLoopBackOff password=NEVER-EXPOSE\nconnection refused"

    @contextmanager
    def management(_cluster):
        yield Kubernetes()

    for module in ("app.assistant.actions", "app.assistant.observations", "app.api.v1.resource_management"):
        monkeypatch.setattr(f"{module}.management_client", management)
    with TestClient(app) as client:
        client.cookies.set("kubepilot_session", cookie)
        yield SimpleNamespace(client=client, db=factory, user=user, session=session, cluster=cluster, effects=effects, current=current, settings=settings)
    engine.dispose()


def proposal(api, **extra):
    response = api.client.post("/api/v1/assistant/proposals", json={"action": "scale", "cluster": "primary", "namespace": "default", "name": "web", "replicas": 5, **extra})
    assert response.status_code == 201, response.text
    assert api.effects == []
    return response.json()["proposal_id"]


def decide(api, identity, **extra):
    return api.client.post(f"/api/v1/assistant/proposals/{identity}/decision", json={"approved": True, "cluster": "primary", "confirm_name": "web", **extra})


def test_read_requires_active_session_and_never_exposes_cluster_credentials(api):
    response = api.client.post("/api/v1/assistant/observe/list", json={"cluster": "primary", "namespace": "default"})
    assert response.status_code == 200, response.text
    assert response.json()["result"]["truncated"] is True
    assert "NEVER-EXPOSE" not in response.text and "private-endpoint" not in response.text
    failed = api.client.post("/api/v1/assistant/observe/list", json={"cluster": "missing", "namespace": "default"})
    assert failed.status_code == 404
    with api.db() as db:
        actions = list(db.scalars(select(AuditAction).where(AuditAction.action == AuditEvent.ASSISTANT_TOOL)))
        assert [action.result for action in actions] == ["success", "failed"]
        serialized = "".join(action.context or "" for action in actions)
        assert "NEVER-EXPOSE" not in serialized and "private-endpoint" not in serialized
        assert set(json.loads(actions[0].context)) == {"cluster", "duration_ms"}
    api.client.cookies.clear()
    assert api.client.post("/api/v1/assistant/observe/list", json={"cluster": "primary"}).status_code == 401


def test_inference_failures_before_headers_are_audited_without_request_content(api, monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise AINotConfiguredError("secret provider detail")

    monkeypatch.setattr(assistant_api, "resolve_runtime_model", unavailable)
    response = api.client.post(
        "/api/v1/assistant/inference/chat/completions",
        json={
            "model": "default",
            "messages": [{"role": "user", "content": "prompt-secret"}],
            "stream": True,
        },
    )
    assert response.status_code == 503
    with api.db() as db:
        action = db.scalar(select(AuditAction).where(AuditAction.action == AuditEvent.ASSISTANT_INFERENCE))
        assert action is not None
        assert action.actor_id == api.user.id
        assert action.resource_type == "ai_model"
        assert action.resource_id == "default"
        assert action.result == "failed"
        context = json.loads(action.context)
        assert context["error_code"] == "ai_not_configured"
        assert "prompt-secret" not in action.context
        assert "secret provider detail" not in action.context


def test_stream_terminal_outcomes_are_audited_exactly_once_and_redacted(api):
    class Stream:
        def __init__(self, outcome):
            self.outcome = outcome
            self.sent = False
            self.closed = False

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.outcome == "failed":
                raise AIProviderTimeoutError("provider-secret")
            if not self.sent:
                self.sent = True
                return b"response-secret"
            raise StopAsyncIteration

        async def aclose(self):
            self.closed = True

    runtime = SimpleNamespace(
        model_id=uuid4(),
        provider=SimpleNamespace(provider_id="openai"),
        supports_tools=True,
    )

    async def exercise():
        with api.db() as db:
            actor = SimpleNamespace(user_id=api.user.id)
            success_source = Stream("success")
            success = assistant_api.AuditedInferenceStream(success_source, db, actor, runtime.model_id, runtime, 0)
            assert await success.__anext__() == b"response-secret"
            with pytest.raises(StopAsyncIteration):
                await success.__anext__()
            await success.aclose()

            failed_source = Stream("failed")
            failed = assistant_api.AuditedInferenceStream(failed_source, db, actor, runtime.model_id, runtime, 0)
            with pytest.raises(AIProviderTimeoutError):
                await failed.__anext__()
            await failed.aclose()

            cancelled_source = Stream("cancelled")
            cancelled = assistant_api.AuditedInferenceStream(cancelled_source, db, actor, runtime.model_id, runtime, 0)
            await cancelled.aclose()
            await cancelled.aclose()

    asyncio.run(exercise())
    with api.db() as db:
        actions = list(db.scalars(select(AuditAction).where(AuditAction.action == AuditEvent.ASSISTANT_INFERENCE)))
        assert [action.result for action in actions] == ["success", "failed", "cancelled"]
        assert all(action.resource_id == str(runtime.model_id) for action in actions)
        contexts = [json.loads(action.context) for action in actions]
        assert contexts[0]["provider_id"] == "openai"
        assert contexts[0]["tool_mode"] == "enabled"
        assert contexts[1]["error_code"] == "ai_provider_timeout"
        assert contexts[2]["error_code"] == "request_cancelled"
        serialized = json.dumps(contexts)
        assert "response-secret" not in serialized and "provider-secret" not in serialized


def test_approval_executes_exact_snapshot_once_and_records_metadata_audit(api):
    identity = proposal(api)
    review = api.client.get(f"/api/v1/assistant/proposals/{identity}")
    assert review.json()["arguments"]["replicas"] == 5
    assert review.json()["expires_at"].endswith("+00:00")
    result = decide(api, identity)
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "submitted"
    assert api.effects == [("patch", "default", "web", {"metadata": {"uid": "object-uid", "resourceVersion": "12"}, "spec": {"replicas": 5}})]
    assert decide(api, identity).status_code == 409
    assert len(api.effects) == 1
    with api.db() as db:
        actions = list(db.scalars(select(AuditAction)))
        assert {a.action for a in actions} >= {"assistant.proposed", "assistant.decision", "assistant.result"}


@pytest.mark.parametrize("change", [{"cluster": "other"}, {"confirm_name": "different"}, {"replicas": 99}])
def test_confirmation_cannot_change_scope_target_or_arguments(api, change):
    identity = proposal(api)
    assert decide(api, identity, **change).status_code in {409, 422}
    assert api.effects == []


@pytest.mark.parametrize("field,value", [("uid", "replacement"), ("resource_version", "13")])
def test_stale_resources_never_execute(api, field, value):
    identity = proposal(api)
    setattr(api.current, field, value)
    result = decide(api, identity).json()
    assert result["status"] == "failed" and result["result"]["code"] == "stale_target"
    assert api.effects == []


def test_rejection_and_expiration_cannot_be_replayed(api):
    identity = proposal(api)
    assert decide(api, identity, approved=False).json()["status"] == "denied"
    assert decide(api, identity).status_code == 409
    identity = proposal(api)
    with api.db() as db:
        db.get(AssistantProposal, UUID(identity)).expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    assert decide(api, identity).status_code == 409
    assert api.effects == []


@pytest.mark.parametrize("change", ["session", "actor", "cluster"])
def test_proposal_is_bound_to_actor_session_and_cluster_registration(api, change):
    identity = proposal(api)
    with api.db() as db:
        record = db.get(AssistantProposal, UUID(identity))
        setattr(record, {"actor": "actor_id", "session": "session_id", "cluster": "cluster_id"}[change], uuid4())
        db.commit()
    assert decide(api, identity).status_code == (409 if change == "cluster" else 404)
    if change != "cluster":
        assert api.client.get(f"/api/v1/assistant/proposals/{identity}").status_code == 404
    assert api.effects == []


@pytest.mark.parametrize("change", ["viewer", "inactive", "restricted", "revoked"])
def test_permissions_and_session_are_checked_again_at_confirmation(api, change):
    identity = proposal(api)
    with api.db() as db:
        user = db.get(UserAccount, api.user.id)
        session = db.get(Session, api.session.id)
        if change == "viewer": user.role = "viewer"
        elif change == "inactive": user.is_active = False
        elif change == "restricted": session.restricted = True
        else: db.delete(session)
        db.commit()
    assert decide(api, identity).status_code in {401, 403}
    assert api.effects == []


@pytest.mark.parametrize("namespace", ["kube-system", "kube-public", "kube-node-lease", "kubepilot"])
def test_protected_namespaces_reject_proposals(api, namespace):
    response = api.client.post("/api/v1/assistant/proposals", json={"action": "restart", "cluster": "primary", "namespace": namespace, "name": "web"})
    assert response.status_code == 422 and response.json()["code"] == "namespace_protected", response.text
    assert api.effects == []


def test_viewer_can_inspect_but_cannot_propose(api):
    with api.db() as db:
        db.get(UserAccount, api.user.id).role = "viewer"; db.commit()
    assert api.client.post("/api/v1/assistant/observe/inspect", json={"cluster": "primary", "namespace": "default", "name": "web"}).status_code == 200
    assert api.client.post("/api/v1/assistant/proposals", json={"action": "restart", "cluster": "primary", "namespace": "default", "name": "web"}).status_code == 403


def test_unknown_outcome_is_durable_and_not_retried(api, monkeypatch):
    identity = proposal(api)
    async def fail(*args):
        api.effects.append("attempt")
        raise ResourceManagementError(504, "operation_outcome_unknown", "timeout password=NEVER-EXPOSE")
    monkeypatch.setattr("app.assistant.actions.execute", fail)
    result = decide(api, identity)
    assert result.json()["status"] == "unknown"
    assert "NEVER-EXPOSE" not in result.text
    assert decide(api, identity).status_code == 409
    assert api.effects == ["attempt"]


def test_delete_delegates_to_existing_authenticated_api(api):
    identity = proposal(api, action="delete", replicas=None, resource_type="pods")
    response = decide(api, identity)
    assert response.json()["status"] == "submitted", response.text
    assert api.effects == [("delete", "default", "web", "object-uid")]


def test_previous_container_logs_are_bounded_and_scrubbed(api):
    response = api.client.post("/api/v1/assistant/observe/logs", json={"cluster": "primary", "namespace": "default", "name": "web", "container": "web", "previous": True})
    assert response.status_code == 200
    assert "NEVER-EXPOSE" not in response.text
    assert "connection refused" in response.text


@pytest.mark.parametrize("resource", ["secrets", "configmaps", "pods", "deployments"])
def test_projection_omits_sensitive_spec_metadata_and_values(resource):
    raw = {"metadata": {"name": "web", "annotations": {"password": "NEVER-EXPOSE"}}, "data": {"config": "NEVER-EXPOSE"}, "spec": {"containers": [{"env": [{"value": "NEVER-EXPOSE"}]}]}, "status": {"container_statuses": [{"name": "web", "restart_count": 8, "state": {"waiting": {"reason": "CrashLoopBackOff", "message": "password=NEVER-EXPOSE"}}}]}}
    result = str(diagnostic_projection(raw, resource))
    assert "NEVER-EXPOSE" not in result
    if resource == "pods": assert "CrashLoopBackOff" in result


def test_text_scrubbing_retains_operational_evidence():
    text = safe_text("reason=CrashLoopBackOff password=abc Bearer xyz https://user:pass@host/path")
    assert "CrashLoopBackOff" in text
    assert all(value not in text for value in ["abc", "xyz", "user:pass"])
