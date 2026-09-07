from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session as DatabaseSession

from app.core.config import Settings
from app.db.session import create_session_factory
from app.kubernetes.client import ClusterClient, ClusterUnavailableError
from app.models.base import Base
from app.models.entities import ClusterConnection


@pytest.fixture()
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    database_url = f"sqlite:///{tmp_path / 'kubepilot-routing.db'}"
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


@pytest.fixture()
def authed_api(api: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    from app.core.dependencies import AuthenticatedActor, get_current_actor

    app = api.client.app
    app.dependency_overrides[get_current_actor] = lambda: AuthenticatedActor("ops", "admin")
    return api


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
users:
  - name: staging
    user:
      token: fake-token
current-context: staging
"""


def seed_registered_cluster(api: SimpleNamespace, name: str, content: str | None) -> None:
    database = api.factory()
    try:
        existing = database.scalar(select(ClusterConnection).where(ClusterConnection.name == name))
        if existing is None:
            database.add(ClusterConnection(name=name, endpoint="https://10.0.0.1:6443", kubeconfig_ref=name, kubeconfig_content=content))
            database.commit()
    finally:
        database.close()


class StubClusterClient(ClusterClient):
    def namespaces(self) -> list[tuple[str, str]]:
        return [(self.cluster_name, "Active")]


def test_default_cluster_uses_in_cluster_when_param_absent(authed_api: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict] = []

    def fake_create_cluster_client(settings, loader=None, kubeconfig_content=None, cluster_name=None):
        captured.append({"kubeconfig_content": kubeconfig_content, "cluster_name": cluster_name or settings.cluster_name})
        return StubClusterClient(cluster_name or settings.cluster_name, object(), object())

    monkeypatch.setattr("app.core.dependencies.create_cluster_client", fake_create_cluster_client)
    with authed_api.client as client:
        response = client.get("/api/v1/cluster/namespaces")
    assert response.status_code == 200, response.text
    assert captured == [{"kubeconfig_content": None, "cluster_name": "primary"}]


def test_named_default_cluster_uses_no_kubeconfig(authed_api: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict] = []

    def fake_create_cluster_client(settings, loader=None, kubeconfig_content=None, cluster_name=None):
        captured.append({"kubeconfig_content": kubeconfig_content, "cluster_name": cluster_name or settings.cluster_name})
        return StubClusterClient(cluster_name or settings.cluster_name, object(), object())

    monkeypatch.setattr("app.core.dependencies.create_cluster_client", fake_create_cluster_client)
    with authed_api.client as client:
        response = client.get("/api/v1/cluster/namespaces?cluster=primary")
    assert response.status_code == 200, response.text
    assert captured == [{"kubeconfig_content": None, "cluster_name": "primary"}]


def test_registered_cluster_loads_kubeconfig_from_store(authed_api: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_registered_cluster(authed_api, "staging", VALID_KUBECONFIG)
    captured: list[dict] = []

    def fake_create_cluster_client(settings, loader=None, kubeconfig_content=None, cluster_name=None):
        captured.append({"kubeconfig_content": kubeconfig_content, "cluster_name": cluster_name or settings.cluster_name})
        return StubClusterClient(cluster_name or settings.cluster_name, object(), object())

    monkeypatch.setattr("app.core.dependencies.create_cluster_client", fake_create_cluster_client)
    with authed_api.client as client:
        response = client.get("/api/v1/cluster/namespaces?cluster=staging")
    assert response.status_code == 200, response.text
    assert captured == [{"kubeconfig_content": VALID_KUBECONFIG, "cluster_name": "staging"}]


def raise_if_called(*args, **kwargs) -> ClusterClient:
    raise AssertionError("create_cluster_client must not be called")


def test_unknown_cluster_returns_404(authed_api: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.dependencies.create_cluster_client", raise_if_called)
    with authed_api.client as client:
        response = client.get("/api/v1/cluster/namespaces?cluster=missing")
    assert response.status_code == 404, response.text
    assert response.json() == {"code": "cluster_not_found", "message": "Cluster was not found"}


def test_unloadable_kubeconfig_returns_503(authed_api: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_registered_cluster(authed_api, "broken", "apiVersion: v1\nclusters: [unclosed")
    with authed_api.client as client:
        response = client.get("/api/v1/cluster/namespaces?cluster=broken")
    assert response.status_code == 503, response.text
    assert response.json()["code"] == "cluster_unavailable"


def set_cluster_status(api: SimpleNamespace, name: str, status: str) -> None:
    database = api.factory()
    try:
        row = database.scalar(select(ClusterConnection).where(ClusterConnection.name == name))
        assert row is not None
        row.status = status
        database.commit()
    finally:
        database.close()


def test_inactive_cluster_returns_404(authed_api: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_registered_cluster(authed_api, "staging", VALID_KUBECONFIG)
    set_cluster_status(authed_api, "staging", "inactive")
    monkeypatch.setattr("app.core.dependencies.create_cluster_client", raise_if_called)
    with authed_api.client as client:
        response = client.get("/api/v1/cluster/namespaces?cluster=staging")
    assert response.status_code == 404, response.text
    assert response.json() == {"code": "cluster_not_found", "message": "Cluster was not found"}


def test_reactivated_cluster_loads_kubeconfig_again(authed_api: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_registered_cluster(authed_api, "staging", VALID_KUBECONFIG)
    set_cluster_status(authed_api, "staging", "inactive")
    set_cluster_status(authed_api, "staging", "active")
    captured: list[dict] = []

    def fake_create_cluster_client(settings, loader=None, kubeconfig_content=None, cluster_name=None):
        captured.append({"kubeconfig_content": kubeconfig_content, "cluster_name": cluster_name or settings.cluster_name})
        return StubClusterClient(cluster_name or settings.cluster_name, object(), object())

    monkeypatch.setattr("app.core.dependencies.create_cluster_client", fake_create_cluster_client)
    with authed_api.client as client:
        response = client.get("/api/v1/cluster/namespaces?cluster=staging")
    assert response.status_code == 200, response.text
    assert captured == [{"kubeconfig_content": VALID_KUBECONFIG, "cluster_name": "staging"}]