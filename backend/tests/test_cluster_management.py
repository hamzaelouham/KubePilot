import os
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

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
from app.models.entities import AuditAction, ClusterConnection, InstallationJob, Namespace, Workload




os.environ.setdefault("KUBEPILOT_WORKER_ENABLED", "false")
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


def create_operator(api: SimpleNamespace) -> dict:
    admin = admin_login(api)
    with api.client as client:
        response = client.post(
            "/api/v1/users",
            headers=cookie_header(admin["cookie"]),
            json={"email": "operator@example.com", "password": "correct-horse-00", "role": "operator"},
        )
    assert response.status_code == 201, response.text
    return response.json()


class _ProbeOkClient(ClusterClient):
    def health(self) -> None:
        return None

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

REPLACED_KUBECONFIG = """apiVersion: v1
kind: Config
clusters:
  - name: fallback
    cluster:
      server: https://fallback.example.com:6443
contexts:
  - name: fallback
    context:
      cluster: fallback
      user: fallback
current-context: fallback
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


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (None, "connected"),
        (ClusterUnavailableError("connection refused"), "unavailable"),
        (ClusterForbiddenError("denied"), "forbidden"),
    ],
)
def test_list_clusters_reports_live_connection_status(
    api: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception | None,
    expected: str,
) -> None:
    class HealthClient(_ProbeOkClient):
        def health(self) -> None:
            if error is not None:
                raise error

    database = api.factory()
    try:
        database.add(
            ClusterConnection(
                name="staging",
                endpoint="https://10.0.0.1:6443",
                kubeconfig_ref="",
                kubeconfig_content=VALID_KUBECONFIG,
                status="active",
            )
        )
        database.commit()
    finally:
        database.close()
    monkeypatch.setattr(
        "app.api.v1.routes.create_cluster_client",
        lambda settings, **kwargs: HealthClient(kwargs.get("cluster_name") or "primary", object(), object()),
    )

    admin = admin_login(api)
    with api.client as client:
        response = client.get("/api/v1/clusters", headers=cookie_header(admin["cookie"]))

    assert response.status_code == 200, response.text
    staging = next(item for item in response.json()["items"] if item["name"] == "staging")
    assert staging["status"] == "active"
    assert staging["connection_status"] == expected


def test_list_clusters_skips_probe_for_inactive_connections(api: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    database = api.factory()
    try:
        database.add(
            ClusterConnection(
                name="staging",
                endpoint="https://10.0.0.1:6443",
                kubeconfig_ref="",
                kubeconfig_content=VALID_KUBECONFIG,
                status="inactive",
            )
        )
        database.commit()
    finally:
        database.close()

    def raise_if_staging(settings, **kwargs):
        if kwargs.get("cluster_name") == "staging":
            raise AssertionError("inactive clusters must not be probed")
        return _ProbeOkClient("primary", object(), object())

    monkeypatch.setattr("app.api.v1.routes.create_cluster_client", raise_if_staging)
    admin = admin_login(api)
    with api.client as client:
        response = client.get("/api/v1/clusters", headers=cookie_header(admin["cookie"]))

    assert response.status_code == 200, response.text
    staging = next(item for item in response.json()["items"] if item["name"] == "staging")
    assert staging["status"] == "inactive"
    assert staging["connection_status"] == "inactive"


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


def create_managed_cluster(api: SimpleNamespace, admin: dict, name: str, kubeconfig: str = VALID_KUBECONFIG) -> str:
    with api.client as client:
        response = client.post(
            "/api/v1/clusters",
            headers=cookie_header(admin["cookie"]),
            json={"name": name, "kubeconfig_content": kubeconfig},
        )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_update_cluster_renames_and_records_audit(api: SimpleNamespace) -> None:
    admin = admin_login(api)
    cluster_id = create_managed_cluster(api, admin, "staging")
    with api.client as client:
        response = client.patch(
            f"/api/v1/clusters/{cluster_id}",
            headers=cookie_header(admin["cookie"]),
            json={"name": "renamed"},
        )
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "renamed"
    assert response.json()["endpoint"] == "https://10.0.0.1:6443"

    database = api.factory()
    try:
        row = database.get(ClusterConnection, UUID(cluster_id))
        assert row is not None
        assert row.name == "renamed"
        audit = database.scalar(
            select(AuditAction)
            .where(AuditAction.action == "cluster.update")
            .order_by(AuditAction.created_at.desc())
        )
        assert audit is not None
        assert audit.resource_id == cluster_id
        assert audit.result == "success"
    finally:
        database.close()


def test_update_cluster_operator_can_rename(api: SimpleNamespace) -> None:
    create_operator(api)
    admin = admin_login(api)
    cluster_id = create_managed_cluster(api, admin, "staging")
    operator = login(api, "operator@example.com", "correct-horse-00")
    with api.client as client:
        response = client.patch(
            f"/api/v1/clusters/{cluster_id}",
            headers=cookie_header(operator["cookie"]),
            json={"name": "renamed"},
        )
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "renamed"


def test_update_cluster_viewer_returns_403(api: SimpleNamespace) -> None:
    create_viewer(api)
    admin = admin_login(api)
    cluster_id = create_managed_cluster(api, admin, "staging")
    viewer = login(api, "viewer@example.com", "correct-horse-00")
    with api.client as client:
        response = client.patch(
            f"/api/v1/clusters/{cluster_id}",
            headers=cookie_header(viewer["cookie"]),
            json={"name": "renamed"},
        )
    assert response.status_code == 403, response.text


def test_update_cluster_duplicate_name_returns_409(api: SimpleNamespace) -> None:
    admin = admin_login(api)
    create_managed_cluster(api, admin, "staging")
    other = create_managed_cluster(api, admin, "selected")
    with api.client as client:
        response = client.patch(
            f"/api/v1/clusters/{other}",
            headers=cookie_header(admin["cookie"]),
            json={"name": "staging"},
        )
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "duplicate_cluster_name"


def test_update_cluster_rename_to_self_ok(api: SimpleNamespace) -> None:
    admin = admin_login(api)
    cluster_id = create_managed_cluster(api, admin, "staging")
    with api.client as client:
        response = client.patch(
            f"/api/v1/clusters/{cluster_id}",
            headers=cookie_header(admin["cookie"]),
            json={"name": " staging "},
        )
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "staging"


def test_update_cluster_empty_name_returns_422(api: SimpleNamespace) -> None:
    admin = admin_login(api)
    cluster_id = create_managed_cluster(api, admin, "staging")
    with api.client as client:
        response = client.patch(
            f"/api/v1/clusters/{cluster_id}",
            headers=cookie_header(admin["cookie"]),
            json={"name": "   "},
        )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "validation_error"


def test_update_cluster_empty_body_returns_422(api: SimpleNamespace) -> None:
    admin = admin_login(api)
    cluster_id = create_managed_cluster(api, admin, "staging")
    with api.client as client:
        response = client.patch(
            f"/api/v1/clusters/{cluster_id}",
            headers=cookie_header(admin["cookie"]),
            json={},
        )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "validation_error"


def test_update_cluster_replaces_kubeconfig_and_endpoint(api: SimpleNamespace) -> None:
    admin = admin_login(api)
    cluster_id = create_managed_cluster(api, admin, "staging")
    with api.client as client:
        response = client.patch(
            f"/api/v1/clusters/{cluster_id}",
            headers=cookie_header(admin["cookie"]),
            json={"kubeconfig_content": REPLACED_KUBECONFIG},
        )
    assert response.status_code == 200, response.text
    assert response.json()["endpoint"] == "https://fallback.example.com:6443"

    database = api.factory()
    try:
        row = database.get(ClusterConnection, UUID(cluster_id))
        assert row is not None
        assert row.endpoint == "https://fallback.example.com:6443"
        assert row.kubeconfig_ref == ""
        assert row.kubeconfig_content == REPLACED_KUBECONFIG.strip()
        audit = database.scalar(
            select(AuditAction)
            .where(AuditAction.action == "cluster.update")
            .order_by(AuditAction.created_at.desc())
        )
        assert audit is not None
        assert audit.resource_id == cluster_id
    finally:
        database.close()


def test_update_cluster_unreachable_replace_returns_502_row_unchanged(
    api: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = admin_login(api)
    cluster_id = create_managed_cluster(api, admin, "staging")

    def unavailable_probe(settings, **kwargs):
        raise ClusterUnavailableError("connection refused")

    monkeypatch.setattr("app.api.v1.routes.create_cluster_client", unavailable_probe)
    with api.client as client:
        response = client.patch(
            f"/api/v1/clusters/{cluster_id}",
            headers=cookie_header(admin["cookie"]),
            json={"kubeconfig_content": REPLACED_KUBECONFIG},
        )
    assert response.status_code == 502, response.text
    assert response.json()["code"] == "kubeconfig_unreachable"

    database = api.factory()
    try:
        row = database.get(ClusterConnection, UUID(cluster_id))
        assert row is not None
        assert row.name == "staging"
        assert row.endpoint == "https://10.0.0.1:6443"
        assert row.kubeconfig_content == VALID_KUBECONFIG
    finally:
        database.close()


def test_update_cluster_rejected_kubeconfig_returns_422(api: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    admin = admin_login(api)
    cluster_id = create_managed_cluster(api, admin, "staging")

    def forbidden_probe(settings, **kwargs):
        raise ClusterForbiddenError("Kubernetes RBAC denied the requested operation")

    monkeypatch.setattr("app.api.v1.routes.create_cluster_client", forbidden_probe)
    with api.client as client:
        response = client.patch(
            f"/api/v1/clusters/{cluster_id}",
            headers=cookie_header(admin["cookie"]),
            json={"kubeconfig_content": REPLACED_KUBECONFIG},
        )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "kubeconfig_unreachable"


def test_delete_cluster_removes_row_cascades_and_audits(api: SimpleNamespace) -> None:
    admin = admin_login(api)
    cluster_id = create_managed_cluster(api, admin, "staging")

    database = api.factory()
    try:
        namespace = Namespace(cluster_id=UUID(cluster_id), name="default", status="Active")
        workload = Workload(cluster_id=UUID(cluster_id), namespace="default", kind="Deployment", name="api", status="Running")
        installation = InstallationJob(
            package_id="staging-package",
            package_name="redis",
            chart_name="redis",
            chart_repository="bitnami",
            chart_version="2.0.0",
            cluster_id=UUID(cluster_id),
            namespace="default",
            release_name="staging-redis",
        )
        primary = database.scalar(select(ClusterConnection).where(ClusterConnection.name == "primary"))
        assert primary is not None
        unrelated_installation = InstallationJob(
            package_id="primary-package",
            package_name="redis",
            chart_name="redis",
            chart_repository="bitnami",
            chart_version="2.0.0",
            cluster_id=primary.id,
            namespace="default",
            release_name="primary-redis",
        )
        database.add_all([namespace, workload, installation, unrelated_installation])
        database.commit()
        namespace_id = namespace.id
        workload_id = workload.id
        installation_id = installation.id
        unrelated_installation_id = unrelated_installation.id
    finally:
        database.close()

    with api.client as client:
        response = client.delete(f"/api/v1/clusters/{cluster_id}", headers=cookie_header(admin["cookie"]))
    assert response.status_code == 204, response.text

    database = api.factory()
    try:
        assert database.get(ClusterConnection, UUID(cluster_id)) is None
        assert database.get(Namespace, namespace_id) is None
        assert database.get(Workload, workload_id) is None
        assert database.get(InstallationJob, installation_id) is None
        assert database.get(InstallationJob, unrelated_installation_id) is not None
        audit = database.scalar(
            select(AuditAction)
            .where(AuditAction.action == "cluster.delete")
            .order_by(AuditAction.created_at.desc())
        )
        assert audit is not None
        assert audit.resource_id == cluster_id
        assert audit.result == "success"
        assert audit.context is not None
        assert '"staging"' in audit.context
    finally:
        database.close()


def test_delete_cluster_unknown_id_returns_404(api: SimpleNamespace) -> None:
    admin = admin_login(api)
    with api.client as client:
        response = client.delete(f"/api/v1/clusters/{uuid4()}", headers=cookie_header(admin["cookie"]))
    assert response.status_code == 404, response.text
    assert response.json()["code"] == "cluster_not_found"


def test_delete_cluster_viewer_returns_403(api: SimpleNamespace) -> None:
    create_viewer(api)
    admin = admin_login(api)
    cluster_id = create_managed_cluster(api, admin, "staging")
    viewer = login(api, "viewer@example.com", "correct-horse-00")
    with api.client as client:
        response = client.delete(f"/api/v1/clusters/{cluster_id}", headers=cookie_header(viewer["cookie"]))
    assert response.status_code == 403, response.text


def test_delete_cluster_operator_returns_403(api: SimpleNamespace) -> None:
    create_operator(api)
    admin = admin_login(api)
    cluster_id = create_managed_cluster(api, admin, "staging")
    operator = login(api, "operator@example.com", "correct-horse-00")
    with api.client as client:
        response = client.delete(f"/api/v1/clusters/{cluster_id}", headers=cookie_header(operator["cookie"]))
    assert response.status_code == 403, response.text
