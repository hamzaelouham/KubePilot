import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session as DatabaseSession

from app.core.config import Settings
from app.db.session import create_session_factory
from app.models.base import Base
from app.models.entities import UserAccount




os.environ.setdefault("KUBEPILOT_WORKER_ENABLED", "false")
@pytest.fixture()
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    database_url = f"sqlite:///{tmp_path / 'kubepilot-e2e.db'}"
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


def admin_login(api: SimpleNamespace) -> dict:
    return login(api, api.settings.admin_email, api.settings.admin_password)


def create_user(api: SimpleNamespace, email: str, role: str) -> dict:
    admin = admin_login(api)
    with api.client as client:
        response = client.post(
            "/api/v1/users",
            headers=cookie_header(admin["cookie"]),
            json={"email": email, "password": "correct-horse-00", "role": role},
        )
    assert response.status_code == 201, response.text
    return response.json()


def set_cluster_override(api: SimpleNamespace) -> None:
    class FakeCluster:
        cluster_name = "test-cluster"

        def namespaces(self):
            return [("default", "Active")]

    from app.core.dependencies import get_cluster_client

    api.client.app.dependency_overrides[get_cluster_client] = lambda: FakeCluster()


def test_admin_full_privileges(api: SimpleNamespace) -> None:
    admin = admin_login(api)
    with api.client as client:
        headers = cookie_header(admin["cookie"])
        me = client.get("/api/v1/auth/me", headers=headers)
        assert me.status_code == 200
        assert me.json()["role"] == "admin"
        users = client.get("/api/v1/users", headers=headers)
        assert users.status_code == 200
        assert len(users.json()["items"]) >= 1


def test_operator_reads_but_no_user_mutations(api: SimpleNamespace) -> None:
    set_cluster_override(api)
    create_user(api, "operator@example.com", "operator")
    op = login(api, "operator@example.com", "correct-horse-00")
    with api.client as client:
        headers = cookie_header(op["cookie"])
        assert client.get("/api/v1/cluster/namespaces", headers=headers).status_code == 200
        assert client.get("/api/v1/auth/me", headers=headers).json()["role"] == "operator"
        assert client.get("/api/v1/users", headers=headers).status_code == 403
        assert client.post(
            "/api/v1/users",
            headers=headers,
            json={"email": "x@example.com", "password": "correct-horse-00", "role": "viewer"},
        ).status_code == 403


def test_viewer_read_only(api: SimpleNamespace) -> None:
    set_cluster_override(api)
    create_user(api, "viewer@example.com", "viewer")
    viewer = login(api, "viewer@example.com", "correct-horse-00")
    with api.client as client:
        headers = cookie_header(viewer["cookie"])
        assert client.get("/api/v1/cluster/namespaces", headers=headers).status_code == 200
        assert client.get("/api/v1/users", headers=headers).status_code == 403
        assert client.delete("/api/v1/users/00000000-0000-0000-0000-000000000000", headers=headers).status_code == 403


def test_unauthenticated_requests_are_generic_401(api: SimpleNamespace) -> None:
    with api.client as client:
        users = client.get("/api/v1/users")
        namespaces = client.get("/api/v1/cluster/namespaces")
    assert users.status_code == 401 and users.json()["code"] == "authentication_required"
    assert namespaces.status_code == 401 and namespaces.json()["code"] == "authentication_required"


def test_deactivation_invalidates_sessions(api: SimpleNamespace) -> None:
    create_user(api, "operator@example.com", "operator")
    op = login(api, "operator@example.com", "correct-horse-00")
    admin = admin_login(api)
    user = get_user_by_email(api, "operator@example.com")
    with api.client as client:
        headers = cookie_header(admin["cookie"])
        assert client.patch(f"/api/v1/users/{user.id}", headers=headers, json={"is_active": False}).status_code == 200
        invalidated = client.get("/api/v1/auth/me", headers=cookie_header(op["cookie"]))
    assert invalidated.status_code == 401


def test_reset_ends_sessions_and_forces_change(api: SimpleNamespace) -> None:
    set_cluster_override(api)
    create_user(api, "operator@example.com", "operator")
    op = login(api, "operator@example.com", "correct-horse-00")
    admin = admin_login(api)
    user = get_user_by_email(api, "operator@example.com")
    with api.client as client:
        reset = client.post(
            f"/api/v1/users/{user.id}/reset-password",
            headers=cookie_header(admin["cookie"]),
            json={"new_password": "temporary-pass-00"},
        )
        assert reset.status_code == 200
        old_session = client.get("/api/v1/auth/me", headers=cookie_header(op["cookie"]))
        assert old_session.status_code == 401

        fresh = login(api, "operator@example.com", "temporary-pass-00")
        assert fresh["change_required"] is True
        blocked = client.get("/api/v1/cluster/namespaces", headers=cookie_header(fresh["cookie"]))
        assert blocked.status_code == 403
        assert blocked.json()["code"] == "password_change_required"
        changed = client.post(
            "/api/v1/auth/change-password",
            headers=cookie_header(fresh["cookie"]),
            json={"current_password": "temporary-pass-00", "new_password": "correct-horse-11"},
        )
        assert changed.status_code == 200
        allowed = client.get("/api/v1/cluster/namespaces", headers=cookie_header(fresh["cookie"]))
        assert allowed.status_code == 200


def test_expired_password_lockout_until_change(api: SimpleNamespace) -> None:
    set_cluster_override(api)
    create_user(api, "viewer@example.com", "viewer")
    with api.factory() as database:
        user = database.scalar(select(UserAccount).where(UserAccount.email == "viewer@example.com"))
        user.password_expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        database.commit()
    result = login(api, "viewer@example.com", "correct-horse-00")
    assert result["change_required"] is True
    with api.client as client:
        headers = cookie_header(result["cookie"])
        assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
        blocked = client.get("/api/v1/cluster/namespaces", headers=headers)
        assert blocked.status_code == 403 and blocked.json()["code"] == "password_change_required"


def get_user_by_email(api: SimpleNamespace, email: str) -> UserAccount:
    with api.factory() as database:
        return database.scalar(select(UserAccount).where(UserAccount.email == email))
