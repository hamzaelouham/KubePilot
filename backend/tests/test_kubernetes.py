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
    ResourceNotFoundError,
    classify_kubernetes_error,
    create_cluster_client,
)


class FakeCore:
    def __init__(self) -> None:
        self.namespace_calls: list[str | None] = []

    def list_namespaced_pod(self, namespace: str):
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


def test_namespaced_replica_set_listing_uses_namespaced_method() -> None:
    class FakeApps:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def list_namespaced_replica_set(self, namespace: str):
            self.calls.append(f"ns:{namespace}")
            return SimpleNamespace(
                items=[
                    SimpleNamespace(
                        metadata=SimpleNamespace(namespace=namespace, name="rs-1"),
                        status=SimpleNamespace(available_replicas=2),
                    )
                ]
            )

    apps = FakeApps()
    cluster = ClusterClient("test-cluster", object(), apps)
    resources = cluster.resources("replica-sets", "payments")
    assert apps.calls == ["ns:payments"]
    assert resources[0].namespace == "payments"
    assert resources[0].status == "2"


def test_cluster_scoped_resources_list_at_cluster_level() -> None:
    class FakeStorage:
        def list_storage_class(self):
            return SimpleNamespace(
                items=[SimpleNamespace(metadata=SimpleNamespace(name="standard"))]
            )

    cluster = ClusterClient("test-cluster", object(), object(), storage=FakeStorage())
    resources = cluster.resources("storage-classes", None)
    assert len(resources) == 1
    assert resources[0].name == "standard"
    assert resources[0].namespace is None


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


class FakeDetailCore:
    def read_namespaced_pod(self, name: str, namespace: str):
        return SimpleNamespace(
            metadata=SimpleNamespace(
                namespace=namespace,
                name=name,
                labels={"app": "api"},
                annotations={"kube-secret-token": "super-secret-value"},
            ),
            status=SimpleNamespace(phase="Running", to_dict=lambda: {"phase": "Running"}),
            to_dict=lambda: {
                "metadata": {
                    "namespace": namespace,
                    "name": name,
                    "labels": {"app": "api"},
                    "annotations": {"kube-secret-token": "super-secret-value"},
                },
                "status": {"phase": "Running"},
            },
        )


def test_detail_returns_typed_resources() -> None:
    core = FakeDetailCore()
    cluster = ClusterClient("test-cluster", core, object())
    detail = cluster.detail("pods", "api-1", "default")
    assert detail["name"] == "api-1"
    assert detail["namespace"] == "default"
    assert detail["kind"] == "Pod"
    assert detail["status"] == "Running"
    assert detail["metadata"]["app"] == "api"


def test_detail_redacts_sensitive_metadata() -> None:
    core = FakeDetailCore()
    cluster = ClusterClient("test-cluster", core, object())
    detail = cluster.detail("pods", "api-1", "default")
    assert detail["metadata"]["kube-secret-token"] == "[REDACTED]"


def test_yaml_redacts_sensitive_fields() -> None:
    core = FakeDetailCore()
    cluster = ClusterClient("test-cluster", core, object())
    content, truncated = cluster.yaml("pods", "api-1", "default")
    assert not truncated
    assert "super-secret-value" not in content
    assert "REDACTED" in content


def test_detail_node_is_cluster_scoped_via_route(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KUBEPILOT_AUTH_SECRET", "x" * 32)
    monkeypatch.setenv("KUBEPILOT_DATABASE_URL", "sqlite:///:memory:")
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_current_actor] = lambda: AuthenticatedActor("ops", "admin")
    app.dependency_overrides[get_cluster_client] = lambda: ClusterClient("test-cluster", FakeDetailCore(), object())
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/cluster/resources/nodes/node-1?cluster=other-cluster"
        )
    assert response.status_code == 422
    assert response.json() == {"code": "invalid_resource_identity", "message": "Invalid cluster scope"}


def test_detail_namespaced_resource_requires_namespace(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KUBEPILOT_AUTH_SECRET", "x" * 32)
    monkeypatch.setenv("KUBEPILOT_DATABASE_URL", "sqlite:///:memory:")
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_current_actor] = lambda: AuthenticatedActor("ops", "admin")
    app.dependency_overrides[get_cluster_client] = lambda: ClusterClient("test-cluster", FakeDetailCore(), object())
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/cluster/resources/pods/api-1?cluster=primary"
        )
    assert response.status_code == 422
    assert response.json() == {"code": "invalid_resource_identity", "message": "Namespace is required"}


def test_detail_not_found_maps_to_404(monkeypatch: pytest.MonkeyPatch) -> None:
    class NotFoundClient(ClusterClient):
        def detail(self, resource_type, name, namespace=None):
            raise ResourceNotFoundError("missing")

    monkeypatch.setenv("KUBEPILOT_AUTH_SECRET", "x" * 32)
    monkeypatch.setenv("KUBEPILOT_DATABASE_URL", "sqlite:///:memory:")
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_current_actor] = lambda: AuthenticatedActor("ops", "admin")
    app.dependency_overrides[get_cluster_client] = lambda: NotFoundClient("test", object(), object())
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/cluster/resources/pods/missing?cluster=primary&namespace=default"
        )
    assert response.status_code == 404
    assert response.json() == {"code": "resource_not_found", "message": "Kubernetes resource was not found"}


def test_detail_forbidden_maps_to_403(monkeypatch: pytest.MonkeyPatch) -> None:
    class ForbiddenClient(ClusterClient):
        def detail(self, resource_type, name, namespace=None):
            raise ClusterForbiddenError("denied")

    monkeypatch.setenv("KUBEPILOT_AUTH_SECRET", "x" * 32)
    monkeypatch.setenv("KUBEPILOT_DATABASE_URL", "sqlite:///:memory:")
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_current_actor] = lambda: AuthenticatedActor("ops", "admin")
    app.dependency_overrides[get_cluster_client] = lambda: ForbiddenClient("test", object(), object())
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/cluster/resources/pods/api-1?cluster=primary&namespace=default"
        )
    assert response.status_code == 403
    assert response.json() == {"code": "cluster_forbidden", "message": "Kubernetes access is forbidden"}


def test_detail_unauthenticated_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KUBEPILOT_AUTH_SECRET", "x" * 32)
    monkeypatch.setenv("KUBEPILOT_DATABASE_URL", "sqlite:///:memory:")
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_cluster_client] = lambda: ClusterClient("test-cluster", FakeDetailCore(), object())
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/cluster/resources/pods/api-1?cluster=primary&namespace=default"
        )
    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"
