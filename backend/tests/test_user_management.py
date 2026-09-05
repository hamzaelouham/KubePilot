from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session as DatabaseSession
from sqlalchemy.pool import StaticPool

from app.api.v1.auth_schemas import LoginRequest  # noqa: F401  (contract reference)
from app.core.dependencies import get_database_session
from app.core.passwords import hash_password
from app.models.base import Base
from app.models.entities import UserAccount

LOGIN_URL = "/api/v1/auth/login"
USERS_URL = "/api/v1/users"
COOKIE_NAME = "kubepilot_session"
FORBIDDEN_BODY = {"code": "authentication_required", "message": "Authentication is required"}
FORBIDDEN_403 = {"code": "insufficient_permissions", "message": "Admin access is required"}
ROLES = {"admin", "operator", "viewer"}


def build_client(monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, object]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    monkeypatch.setenv("KUBEPILOT_AUTH_SECRET", "x" * 32)
    monkeypatch.setenv("KUBEPILOT_DATABASE_URL", "sqlite://")

    from app.main import create_app

    app = create_app()

    def override_database_session() -> Iterator[DatabaseSession]:
        session = DatabaseSession(engine)
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_database_session] = override_database_session
    return TestClient(app), engine


def add_user(engine: object, email: str, password: str, *, role: str, is_active: bool = True) -> None:
    with DatabaseSession(engine) as database:
        database.add(
            UserAccount(email=email, password_hash=hash_password(password), role=role, is_active=is_active)
        )
        database.commit()


def find_user(engine: object, email: str) -> UserAccount:
    with DatabaseSession(engine) as database:
        return database.scalar(select(UserAccount).where(UserAccount.email == email))


def login(client: TestClient, email: str, password: str) -> str:
    with client:
        response = client.post(LOGIN_URL, json={"email": email, "password": password})
    assert response.status_code == 200
    assert response.json()["cookie"]
    return response.json()["cookie"]


def login_as_admin(monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, object, str]:
    monkeypatch.setenv("KUBEPILOT_ADMIN_PASSWORD", "kubepilot")
    client, engine = build_client(monkeypatch)
    cookie = login(client, "ops@kubepilot.io", "kubepilot")
    return client, engine, cookie


# --- Step 1: inactive users are blocked at the auth boundary ---


def test_inactive_user_login_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    client, engine = build_client(monkeypatch)
    add_user(engine, "alice@example.com", "s3cret", role="operator", is_active=False)
    add_user(engine, "bob@example.com", "s3cret", role="operator", is_active=True)
    with client:
        response = client.post(LOGIN_URL, json={"email": "alice@example.com", "password": "s3cret"})
    assert response.status_code == 401
    assert response.json() == FORBIDDEN_BODY
    with client:
        response = client.post(LOGIN_URL, json={"email": "bob@example.com", "password": "s3cret"})
    assert response.status_code == 200


def test_inactive_user_existing_cookie_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    client, engine = build_client(monkeypatch)
    add_user(engine, "alice@example.com", "s3cret", role="viewer", is_active=True)
    cookie = login(client, "alice@example.com", "s3cret")
    with DatabaseSession(engine) as database:
        user = database.scalar(select(UserAccount))
        assert user is not None
        user.is_active = False
        database.commit()
    with client:
        response = client.get("/api/v1/auth/context", cookies={COOKIE_NAME: cookie})
    assert response.status_code == 401
    assert response.json() == FORBIDDEN_BODY


def test_inactive_password_match_does_not_identify_account(monkeypatch: pytest.MonkeyPatch) -> None:
    client, engine = build_client(monkeypatch)
    add_user(engine, "alice@example.com", "s3cret", role="operator", is_active=False)
    add_user(engine, "bob@example.com", "other-pass", role="operator", is_active=True)
    with client:
        response = client.post(LOGIN_URL, json={"email": "alice@example.com", "password": "s3cret"})
    assert response.status_code == 401
    assert response.json() == FORBIDDEN_BODY


# --- Step 2: admin-only user management API ---


def test_users_list_requires_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    client, engine = build_client(monkeypatch)
    add_user(engine, "alice@example.com", "s3cret", role="operator")
    cookie = login(client, "alice@example.com", "s3cret")
    with client:
        response = client.get(USERS_URL, cookies={COOKIE_NAME: cookie})
    assert response.status_code == 403
    assert response.json() == FORBIDDEN_403
    with client:
        response = client.get(USERS_URL)
    assert response.status_code == 401
    assert response.json() == FORBIDDEN_BODY


def test_users_list_returns_items_without_password_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    client, engine, cookie = login_as_admin(monkeypatch)
    add_user(engine, "alice@example.com", "s3cret", role="operator")
    with client:
        response = client.get(USERS_URL, cookies={COOKIE_NAME: cookie})
    assert response.status_code == 200
    body = response.json()
    emails = {item["email"] for item in body["items"]}
    assert "ops@kubepilot.io" in emails
    assert "alice@example.com" in emails
    assert all("password_hash" not in item for item in body["items"])
    assert all(item["role"] in ROLES for item in body["items"])
    assert all(isinstance(item["isActive"], bool) for item in body["items"])


def test_create_user_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    client, engine, cookie = login_as_admin(monkeypatch)
    with client:
        response = client.post(
            USERS_URL,
            json={"email": "  ALICE@Example.COM ", "password": "s3cret", "role": "viewer"},
            cookies={COOKIE_NAME: cookie},
        )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert body["role"] == "viewer"
    assert body["isActive"] is True
    assert "password_hash" not in body
    stored = find_user(engine, "alice@example.com")
    assert stored is not None
    assert stored.role == "viewer"
    assert stored.is_active is True


def test_create_user_duplicate_email_conflicts(monkeypatch: pytest.MonkeyPatch) -> None:
    client, engine, cookie = login_as_admin(monkeypatch)
    add_user(engine, "alice@example.com", "s3cret", role="operator")
    with client:
        response = client.post(
            USERS_URL,
            json={"email": "alice@example.com", "password": "other", "role": "viewer"},
            cookies={COOKIE_NAME: cookie},
        )
    assert response.status_code == 409
    assert response.json()["code"] == "email_in_use"


def test_create_user_rejects_invalid_role_and_empty_password(monkeypatch: pytest.MonkeyPatch) -> None:
    client, engine, cookie = login_as_admin(monkeypatch)
    with client:
        response = client.post(
            USERS_URL,
            json={"email": "alice@example.com", "password": "s3cret", "role": "superuser"},
            cookies={COOKIE_NAME: cookie},
        )
    assert response.status_code == 422
    with client:
        response = client.post(
            USERS_URL,
            json={"email": "bob@example.com", "password": "", "role": "viewer"},
            cookies={COOKIE_NAME: cookie},
        )
    assert response.status_code == 422


def test_create_user_requires_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    client, engine = build_client(monkeypatch)
    add_user(engine, "alice@example.com", "s3cret", role="operator")
    cookie = login(client, "alice@example.com", "s3cret")
    with client:
        response = client.post(
            USERS_URL,
            json={"email": "bob@example.com", "password": "s3cret", "role": "viewer"},
            cookies={COOKIE_NAME: cookie},
        )
    assert response.status_code == 403
    with client:
        response = client.post(
            USERS_URL,
            json={"email": "bob@example.com", "password": "s3cret", "role": "viewer"},
        )
    assert response.status_code == 401


def test_role_change_updates_user(monkeypatch: pytest.MonkeyPatch) -> None:
    client, engine, cookie = login_as_admin(monkeypatch)
    add_user(engine, "alice@example.com", "s3cret", role="operator")
    user_id = str(find_user(engine, "alice@example.com").id)
    with client:
        response = client.patch(
            f"{USERS_URL}/{user_id}/role",
            json={"role": "admin"},
            cookies={COOKIE_NAME: cookie},
        )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"
    assert find_user(engine, "alice@example.com").role == "admin"


def test_env_admin_role_cannot_be_changed(monkeypatch: pytest.MonkeyPatch) -> None:
    client, engine, cookie = login_as_admin(monkeypatch)
    admin_id = str(find_user(engine, "ops@kubepilot.io").id)
    with client:
        response = client.patch(
            f"{USERS_URL}/{admin_id}/role",
            json={"role": "viewer"},
            cookies={COOKIE_NAME: cookie},
        )
    assert response.status_code == 422
    assert response.json()["code"] == "protected_admin_account"
    assert find_user(engine, "ops@kubepilot.io").role == "admin"


def test_role_change_unknown_user_404(monkeypatch: pytest.MonkeyPatch) -> None:
    client, engine, cookie = login_as_admin(monkeypatch)
    with client:
        response = client.patch(
            f"{USERS_URL}/00000000-0000-0000-0000-000000000000/role",
            json={"role": "viewer"},
            cookies={COOKIE_NAME: cookie},
        )
    assert response.status_code == 404


def test_deactivate_user(monkeypatch: pytest.MonkeyPatch) -> None:
    client, engine, cookie = login_as_admin(monkeypatch)
    add_user(engine, "alice@example.com", "s3cret", role="operator")
    user_id = str(find_user(engine, "alice@example.com").id)
    with client:
        response = client.post(f"{USERS_URL}/{user_id}/deactivate", cookies={COOKIE_NAME: cookie})
    assert response.status_code == 200
    assert response.json() == {"id": user_id, "isActive": False}
    assert find_user(engine, "alice@example.com").is_active is False
    with client:
        response = client.post(f"{USERS_URL}/{user_id}/deactivate", cookies={COOKIE_NAME: cookie})
    assert response.status_code == 200
    assert response.json()["isActive"] is False


def test_deactivate_and_reactive_login_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    client, engine, cookie = login_as_admin(monkeypatch)
    add_user(engine, "alice@example.com", "s3cret", role="operator")
    user_id = str(find_user(engine, "alice@example.com").id)
    with client:
        client.post(f"{USERS_URL}/{user_id}/deactivate", cookies={COOKIE_NAME: cookie})
    with client:
        response = client.post(LOGIN_URL, json={"email": "alice@example.com", "password": "s3cret"})
    assert response.status_code == 401
    with DatabaseSession(engine) as database:
        user = database.scalar(select(UserAccount).where(UserAccount.email == "alice@example.com"))
        assert user is not None
        user.is_active = True
        database.commit()
    with client:
        response = client.post(LOGIN_URL, json={"email": "alice@example.com", "password": "s3cret"})
    assert response.status_code == 200


def test_deactivate_env_admin_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    client, engine, cookie = login_as_admin(monkeypatch)
    admin_id = str(find_user(engine, "ops@kubepilot.io").id)
    with client:
        response = client.post(f"{USERS_URL}/{admin_id}/deactivate", cookies={COOKIE_NAME: cookie})
    assert response.status_code == 422
    assert response.json()["code"] == "protected_admin_account"
    assert find_user(engine, "ops@kubepilot.io").is_active is True