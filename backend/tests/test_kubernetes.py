from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from kubernetes import config
from kubernetes.client.exceptions import ApiException

from app.core.config import Settings
from app.core.dependencies import AuthenticatedActor, _resolve_cookie_actor, get_current_actor
from app.api.v1.routes import get_cluster_client
from app.kubernetes.client import (
    ClusterClient,
    ClusterForbiddenError,
    ClusterUnavailableError,
    classify_kubernetes_error,
    create_cluster_client,
)


class FakeCore:
    def __init__(self) -> None:
        self.namespace_calls: list[str | None] = []

    def list_pod_for_namespace(self, namespace: str):
        self.namespace_calls.append(namespace)
        return SimpleNamespace(
            items=[
                SimpleNamespace(
                    metadata=SimpleNamespace(namespace=namespace, name="api-1"),
                    status=SimpleNamespace(phase="Running"),
                )
            ]
        )


def settings() -> Settings:
    return Settings(
        auth_secret="x" * 32,
        database_url="sqlite:///:memory:",
        cluster_name="test-cluster",
    )


def test_client_factory_uses_service_account_loader(monkeypatch: pytest.MonkeyPatch) -> None:
    loaded = False

    def loader() -> None:
        nonlocal loaded
        loaded = True

    cluster = create_cluster_client(settings(), loader=loader)
    assert loaded
    assert cluster.cluster_name == "test-cluster"


def test_missing_service_account_configuration_is_unavailable() -> None:
    def loader() -> None:
        raise config.ConfigException("not running in a pod")

    with pytest.raises(ClusterUnavailableError):
        create_cluster_client(settings(), loader=loader)


def test_forbidden_kubernetes_response_is_classified() -> None:
    error = ApiException(status=403)
    assert isinstance(classify_kubernetes_error(error), ClusterForbiddenError)


def test_namespaced_resource_call_preserves_namespace() -> None:
    core = FakeCore()
    cluster = ClusterClient("test-cluster", core, object())
    resources = cluster.resources("pods", "payments")
    assert core.namespace_calls == ["payments"]
    assert resources[0].namespace == "payments"


def test_forbidden_discovery_is_returned_as_safe_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class ForbiddenCluster(ClusterClient):
        def namespaces(self):
            raise ClusterForbiddenError("internal detail")

    from app.main import create_app

    monkeypatch.setenv("KUBEPILOT_AUTH_SECRET", "x" * 32)
    monkeypatch.setenv("KUBEPILOT_DATABASE_URL", "sqlite:///:memory:")
    app = create_app()
    app.dependency_overrides[get_current_actor] = lambda: AuthenticatedActor("ops", "admin")
    app.dependency_overrides[get_cluster_client] = lambda: ForbiddenCluster("test", object(), object())
    with TestClient(app) as client:
        response = client.get("/api/v1/cluster/namespaces")
    assert response.status_code == 403
    assert response.json() == {"code": "cluster_forbidden", "message": "Kubernetes access is forbidden"}


def test_tampered_shared_cookie_is_rejected() -> None:
    from app.db.session import create_session_factory

    settings_value = settings()
    database = create_session_factory(settings_value)()
    try:
        assert _resolve_cookie_actor("invalid.invalid", settings_value.auth_secret, database) is None
    finally:
        database.close()
