from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session as DatabaseSession

from app.core.config import Settings
from app.db.session import create_session_factory
from app.kubernetes.client import (
    ClusterClient,
    ClusterForbiddenError,
    ClusterUnavailableError,
)
from app.models.base import Base
from app.models.entities import AuditAction, ClusterConnection


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


class _ProbeOkClient(ClusterClient):
    def namespaces(self) -> list[tuple[str, str]]:
        return [("default", "Active")]


@pytest.fixture(autouse=True)
def _connected_create_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.v1.routes.create_cluster_client",
        lambda settings, **kwargs: _ProbeOkClient("probe", object(), object()),
    )


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

MULTI_CLUSTER_KUBECONFIG = """apiVersion: v1
kind: Config
clusters:
  - name: prod
    cluster:
      server: https://prod.example.com:6443
  - name: staging
    cluster:
      server: https://10.0.0.1:6443
contexts:
  - name: prod
    context:
      cluster: prod
      user: prod
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


def test_create_cluster_resolves_endpoint_from_current_context(api: SimpleNamespace) -> None:
    admin = admin_login(api)
    with api.client as client:
        response = client.post(
            "/api/v1/clusters",
            headers=cookie_header(admin["cookie"]),
            json={"name": "staging", "kubeconfig_content": MULTI_CLUSTER_KUBECONFIG},
        )
    assert response.status_code == 201, response.text
    assert response.json()["endpoint"] == "https://10.0.0.1:6443"


def test_create_cluster_missing_current_context_returns_422(api: SimpleNamespace) -> None:
    admin = admin_login(api)
    kubeconfig = """apiVersion: v1
kind: Config
clusters:
  - name: prod
    cluster:
      server: https://prod.example.com:6443
contexts:
  - name: prod
    context:
      cluster: prod
      user: prod
"""
    with api.client as client:
        response = client.post(
            "/api/v1/clusters",
            headers=cookie_header(admin["cookie"]),
            json={"name": "bad", "kubeconfig_content": kubeconfig},
        )
    assert response.status_code == 422, response.text
    assert "current-context" in response.json()["message"]


def test_create_cluster_unknown_current_context_returns_422(api: SimpleNamespace) -> None:
    admin = admin_login(api)
    kubeconfig = """apiVersion: v1
kind: Config
clusters:
  - name: prod
    cluster:
      server: https://prod.example.com:6443
contexts:
  - name: prod
    context:
      cluster: prod
      user: prod
current-context: ghost
"""
    with api.client as client:
        response = client.post(
            "/api/v1/clusters",
            headers=cookie_header(admin["cookie"]),
            json={"name": "bad", "kubeconfig_content": kubeconfig},
        )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "invalid_kubeconfig"


def test_create_cluster_context_reference_unknown_cluster_returns_422(api: SimpleNamespace) -> None:
    admin = admin_login(api)
    kubeconfig = """apiVersion: v1
kind: Config
clusters:
  - name: prod
    cluster:
      server: https://prod.example.com:6443
contexts:
  - name: staging
    context:
      cluster: ghost
      user: staging
current-context: staging
"""
    with api.client as client:
        response = client.post(
            "/api/v1/clusters",
            headers=cookie_header(admin["cookie"]),
            json={"name": "bad", "kubeconfig_content": kubeconfig},
        )
    assert response.status_code == 422, response.text
    assert "ghost" in response.json()["message"]


def test_create_cluster_unreachable_probe_returns_502_and_does_not_persist(api: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_probe(settings, **kwargs):
        raise ClusterUnavailableError("Kubernetes cluster is unavailable: [Errno 111] Connection refused")

    monkeypatch.setattr("app.api.v1.routes.create_cluster_client", fail_probe)
    admin = admin_login(api)
    with api.client as client:
        response = client.post(
            "/api/v1/clusters",
            headers=cookie_header(admin["cookie"]),
            json={"name": "staging", "kubeconfig_content": VALID_KUBECONFIG},
        )
        listing = client.get("/api/v1/clusters", headers=cookie_header(admin["cookie"]))
    assert response.status_code == 502, response.text
    assert response.json()["code"] == "kubeconfig_unreachable"
    assert "https://10.0.0.1:6443" in response.json()["message"]
    assert "Connection refused" in response.json()["message"]
    assert all(item["name"] != "staging" for item in listing.json()["items"])


def test_create_cluster_loopback_server_includes_hint(api: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_probe(settings, **kwargs):
        raise ClusterUnavailableError("Kubernetes cluster is unavailable: [Errno 111] Connection refused")

    monkeypatch.setattr("app.api.v1.routes.create_cluster_client", fail_probe)
    admin = admin_login(api)
    kubeconfig = """apiVersion: v1
kind: Config
clusters:
  - name: kind
    cluster:
      server: https://127.0.0.1:40393
contexts:
  - name: kind
    context:
      cluster: kind
      user: kind
current-context: kind
"""
    with api.client as client:
        response = client.post(
            "/api/v1/clusters",
            headers=cookie_header(admin["cookie"]),
            json={"name": "kind", "kubeconfig_content": kubeconfig},
        )
    assert response.status_code == 502, response.text
    assert "127.0.0.1" in response.json()["message"]
    assert "localhost" in response.json()["message"]


def test_create_cluster_rejected_credentials_returns_422(api: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden_probe(settings, **kwargs):
        raise ClusterForbiddenError("Kubernetes RBAC denied the requested operation")

    monkeypatch.setattr("app.api.v1.routes.create_cluster_client", forbidden_probe)
    admin = admin_login(api)
    with api.client as client:
        response = client.post(
            "/api/v1/clusters",
            headers=cookie_header(admin["cookie"]),
            json={"name": "staging", "kubeconfig_content": VALID_KUBECONFIG},
        )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "kubeconfig_unreachable"


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


def test_update_cluster_status_round_trip(api: SimpleNamespace) -> None:
    admin = admin_login(api)
    with api.client as client:
        create = client.post(
            "/api/v1/clusters",
            headers=cookie_header(admin["cookie"]),
            json={"name": "staging", "kubeconfig_content": VALID_KUBECONFIG},
        )
        assert create.status_code == 201, create.text
        cluster_id = create.json()["id"]

        deactivate = client.patch(
            f"/api/v1/clusters/{cluster_id}",
            headers=cookie_header(admin["cookie"]),
            json={"status": "inactive"},
        )
        assert deactivate.status_code == 200, deactivate.text
        assert deactivate.json()["status"] == "inactive"

        reactivate = client.patch(
            f"/api/v1/clusters/{cluster_id}",
            headers=cookie_header(admin["cookie"]),
            json={"status": "active"},
        )
        assert reactivate.status_code == 200, reactivate.text
        assert reactivate.json()["status"] == "active"
        assert reactivate.json()["name"] == "staging"
        assert reactivate.json()["endpoint"] == "https://10.0.0.1:6443"

    database = api.factory()
    try:
        row = database.scalar(select(ClusterConnection).where(ClusterConnection.name == "staging"))
        assert row is not None
        assert row.status == "active"
    finally:
        database.close()


def test_update_cluster_status_unknown_id_returns_404(api: SimpleNamespace) -> None:
    admin = admin_login(api)
    with api.client as client:
        response = client.patch(
            f"/api/v1/clusters/{uuid4()}",
            headers=cookie_header(admin["cookie"]),
            json={"status": "inactive"},
        )
    assert response.status_code == 404, response.text
    assert response.json()["code"] == "cluster_not_found"


def test_update_cluster_status_invalid_value_returns_422(api: SimpleNamespace) -> None:
    admin = admin_login(api)
    with api.client as client:
        create = client.post(
            "/api/v1/clusters",
            headers=cookie_header(admin["cookie"]),
            json={"name": "staging", "kubeconfig_content": VALID_KUBECONFIG},
        )
        assert create.status_code == 201, create.text
        response = client.patch(
            f"/api/v1/clusters/{create.json()['id']}",
            headers=cookie_header(admin["cookie"]),
            json={"status": "paused"},
        )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "validation_error"


def test_update_cluster_status_viewer_returns_403(api: SimpleNamespace) -> None:
    create_viewer(api)
    admin = admin_login(api)
    with api.client as client:
        create = client.post(
            "/api/v1/clusters",
            headers=cookie_header(admin["cookie"]),
            json={"name": "staging", "kubeconfig_content": VALID_KUBECONFIG},
        )
        assert create.status_code == 201, create.text
        cluster_id = create.json()["id"]
    viewer = login(api, "viewer@example.com", "correct-horse-00")
    with api.client as client:
        response = client.patch(
            f"/api/v1/clusters/{cluster_id}",
            headers=cookie_header(viewer["cookie"]),
            json={"status": "inactive"},
        )
    assert response.status_code == 403, response.text


def test_update_cluster_status_records_audit(api: SimpleNamespace) -> None:
    admin = admin_login(api)
    with api.client as client:
        create = client.post(
            "/api/v1/clusters",
            headers=cookie_header(admin["cookie"]),
            json={"name": "staging", "kubeconfig_content": VALID_KUBECONFIG},
        )
        assert create.status_code == 201, create.text
        cluster_id = create.json()["id"]
        toggle = client.patch(
            f"/api/v1/clusters/{cluster_id}",
            headers=cookie_header(admin["cookie"]),
            json={"status": "inactive"},
        )
        assert toggle.status_code == 200, toggle.text

    database = api.factory()
    try:
        admin_row = database.scalar(select(ClusterConnection).where(ClusterConnection.name == "primary"))
        assert admin_row is not None
        audit = database.scalar(
            select(AuditAction)
            .where(AuditAction.action == "cluster.status_change")
            .order_by(AuditAction.created_at.desc())
        )
        assert audit is not None
        assert audit.actor_id is not None
        assert audit.resource_type == "cluster_connection"
        assert audit.resource_id == cluster_id
        assert audit.result == "success"
    finally:
        database.close()
