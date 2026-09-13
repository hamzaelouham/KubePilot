import os
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select

from app.api.v1.routes import _signed_cookie
from app.core.config import Settings
from app.db.session import create_session_factory
from app.models.base import Base
from app.models.entities import AuditAction, Session, UserAccount


os.environ.setdefault("KUBEPILOT_WORKER_ENABLED", "false")


@pytest.fixture()
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    database_url = f"sqlite:///{tmp_path / 'helm-repositories.db'}"
    monkeypatch.setenv("KUBEPILOT_AUTH_SECRET", "x" * 32)
    monkeypatch.setenv("KUBEPILOT_DATABASE_URL", database_url)
    monkeypatch.setenv("KUBEPILOT_ADMIN_EMAIL", "ops@kubepilot.io")
    monkeypatch.setenv("KUBEPILOT_ADMIN_PASSWORD", "kubepilot")
    settings = Settings.from_env()
    Base.metadata.create_all(create_engine(settings.database_url))
    factory = create_session_factory(settings)
    from app.main import create_app

    with TestClient(create_app()) as client:
        yield SimpleNamespace(settings=settings, factory=factory, client=client)


def cookie_header(cookie: str) -> dict[str, str]:
    return {"cookie": f"kubepilot_session={cookie}"}


def login(api: SimpleNamespace, email: str, password: str) -> dict:
    response = api.client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def create_user(api: SimpleNamespace, admin: dict, email: str, role: str) -> dict:
    response = api.client.post(
        "/api/v1/users",
        headers=cookie_header(admin["cookie"]),
        json={"email": email, "password": "correct-horse-00", "role": role},
    )
    assert response.status_code == 201, response.text
    return response.json()


def session_cookie(api: SimpleNamespace, email: str) -> str:
    with api.factory() as database:
        user = database.scalar(select(UserAccount).where(UserAccount.email == email))
        assert user is not None
        expires_ms = int((time.time() + 3600) * 1000)
        cookie, _ = _signed_cookie(user.email, expires_ms, api.settings.auth_secret)
        payload = cookie.split(".")[0]
        import hashlib

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


@pytest.fixture()
def admin(api: SimpleNamespace) -> dict:
    return login(api, "ops@kubepilot.io", "kubepilot")


def test_repository_crud_is_global_and_audited(api: SimpleNamespace, admin: dict) -> None:
    headers = cookie_header(admin["cookie"])
    created = api.client.post(
        "/api/v1/helm/repositories",
        headers=headers,
        json={"name": "Bitnami", "url": "https://charts.bitnami.com/bitnami/"},
    )
    assert created.status_code == 201, created.text
    repository = created.json()
    assert repository["name"] == "bitnami"
    assert repository["url"] == "https://charts.bitnami.com/bitnami"
    assert repository["created_by_id"] is not None

    listed = api.client.get("/api/v1/helm/repositories?cluster=not-a-cluster", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["items"][0]["id"] == repository["id"]

    updated = api.client.patch(
        f"/api/v1/helm/repositories/{repository['id']}",
        headers=headers,
        json={"name": "bitnami-public", "url": "https://charts.example.test/stable"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "bitnami-public"

    deleted = api.client.delete(f"/api/v1/helm/repositories/{repository['id']}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json() == {"id": repository["id"], "status": "deleted"}
    assert api.client.get("/api/v1/helm/repositories", headers=headers).json()["items"] == []

    with api.factory() as database:
        actions = database.scalars(select(AuditAction).order_by(AuditAction.created_at)).all()
    assert [action.action for action in actions if action.resource_type == "helm_repository"] == [
        "helm.repository_created",
        "helm.repository_updated",
        "helm.repository_deleted",
    ]
    assert all("password" not in (action.context or "") for action in actions)


def test_repository_validation_and_conflicts(api: SimpleNamespace, admin: dict) -> None:
    headers = cookie_header(admin["cookie"])
    invalid_urls = ["ftp://charts.example.test", "https://user:pass@charts.example.test", "https://charts.example.test/?token=secret"]
    for url in invalid_urls:
        response = api.client.post(
            "/api/v1/helm/repositories", headers=headers, json={"name": "stable", "url": url}
        )
        assert response.status_code == 422, response.text
        assert response.json()["code"] == "invalid_repository_url"

    created = api.client.post(
        "/api/v1/helm/repositories", headers=headers, json={"name": "stable", "url": "https://charts.example.test"}
    )
    assert created.status_code == 201
    duplicate_name = api.client.post(
        "/api/v1/helm/repositories", headers=headers, json={"name": "STABLE", "url": "https://other.example.test"}
    )
    duplicate_url = api.client.post(
        "/api/v1/helm/repositories", headers=headers, json={"name": "other", "url": "https://charts.example.test/"}
    )
    assert duplicate_name.status_code == duplicate_url.status_code == 409


def test_viewers_can_list_but_cannot_mutate_repositories(api: SimpleNamespace, admin: dict) -> None:
    viewer = create_user(api, admin, "viewer@example.com", "viewer")
    viewer_headers = cookie_header(session_cookie(api, viewer["email"]))
    assert api.client.get("/api/v1/helm/repositories", headers=viewer_headers).status_code == 200
    created = api.client.post(
        "/api/v1/helm/repositories",
        headers=viewer_headers,
        json={"name": "stable", "url": "https://charts.example.test"},
    )
    assert created.status_code == 403
    assert created.json()["code"] == "insufficient_permissions"
