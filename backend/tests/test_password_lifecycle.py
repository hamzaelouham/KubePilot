import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session as DatabaseSession

from app.api.v1.routes import _signed_cookie
from app.core.audit import AuditEvent
from app.core.config import Settings
from app.db.session import create_session_factory
from app.models.base import Base
from app.models.entities import AuditAction, UserAccount

os.environ.setdefault("KUBEPILOT_PASSWORD_TTL_DAYS", "15")


@pytest.fixture()
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    database_url = f"sqlite:///{tmp_path / 'kubepilot-lifecycle.db'}"
    monkeypatch.setenv("KUBEPILOT_AUTH_SECRET", "x" * 32)
    monkeypatch.setenv("KUBEPILOT_DATABASE_URL", database_url)
    monkeypatch.setenv("KUBEPILOT_ADMIN_EMAIL", "ops@kubepilot.io")
    monkeypatch.setenv("KUBEPILOT_ADMIN_PASSWORD", "kubepilot")

    from app.main import create_app

    settings = Settings.from_env()
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(settings)
    app = create_app()
    return SimpleNamespace(settings=settings, factory=factory, client=TestClient(app))


def cookie_header(cookie: str) -> dict[str, str]:
    return {"cookie": f"kubepilot_session={cookie}"}


def login(api: SimpleNamespace, email: str, password: str) -> dict:
    with api.client as client:
        response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def create_user(api: SimpleNamespace, email: str, role: str = "viewer") -> dict:
    admin_login = login(api, api.settings.admin_email, api.settings.admin_password)
    with api.client as client:
        response = client.post(
            "/api/v1/users",
            headers=cookie_header(admin_login["cookie"]),
            json={"email": email, "password": "correct-horse-00", "role": role},
        )
    assert response.status_code == 201, response.text
    return response.json()


def get_user(api: SimpleNamespace, email: str) -> UserAccount:
    with api.factory() as database:
        return database.scalar(select(UserAccount).where(UserAccount.email == email))


def actions_in_db(api: SimpleNamespace) -> list[str]:
    with api.factory() as database:
        return list(database.scalars(select(AuditAction.action)))


def test_provisioned_viewer_can_login_and_see_me(api: SimpleNamespace) -> None:
    create_user(api, "viewer@example.com", role="viewer")
    result = login(api, "viewer@example.com", "correct-horse-00")
    assert result["change_required"] is False
    with api.client as client:
        me = client.get("/api/v1/auth/me", headers=cookie_header(result["cookie"]))
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "viewer@example.com"
    assert body["role"] == "viewer"
    assert body["is_active"] is True
    assert "password_hash" not in me.text
    assert AuditEvent.USER_LOGIN_SUCCESS in actions_in_db(api)


def test_login_rejects_unknown_and_wrong_passwords(api: SimpleNamespace) -> None:
    create_user(api, "viewer@example.com", role="viewer")
    with api.client as client:
        unknown = client.post("/api/v1/auth/login", json={"email": "ghost@example.com", "password": "whatever-00"})
        wrong = client.post("/api/v1/auth/login", json={"email": "viewer@example.com", "password": "wrong-pass-00"})
    assert unknown.status_code == 401
    assert wrong.status_code == 401
    assert known_login_failure(api, "ghost@example.com") is True
    assert actions_in_db(api).count(AuditEvent.USER_LOGIN_FAILURE) >= 2


def known_login_failure(api: SimpleNamespace, email: str) -> bool:
    with api.factory() as database:
        return database.scalar(
            select(AuditAction).where(
                AuditAction.action == AuditEvent.USER_LOGIN_FAILURE,
                AuditAction.resource_id == email,
                AuditAction.actor_id.is_(None),
            )
        ) is not None


def test_login_rejects_disabled_user(api: SimpleNamespace) -> None:
    viewer = create_user(api, "viewer@example.com", role="viewer")
    admin_login = login(api, api.settings.admin_email, api.settings.admin_password)
    with api.client as client:
        client.patch(
            f"/api/v1/users/{viewer['id']}",
            headers=cookie_header(admin_login["cookie"]),
            json={"is_active": False},
        )
        response = client.post("/api/v1/auth/login", json={"email": "viewer@example.com", "password": "correct-horse-00"})
    assert response.status_code == 401
    with api.client as client:
        me = client.get("/api/v1/auth/me", headers=cookie_header(admin_login["cookie"]))
        assert me.status_code == 200


def test_expired_password_forces_change_then_restores_access(api: SimpleNamespace) -> None:
    class FakeCluster:
        cluster_name = "test-cluster"

        def namespaces(self):
            return [("default", "Active")]

    from app.core.dependencies import get_cluster_client

    api.client.app.dependency_overrides[get_cluster_client] = lambda: FakeCluster()
    create_user(api, "viewer@example.com", role="viewer")
    with api.factory() as database:
        user = database.scalar(select(UserAccount).where(UserAccount.email == "viewer@example.com"))
        user.must_change_password = False
        user.password_expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        database.commit()

    result = login(api, "viewer@example.com", "correct-horse-00")
    assert result["change_required"] is True

    with api.client as client:
        blocked = client.get("/api/v1/cluster/namespaces", headers=cookie_header(result["cookie"]))
        assert blocked.status_code == 403
        assert blocked.json()["code"] == "password_change_required"
        me = client.get("/api/v1/auth/me", headers=cookie_header(result["cookie"]))
        assert me.status_code == 200
        assert me.json()["password_expired"] is True
        changed = client.post(
            "/api/v1/auth/change-password",
            headers=cookie_header(result["cookie"]),
            json={"current_password": "correct-horse-00", "new_password": "fresh-password-00"},
        )
        assert changed.status_code == 200, changed.text
        me_after = client.get("/api/v1/auth/me", headers=cookie_header(result["cookie"]))
        assert me_after.status_code == 200
        assert me_after.json()["must_change_password"] is False
        assert me_after.json()["password_expired"] is False
        assert me_after.json()["password_expires_at"] is not None
        allowed = client.get("/api/v1/cluster/namespaces", headers=cookie_header(result["cookie"]))
        assert allowed.status_code == 200, allowed.text


def test_forced_password_change_login_is_restricted(api: SimpleNamespace) -> None:
    create_user(api, "viewer@example.com", role="viewer")
    with api.factory() as database:
        user = database.scalar(select(UserAccount).where(UserAccount.email == "viewer@example.com"))
        user.must_change_password = True
        database.commit()
    result = login(api, "viewer@example.com", "correct-horse-00")
    assert result["change_required"] is True
    with api.client as client:
        response = client.get("/api/v1/auth/me", headers=cookie_header(result["cookie"]))
    assert response.json()["must_change_password"] is True


def test_change_requires_current_password_and_policy(api: SimpleNamespace) -> None:
    viewer = create_user(api, "viewer@example.com", role="viewer")
    result = login(api, "viewer@example.com", "correct-horse-00")
    with api.client as client:
        headers = cookie_header(result["cookie"])
        wrong = client.post(
            "/api/v1/auth/change-password",
            headers=headers,
            json={"current_password": "nope-nope", "new_password": "fresh-password-00"},
        )
        short = client.post(
            "/api/v1/auth/change-password",
            headers=headers,
            json={"current_password": "correct-horse-00", "new_password": "short"},
        )
        unauthenticated = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "correct-horse-00", "new_password": "fresh-password-00"},
        )
    assert wrong.status_code == 422 and wrong.json()["code"] == "invalid_current_password"
    assert short.status_code == 422 and short.json()["code"] == "invalid_password"
    assert unauthenticated.status_code == 401
    assert viewer["id"]
    assert AuditEvent.USER_PASSWORD_CHANGED not in actions_in_db(api)


def test_change_password_invalidates_other_sessions(api: SimpleNamespace) -> None:
    create_user(api, "viewer@example.com", role="viewer")
    first = login(api, "viewer@example.com", "correct-horse-00")
    second = login(api, "viewer@example.com", "correct-horse-00")
    with api.client as client:
        changed = client.post(
            "/api/v1/auth/change-password",
            headers=cookie_header(first["cookie"]),
            json={"current_password": "correct-horse-00", "new_password": "fresh-password-00"},
        )
        assert changed.status_code == 200
        other_invalid = client.get("/api/v1/auth/me", headers=cookie_header(second["cookie"]))
        self_valid = client.get("/api/v1/auth/me", headers=cookie_header(first["cookie"]))
    assert other_invalid.status_code == 401
    assert self_valid.status_code == 200
    assert AuditEvent.USER_PASSWORD_CHANGED in actions_in_db(api)
    assert AuditEvent.USER_LOGIN_SUCCESS in actions_in_db(api)