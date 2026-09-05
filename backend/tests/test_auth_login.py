from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session as DatabaseSession
from sqlalchemy.pool import StaticPool

from app.core.dependencies import get_database_session
from app.core.passwords import hash_password
from app.models.base import Base
from app.models.entities import Session as StoredSession
from app.models.entities import UserAccount

LOGIN_URL = "/api/v1/auth/login"
COOKIE_NAME = "kubepilot_session"
FORBIDDEN_BODY = {"code": "authentication_required", "message": "Authentication is required"}


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


def add_user(engine: object, email: str, password: str, *, role: str) -> None:
    with DatabaseSession(engine) as database:
        database.add(UserAccount(email=email, password_hash=hash_password(password), role=role))
        database.commit()


def count_sessions(engine: object) -> int:
    with DatabaseSession(engine) as database:
        return len(database.scalars(select(StoredSession)).all())


def test_admin_is_seeded_on_first_login(monkeypatch: pytest.MonkeyPatch) -> None:
    client, engine = build_client(monkeypatch)
    with client:
        response = client.post(LOGIN_URL, json={"email": "OPS@kubepilot.io", "password": "kubepilot"})
    assert response.status_code == 200
    body = response.json()
    assert body["cookie"]
    assert body["expires_at"] > 0
    with DatabaseSession(engine) as database:
        user = database.scalar(select(UserAccount))
        assert user is not None
        assert user.email == "ops@kubepilot.io"
        assert user.role == "admin"
    assert count_sessions(engine) == 1


def test_existing_non_admin_user_can_login(monkeypatch: pytest.MonkeyPatch) -> None:
    client, engine = build_client(monkeypatch)
    add_user(engine, "alice@example.com", "s3cret", role="operator")
    with client:
        response = client.post(LOGIN_URL, json={"email": "alice@example.com", "password": "s3cret"})
    assert response.status_code == 200
    assert response.json()["cookie"]
    assert count_sessions(engine) == 1


def test_login_cookie_authenticates_non_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    client, engine = build_client(monkeypatch)
    add_user(engine, "alice@example.com", "s3cret", role="viewer")
    with client:
        login = client.post(LOGIN_URL, json={"email": "alice@example.com", "password": "s3cret"})
    cookie = login.json()["cookie"]
    with client:
        response = client.get("/api/v1/auth/context", cookies={COOKIE_NAME: cookie})
    assert response.status_code == 200
    assert response.json() == {"identifier": "alice@example.com", "role": "viewer"}


def test_wrong_password_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    client, engine = build_client(monkeypatch)
    add_user(engine, "alice@example.com", "s3cret", role="operator")
    with client:
        response = client.post(LOGIN_URL, json={"email": "alice@example.com", "password": "wrong"})
    assert response.status_code == 401
    assert response.json() == FORBIDDEN_BODY
    assert count_sessions(engine) == 0


def test_unknown_email_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    client, _engine = build_client(monkeypatch)
    with client:
        response = client.post(LOGIN_URL, json={"email": "nobody@example.com", "password": "anything"})
    assert response.status_code == 401
    assert response.json() == FORBIDDEN_BODY


def test_admin_password_hash_is_refreshed_on_env_password_change(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KUBEPILOT_ADMIN_PASSWORD", "new-admin-password")
    client, engine = build_client(monkeypatch)
    add_user(engine, "ops@kubepilot.io", "old-password", role="admin")
    with client:
        response = client.post(LOGIN_URL, json={"email": "ops@kubepilot.io", "password": "new-admin-password"})
    assert response.status_code == 200
    with DatabaseSession(engine) as database:
        stored = database.scalar(select(UserAccount)).password_hash
    assert stored == hash_password("new-admin-password")