from collections.abc import Iterator
from types import SimpleNamespace

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as DatabaseSession
from sqlalchemy.pool import StaticPool
import pytest

from app.core.dependencies import AuthenticatedActor, get_database_session
from app.core.passwords import hash_password
from app.core.roles import require_minimum_role
from app.kubernetes.client import ClusterClient
from app.main import create_app
from app.models.base import Base
from app.models.entities import UserAccount
from app.api.v1.routes import get_cluster_client

LOGIN_URL = "/api/v1/auth/login"
COOKIE_NAME = "kubepilot_session"
CLUSTER_URL = "/api/v1/cluster/namespaces"
CONTEXT_URL = "/api/v1/auth/context"
UNAUTH_401 = {"code": "authentication_required", "message": "Authentication is required"}
FORBIDDEN_403 = {
    "code": "insufficient_permissions",
    "message": "Insufficient permissions for the required role",
}
ROLES = ("viewer", "operator", "admin")


def fake_cluster_client() -> ClusterClient:
    namespace = SimpleNamespace(
        metadata=SimpleNamespace(name="default"),
        status=SimpleNamespace(phase="Active"),
    )
    core = SimpleNamespace(list_namespace=lambda: SimpleNamespace(items=[namespace]))
    return ClusterClient("test", core, object())


def build_client(monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, object]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    monkeypatch.setenv("KUBEPILOT_AUTH_SECRET", "x" * 32)
    monkeypatch.setenv("KUBEPILOT_DATABASE_URL", "sqlite://")

    app = create_app()

    def override_database_session() -> Iterator[DatabaseSession]:
        session = DatabaseSession(engine)
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_database_session] = override_database_session
    app.dependency_overrides[get_cluster_client] = fake_cluster_client
    return TestClient(app), engine


def add_user(engine: object, email: str, password: str, *, role: str) -> None:
    with DatabaseSession(engine) as database:
        database.add(
            UserAccount(email=email, password_hash=hash_password(password), role=role, is_active=True)
        )
        database.commit()


def login(client: TestClient, email: str, password: str) -> str:
    with client:
        response = client.post(LOGIN_URL, json={"email": email, "password": password})
    assert response.status_code == 200
    assert response.json()["cookie"]
    return response.json()["cookie"]


@pytest.mark.parametrize("role", ROLES)
def test_cluster_read_allowed_for_each_role(monkeypatch: pytest.MonkeyPatch, role: str) -> None:
    client, engine = build_client(monkeypatch)
    add_user(engine, f"{role}@example.com", "password", role=role)
    cookie = login(client, f"{role}@example.com", "password")
    with client:
        response = client.get(CLUSTER_URL, cookies={COOKIE_NAME: cookie})
    assert response.status_code == 200
    assert "items" in response.json()


def test_context_reports_role(monkeypatch: pytest.MonkeyPatch) -> None:
    client, engine = build_client(monkeypatch)
    add_user(engine, "viewer@example.com", "password", role="viewer")
    cookie = login(client, "viewer@example.com", "password")
    with client:
        response = client.get(CONTEXT_URL, cookies={COOKIE_NAME: cookie})
    assert response.status_code == 200
    assert response.json()["role"] == "viewer"


def test_unauthenticated_cluster_read_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    client, _engine = build_client(monkeypatch)
    with client:
        response = client.get(CLUSTER_URL)
    assert response.status_code == 401
    assert response.json() == UNAUTH_401


def test_unknown_role_is_denied_on_cluster_read(monkeypatch: pytest.MonkeyPatch) -> None:
    client, engine = build_client(monkeypatch)
    add_user(engine, "root@example.com", "password", role="root")
    cookie = login(client, "root@example.com", "password")
    with client:
        response = client.get(CLUSTER_URL, cookies={COOKIE_NAME: cookie})
    assert response.status_code == 403
    assert response.json() == FORBIDDEN_403


def test_operator_minimum_denies_viewer() -> None:
    dependency = require_minimum_role("operator")
    with pytest.raises(HTTPException) as exc_info:
        dependency(AuthenticatedActor(identifier="viewer@example.com", role="viewer"))
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == FORBIDDEN_403


def test_operator_minimum_allows_operator_and_admin() -> None:
    dependency = require_minimum_role("operator")
    assert dependency(AuthenticatedActor(identifier="operator@example.com", role="operator")).role == "operator"
    assert dependency(AuthenticatedActor(identifier="admin@example.com", role="admin")).role == "admin"


def test_unknown_minimum_role_is_rejected() -> None:
    with pytest.raises(ValueError):
        require_minimum_role("superuser")