from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.routes import _signed_cookie
from app.core.config import Settings
from app.main import create_app
from app.models.base import Base
from app.models.entities import AuditAction, Session, UserAccount


@pytest.fixture()
def audit_api(tmp_path, monkeypatch):
    settings = Settings(
        auth_secret="x" * 32,
        database_url=f"sqlite:///{tmp_path / 'audit.db'}",
        worker_enabled=False,
    )
    monkeypatch.setenv("KUBEPILOT_AUTH_SECRET", settings.auth_secret)
    monkeypatch.setenv("KUBEPILOT_DATABASE_URL", settings.database_url)
    monkeypatch.setenv("KUBEPILOT_WORKER_ENABLED", "false")

    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    expiry = datetime.now(timezone.utc) + timedelta(hours=1)
    cookies: dict[str, str] = {}

    with factory() as database:
        users = {
            role: UserAccount(email=f"{role}@example.com", password_hash="hash", role=role)
            for role in ("admin", "operator", "viewer")
        }
        target = UserAccount(email="target@example.com", password_hash="hash", role="viewer")
        database.add_all([*users.values(), target])
        database.flush()
        for role, user in users.items():
            cookie, token_hash = _signed_cookie(user.email, int(expiry.timestamp() * 1000), settings.auth_secret)
            cookies[role] = cookie
            database.add(Session(user_id=user.id, token_hash=token_hash, expires_at=expiry))

        base_time = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
        database.add_all(
            [
                AuditAction(
                    actor_id=users["admin"].id,
                    action="settings.update",
                    resource_type="application_setting",
                    resource_id="ui.theme",
                    target_user_id=target.id,
                    result="succeeded",
                    context='{"changed": "theme", "api_key": "sk-secret", "nested": {"token": "hidden"}}',
                    created_at=base_time + timedelta(minutes=3),
                ),
                AuditAction(
                    actor_id=users["admin"].id,
                    action="resource.delete_result",
                    resource_type="pod",
                    resource_id="default/web",
                    result="success",
                    context='{"namespace": "default", "name": "web"}',
                    created_at=base_time + timedelta(minutes=2),
                ),
                AuditAction(
                    actor_id=None,
                    action="marketplace.install_failed",
                    resource_type="installation_job",
                    resource_id="job-1",
                    result="failure",
                    context="helm failed with token=secret-value",
                    created_at=base_time + timedelta(minutes=1),
                ),
                AuditAction(
                    actor_id=users["admin"].id,
                    action="assistant.tool",
                    resource_type="assistant_tool",
                    resource_id="inspectResource",
                    result="success",
                    context='{"cluster": "primary", "duration_ms": 12, "prompt": "show secret"}',
                    created_at=base_time,
                ),
            ]
        )
        database.commit()

    app = create_app()
    app.state.settings = settings
    client = TestClient(app)
    yield SimpleNamespace(client=client, cookies=cookies, factory=factory)
    client.close()
    engine.dispose()


def _cookie(cookie: str) -> dict[str, str]:
    return {"cookie": f"kubepilot_session={cookie}"}


def test_audit_logs_are_admin_only(audit_api) -> None:
    response = audit_api.client.get("/api/v1/settings/audit-logs", headers=_cookie(audit_api.cookies["admin"]))
    assert response.status_code == 200, response.text

    for role in ("operator", "viewer"):
        denied = audit_api.client.get("/api/v1/settings/audit-logs", headers=_cookie(audit_api.cookies[role]))
        assert denied.status_code == 403
        assert denied.json()["code"] == "insufficient_permissions"


def test_audit_logs_are_newest_first_and_paginated(audit_api) -> None:
    response = audit_api.client.get(
        "/api/v1/settings/audit-logs?limit=2&page=0",
        headers=_cookie(audit_api.cookies["admin"]),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 4
    assert body["total_pages"] == 2
    assert body["page"] == 0
    assert body["limit"] == 2
    assert [row["action"] for row in body["logs"]] == ["settings.update", "resource.delete_result"]
    assert body["logs"][0]["actor"] == {"id": body["logs"][0]["actor"]["id"], "email": "admin@example.com"}
    assert body["logs"][0]["target_user"]["email"] == "target@example.com"


def test_audit_logs_filter_by_category_result_resource_action_actor_and_dates(audit_api) -> None:
    admin_cookie = _cookie(audit_api.cookies["admin"])

    resource = audit_api.client.get("/api/v1/settings/audit-logs?category=resource", headers=admin_cookie)
    assert [row["action"] for row in resource.json()["logs"]] == ["resource.delete_result"]

    failure = audit_api.client.get("/api/v1/settings/audit-logs?result=failure", headers=admin_cookie)
    assert [row["action"] for row in failure.json()["logs"]] == ["marketplace.install_failed"]

    pod = audit_api.client.get("/api/v1/settings/audit-logs?resource_type=pod", headers=admin_cookie)
    assert [row["resource_id"] for row in pod.json()["logs"]] == ["default/web"]

    assistant = audit_api.client.get("/api/v1/settings/audit-logs?action=assistant", headers=admin_cookie)
    assert [row["category"] for row in assistant.json()["logs"]] == ["ai"]

    actor = audit_api.client.get("/api/v1/settings/audit-logs?actor=admin", headers=admin_cookie)
    assert {row["action"] for row in actor.json()["logs"]} == {
        "settings.update",
        "resource.delete_result",
        "assistant.tool",
    }

    dated = audit_api.client.get(
        "/api/v1/settings/audit-logs?date_from=2026-09-16T12:01:30%2B00:00&date_to=2026-09-16T12:02:30%2B00:00",
        headers=admin_cookie,
    )
    assert [row["action"] for row in dated.json()["logs"]] == ["resource.delete_result"]


def test_audit_log_context_is_redacted_and_malformed_context_is_safe(audit_api) -> None:
    response = audit_api.client.get("/api/v1/settings/audit-logs?limit=10", headers=_cookie(audit_api.cookies["admin"]))
    assert response.status_code == 200, response.text
    rows = {row["action"]: row for row in response.json()["logs"]}

    settings_context = rows["settings.update"]["context"]
    assert settings_context["changed"] == "theme"
    assert settings_context["api_key"] == "[redacted]"
    assert settings_context["nested"]["token"] == "[redacted]"

    assistant_context = rows["assistant.tool"]["context"]
    assert assistant_context["cluster"] == "primary"
    assert assistant_context["prompt"] == "[redacted]"

    failed_context = rows["marketplace.install_failed"]["context"]
    assert failed_context == {"value": "[redacted]"}
    assert "secret-value" not in response.text
