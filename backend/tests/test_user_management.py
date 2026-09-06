import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session as DatabaseSession

from app.api.v1.routes import _signed_cookie
from app.core.audit import AuditEvent
from app.core.config import Settings
from app.db.session import create_session_factory
from app.models.base import Base
from app.models.entities import AuditAction, Session, UserAccount


@pytest.fixture()
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    database_url = f"sqlite:///{tmp_path / 'kubepilot-test.db'}"
    monkeypatch.setenv("KUBEPILOT_AUTH_SECRET", "x" * 32)
    monkeypatch.setenv("KUBEPILOT_DATABASE_URL", database_url)
    monkeypatch.setenv("KUBEPILOT_ADMIN_EMAIL", "ops@kubepilot.io")
    monkeypatch.setenv("KUBEPILOT_ADMIN_PASSWORD", "kubepilot")
    os.environ["KUBEPILOT_PASSWORD_TTL_DAYS"] = "15"

    from app.main import create_app

    settings = Settings.from_env()
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(settings)
    app = create_app()
    return SimpleNamespace(settings=settings, factory=factory, client=TestClient(app))


@pytest.fixture()
def admin(api: SimpleNamespace) -> dict[str, str]:
    with api.client as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "ops@kubepilot.io", "password": "kubepilot"},
        )
        assert response.status_code == 200
        return response.json()


def cookie_header(cookie: str) -> dict[str, str]:
    return {"cookie": f"kubepilot_session={cookie}"}


def session_cookie_for(
    api: SimpleNamespace,
    user: UserAccount,
) -> str:
    expires_ms = int((time.time() + 3600) * 1000)
    cookie, _ = _signed_cookie(user.email, expires_ms, api.settings.auth_secret)
    payload = cookie.split(".")[0]
    import hashlib

    with api.factory() as database:
        database.add(
            Session(
                user_id=user.id,
                token_hash=hashlib.sha256(payload.encode()).hexdigest(),
                expires_at=datetime.fromtimestamp(expires_ms / 1000, tz=timezone.utc),
                restricted=False,
            )
        )
        database.commit()
    return cookie


def get_user_by_email(api: SimpleNamespace, email: str) -> UserAccount:
    with api.factory() as database:
        return database.scalar(select(UserAccount).where(UserAccount.email == email))


def actions_in_db(api: SimpleNamespace) -> list[str]:
    with api.factory() as database:
        return list(database.scalars(select(AuditAction.action)))


@pytest.fixture()
def operator(api: SimpleNamespace, admin: dict[str, str]) -> dict:
    with api.client as client:
        response = client.post(
            "/api/v1/users",
            headers=cookie_header(admin["cookie"]),
            json={"email": "worker@example.com", "password": "correct-horse-00", "role": "operator"},
        )
        assert response.status_code == 201
        return response.json()


def test_admin_login_seeds_admin_and_can_list_users(api: SimpleNamespace, admin: dict[str, str]) -> None:
    with api.client as client:
        response = client.get("/api/v1/users", headers=cookie_header(admin["cookie"]))
    assert response.status_code == 200, response.text
    emails = [item["email"] for item in response.json()["items"]]
    assert "ops@kubepilot.io" in emails
    seeded = next(item for item in response.json()["items"] if item["email"] == "ops@kubepilot.io")
    assert seeded["role"] == "admin"
    assert seeded["is_active"] is True
    assert "password_hash" not in response.text


def test_admin_creates_user_with_role_and_expiry(api: SimpleNamespace, admin: dict[str, str]) -> None:
    with api.client as client:
        response = client.post(
            "/api/v1/users",
            headers=cookie_header(admin["cookie"]),
            json={"email": "viewer@example.com", "password": "correct-horse-00", "role": "viewer"},
        )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["email"] == "viewer@example.com"
    assert body["role"] == "viewer"
    assert body["is_active"] is True
    assert body["must_change_password"] is False
    assert body["password_expires_at"] is not None
    assert "password_hash" not in response.text
    stored = get_user_by_email(api, "viewer@example.com")
    assert stored is not None
    assert stored.password_hash != "correct-horse-00"
    assert stored.password_hash.startswith("pbkdf2_sha256$120000$")
    assert AuditEvent.USER_CREATED in actions_in_db(api)


def test_create_user_rejects_duplicate_invalid_and_short_password(
    api: SimpleNamespace, admin: dict[str, str]
) -> None:
    with api.client as client:
        headers = cookie_header(admin["cookie"])
        duplicate = client.post(
            "/api/v1/users",
            headers=headers,
            json={"email": "ops@kubepilot.io", "password": "correct-horse-00", "role": "viewer"},
        )
        bad_email = client.post(
            "/api/v1/users", headers=headers, json={"email": "not-an-email", "password": "correct-horse-00", "role": "viewer"}
        )
        bad_role = client.post(
            "/api/v1/users", headers=headers, json={"email": "x@example.com", "password": "correct-horse-00", "role": "root"}
        )
        short_password = client.post(
            "/api/v1/users", headers=headers, json={"email": "y@example.com", "password": "short", "role": "viewer"}
        )
    assert duplicate.status_code == 409
    assert bad_email.status_code == 422
    assert bad_role.status_code == 422
    assert short_password.status_code == 422


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/users"),
        ("post", "/api/v1/users"),
        ("get", "/api/v1/users/{user_id}"),
        ("patch", "/api/v1/users/{user_id}"),
        ("post", "/api/v1/users/{user_id}/reset-password"),
        ("post", "/api/v1/users/{user_id}/force-password-change"),
        ("delete", "/api/v1/users/{user_id}"),
    ],
)
def test_non_admin_users_get_forbidden_on_user_apis(
    api: SimpleNamespace, admin: dict[str, str], operator: dict[str, str], method: str, path: str
) -> None:
    with api.client as client:
        headers = cookie_header(admin["cookie"])
        viewer = client.post(
            "/api/v1/users",
            headers=headers,
            json={"email": "viewer@example.com", "password": "correct-horse-00", "role": "viewer"},
        ).json()
        for role, actor in (("operator", operator), ("viewer", viewer)):
            url = path.format(user_id=actor["id"])
            kwargs = {"headers": cookie_header(session_cookie_for(api, get_user_by_email(api, actor["email"])))}
            if method == "post":
                kwargs["json"] = {"email": "a@example.com", "password": "correct-horse-00", "role": "viewer"}
            response = getattr(client, method)(url, **kwargs)
            assert response.status_code == 403, (role, method, path, response.text)
            assert response.json()["code"] == "insufficient_permissions"


def test_users_api_requires_authentication(api: SimpleNamespace) -> None:
    with api.client as client:
        response = client.get("/api/v1/users")
    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


def test_admin_updates_role_and_deactivates(api: SimpleNamespace, admin: dict[str, str], operator: dict[str, str]) -> None:
    with api.client as client:
        headers = cookie_header(admin["cookie"])
        role_update = client.patch(
            f"/api/v1/users/{operator['id']}", headers=headers, json={"role": "viewer"}
        )
        assert role_update.status_code == 200
        assert role_update.json()["role"] == "viewer"
        deactivate = client.patch(
            f"/api/v1/users/{operator['id']}", headers=headers, json={"is_active": False}
        )
        assert deactivate.status_code == 200
        assert deactivate.json()["is_active"] is False
    actions = actions_in_db(api)
    assert AuditEvent.USER_ROLE_CHANGED in actions
    assert AuditEvent.USER_DEACTIVATED in actions


def _deactivation_setup(api: SimpleNamespace) -> UserAccount:
    operator = get_user_by_email(api, "worker@example.com")
    assert operator is not None
    return operator


def test_deactivation_invalidates_sessions(api: SimpleNamespace, admin: dict[str, str], operator: dict[str, str]) -> None:
    class FakeCluster:
        cluster_name = "test-cluster"

        def namespaces(self):
            return [("default", "Active")]

    from app.core.dependencies import get_cluster_client

    api.client.app.dependency_overrides[get_cluster_client] = lambda: FakeCluster()
    operator_row = _deactivation_setup(api)
    cookie = session_cookie_for(api, operator_row)
    with api.client as client:
        allowed = client.get("/api/v1/cluster/namespaces", headers=cookie_header(cookie))
        assert allowed.status_code == 200, allowed.text
    with api.client as client:
        client.patch(f"/api/v1/users/{operator['id']}", headers=cookie_header(admin["cookie"]), json={"is_active": False})
        denied = client.get("/api/v1/cluster/namespaces", headers=cookie_header(cookie))
    assert denied.status_code == 401
    with api.factory() as database:
        assert database.scalar(select(Session).where(Session.user_id == UUID(operator["id"]))) is None


def test_reactivation_restores_access(api: SimpleNamespace, admin: dict[str, str], operator: dict[str, str]) -> None:
    with api.client as client:
        headers = cookie_header(admin["cookie"])
        client.patch(f"/api/v1/users/{operator['id']}", headers=headers, json={"is_active": False})
        reactivate = client.patch(f"/api/v1/users/{operator['id']}", headers=headers, json={"is_active": True})
    assert reactivate.status_code == 200
    assert reactivate.json()["is_active"] is True
    assert AuditEvent.USER_REACTIVATED in actions_in_db(api)


def test_reset_password_requires_change_and_invalidates_sessions(
    api: SimpleNamespace, admin: dict[str, str], operator: dict[str, str]
) -> None:
    with api.client as client:
        headers = cookie_header(admin["cookie"])
        response = client.post(
            f"/api/v1/users/{operator['id']}/reset-password",
            headers=headers,
            json={"new_password": "temporary-pass-00"},
        )
    assert response.status_code == 200
    assert response.json()["must_change_password"] is True
    stored = get_user_by_email(api, operator["email"])
    assert stored.must_change_password is True
    assert AuditEvent.USER_PASSWORD_RESET in actions_in_db(api)


def test_force_password_change_marks_account(api: SimpleNamespace, admin: dict[str, str], operator: dict[str, str]) -> None:
    with api.client as client:
        headers = cookie_header(admin["cookie"])
        response = client.post(
            f"/api/v1/users/{operator['id']}/force-password-change", headers=headers
        )
    assert response.status_code == 200
    assert response.json()["must_change_password"] is True
    assert AuditEvent.USER_FORCED_PASSWORD_CHANGE in actions_in_db(api)


def test_last_admin_is_protected(api: SimpleNamespace, admin: dict[str, str]) -> None:
    with api.factory() as database:
        target = database.scalar(select(UserAccount).where(UserAccount.email == "ops@kubepilot.io"))
    assert target is not None
    with api.client as client:
        headers = cookie_header(admin["cookie"])
        demote = client.patch(f"/api/v1/users/{target.id}", headers=headers, json={"role": "viewer"})
        deactivate = client.patch(f"/api/v1/users/{target.id}", headers=headers, json={"is_active": False})
        delete = client.delete(f"/api/v1/users/{target.id}", headers=headers)
        reset = client.post(
            f"/api/v1/users/{target.id}/reset-password", headers=headers, json={"new_password": "another-pass-00"}
        )
        force = client.post(f"/api/v1/users/{target.id}/force-password-change", headers=headers)
    assert demote.status_code == 422 and demote.json()["code"] == "cannot_change_own_role"
    assert deactivate.status_code == 422 and deactivate.json()["code"] == "cannot_deactivate_self"
    assert delete.status_code == 422 and delete.json()["code"] == "cannot_delete_self"
    assert reset.status_code == 422 and reset.json()["code"] == "cannot_reset_own_password"
    assert force.status_code == 422 and force.json()["code"] == "cannot_force_own_password_change"


def test_last_active_admin_guards_fire_for_external_actor(
    api: SimpleNamespace, admin: dict[str, str]
) -> None:
    from uuid import uuid4

    from app.core.dependencies import AuthenticatedActor, get_current_actor

    with api.factory() as database:
        target = database.scalar(select(UserAccount).where(UserAccount.email == "ops@kubepilot.io"))
    assert target is not None
    phantom = AuthenticatedActor("phantom-admin@example.com", "admin", user_id=uuid4(), session_id=uuid4())
    api.client.app.dependency_overrides[get_current_actor] = lambda: phantom
    with api.client as client:
        headers = cookie_header("unused-cookie-value")
        demote = client.patch(f"/api/v1/users/{target.id}", headers=headers, json={"role": "viewer"})
        deactivate = client.patch(f"/api/v1/users/{target.id}", headers=headers, json={"is_active": False})
        delete = client.delete(f"/api/v1/users/{target.id}", headers=headers)
    assert demote.status_code == 422 and demote.json()["code"] == "cannot_demote_last_admin"
    assert deactivate.status_code == 422 and deactivate.json()["code"] == "cannot_deactivate_last_admin"
    assert delete.status_code == 422 and delete.json()["code"] == "cannot_delete_last_admin"


def test_delete_user_without_history_succeeds(api: SimpleNamespace, admin: dict[str, str]) -> None:
    from app.core.passwords import hash_password

    with api.factory() as database:
        direct = UserAccount(
            email="temp@example.com",
            password_hash=hash_password("correct-horse-00"),
            role="viewer",
        )
        database.add(direct)
        database.commit()
        direct_id = direct.id
    with api.client as client:
        response = client.delete(f"/api/v1/users/{direct_id}", headers=cookie_header(admin["cookie"]))
    assert response.status_code == 204
    assert get_user_by_email(api, "temp@example.com") is None
    assert AuditEvent.USER_DELETED in actions_in_db(api)


def test_delete_user_with_history_conflicts(api: SimpleNamespace, admin: dict[str, str], operator: dict[str, str]) -> None:
    with api.client as client:
        admin_headers = cookie_header(admin["cookie"])
        client.post(f"/api/v1/users/{operator['id']}/reset-password", headers=admin_headers, json={"new_password": "temp-pass-00"})
        response = client.delete(f"/api/v1/users/{operator['id']}", headers=admin_headers)
    assert response.status_code == 409
    assert response.json()["code"] == "user_has_history"
    assert get_user_by_email(api, operator["email"]) is not None