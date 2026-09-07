from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session as DatabaseSession

from app.core.config import Settings
from app.db.session import create_session_factory
from app.models.base import Base
from app.models.entities import ClusterConnection


@pytest.fixture()
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    database_url = f"sqlite:///{tmp_path / 'kubepilot-clusters.db'}"
    monkeypatch.setenv("KUBEPILOT_AUTH_SECRET", "x" * 32)
    monkeypatch.setenv("KUBEPILOT_DATABASE_URL", database_url)
    monkeypatch.setenv("KUBEPILOT_ADMIN_EMAIL", "ops@kubepilot.io")
    monkeypatch.setenv("KUBEPILOT_ADMIN_PASSWORD", "kubepilot")
    monkeypatch.setenv("KUBEPILOT_CLUSTER_NAME", "primary")

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


def create_viewer(api: SimpleNamespace) -> dict:
    admin = admin_login(api)
    with api.client as client:
        response = client.post(
            "/api/v1/users",
            headers=cookie_header(admin["cookie"]),
            json={"email": "viewer@example.com", "password": "correct-horse-00", "role": "viewer"},
        )
    assert response.status_code == 201, response.text
    return response.json()


VALID_KUBECONFIG = """apiVersion: v1
kind: Config
clusters:
  - name: staging
    cluster:
      server: https://10.0.0.1:6443
contexts:
  - name: staging
    context:
      cluster: staging
      user: staging
current-context: staging
"""


def test_default_cluster_seeded_on_startup(api: SimpleNamespace) -> None:
    with api.client as client:
        admin = admin_login(api)
        response = client.get("/api/v1/clusters", headers=cookie_header(admin["cookie"]))
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["name"] == "primary"
    assert body["items"][0]["endpoint"] == "in-cluster"
    assert body["items"][0]["status"] == "active"


def test_seeding_is_idempotent(api: SimpleNamespace) -> None:
    with api.client as client:
        admin_login(api)
    with api.client as client:
        admin = admin_login(api)
        response = client.get("/api/v1/clusters", headers=cookie_header(admin["cookie"]))
    assert response.status_code == 200, response.text
    assert len(response.json()["items"]) == 1


def test_list_clusters_excludes_kubeconfig_content(api: SimpleNamespace) -> None:
    with api.client as client:
        admin = admin_login(api)
        create = client.post(
            "/api/v1/clusters",
            headers=cookie_header(admin["cookie"]),
            json={"name": "staging", "kubeconfig_content": VALID_KUBECONFIG},
        )
        assert create.status_code == 201, create.text
        response = client.get("/api/v1/clusters", headers=cookie_header(admin["cookie"]))
    assert response.status_code == 200, response.text
    for item in response.json()["items"]:
        assert "kubeconfig_content" not in item


def test_viewer_can_list_clusters(api: SimpleNamespace) -> None:
    create_viewer(api)
    admin = admin_login(api)
    with api.client as client:
        response = client.get("/api/v1/clusters", headers=cookie_header(admin["cookie"]))
    assert response.status_code == 200, response.text
    assert len(response.json()["items"]) >= 1


def test_create_cluster_json_extracts_endpoint(api: SimpleNamespace) -> None:
    admin = admin_login(api)
    with api.client as client:
        response = client.post(
            "/api/v1/clusters",
            headers=cookie_header(admin["cookie"]),
            json={"name": "staging", "kubeconfig_content": VALID_KUBECONFIG},
        )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "staging"
    assert body["endpoint"] == "https://10.0.0.1:6443"
    assert body["status"] == "active"

    database = api.factory()
    try:
        row = database.scalar(select(ClusterConnection).where(ClusterConnection.name == "staging"))
        assert row is not None
        assert row.kubeconfig_content == VALID_KUBECONFIG
    finally:
        database.close()


def test_create_cluster_multipart_upload(api: SimpleNamespace) -> None:
    admin = admin_login(api)
    with api.client as client:
        response = client.post(
            "/api/v1/clusters",
            headers=cookie_header(admin["cookie"]),
            data={"name": "uploaded"},
            files={"kubeconfig_file": ("staging.yaml", VALID_KUBECONFIG, "text/yaml")},
        )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "uploaded"
    assert body["endpoint"] == "https://10.0.0.1:6443"

    database = api.factory()
    try:
        row = database.scalar(select(ClusterConnection).where(ClusterConnection.name == "uploaded"))
        assert row is not None
        assert row.kubeconfig_content == VALID_KUBECONFIG
    finally:
        database.close()


def test_create_cluster_duplicate_name_returns_409(api: SimpleNamespace) -> None:
    admin = admin_login(api)
    with api.client as client:
        first = client.post(
            "/api/v1/clusters",
            headers=cookie_header(admin["cookie"]),
            json={"name": "staging", "kubeconfig_content": VALID_KUBECONFIG},
        )
        assert first.status_code == 201, first.text
        duplicate = client.post(
            "/api/v1/clusters",
            headers=cookie_header(admin["cookie"]),
            json={"name": "staging", "kubeconfig_content": VALID_KUBECONFIG},
        )
    assert duplicate.status_code == 409, duplicate.text


def test_create_cluster_invalid_yaml_returns_422(api: SimpleNamespace) -> None:
    admin = admin_login(api)
    with api.client as client:
        response = client.post(
            "/api/v1/clusters",
            headers=cookie_header(admin["cookie"]),
            json={"name": "bad", "kubeconfig_content": "not: [valid yaml: :"},
        )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "invalid_kubeconfig"


def test_create_cluster_missing_clusters_key_returns_422(api: SimpleNamespace) -> None:
    admin = admin_login(api)
    with api.client as client:
        response = client.post(
            "/api/v1/clusters",
            headers=cookie_header(admin["cookie"]),
            json={"name": "bad", "kubeconfig_content": "apiVersion: v1\nkind: Config\n"},
        )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "invalid_kubeconfig"


def test_create_cluster_missing_server_returns_422(api: SimpleNamespace) -> None:
    admin = admin_login(api)
    kubeconfig = """apiVersion: v1
kind: Config
clusters:
  - name: staging
    cluster:
      certificate-authority-data: abc
"""
    with api.client as client:
        response = client.post(
            "/api/v1/clusters",
            headers=cookie_header(admin["cookie"]),
            json={"name": "bad", "kubeconfig_content": kubeconfig},
        )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "invalid_kubeconfig"


def test_create_cluster_non_admin_returns_403(api: SimpleNamespace) -> None:
    create_viewer(api)
    viewer = login(api, "viewer@example.com", "correct-horse-00")
    with api.client as client:
        response = client.post(
            "/api/v1/clusters",
            headers=cookie_header(viewer["cookie"]),
            json={"name": "forbidden", "kubeconfig_content": VALID_KUBECONFIG},
        )
    assert response.status_code == 403, response.text
