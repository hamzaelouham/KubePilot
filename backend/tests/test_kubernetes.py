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
    ResourceSummary,
    _health_status,
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


def _container(ready: bool = True, restart_count: int = 0, waiting: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        ready=ready,
        restart_count=restart_count,
        state=SimpleNamespace(waiting=SimpleNamespace(reason=waiting) if waiting else None),
    )


@pytest.mark.parametrize(
    ("phase", "containers", "expected"),
    [
        ("Running", None, "healthy"),
        ("Running", [_container()], "healthy"),
        ("Running", [_container(ready=False)], "warning"),
        ("Running", [_container(restart_count=2)], "healthy"),
        ("Running", [_container(waiting="ContainerCreating")], "warning"),
        ("Running", [_container(waiting="CrashLoopBackOff")], "error"),
        ("Running", [_container(waiting="ImagePullBackOff")], "error"),
        ("Pending", None, "error"),
        ("Failed", None, "error"),
        ("Unknown", None, "error"),
        (None, None, "error"),
    ],
)
def test_pod_health_classification(phase, containers, expected) -> None:
    status = SimpleNamespace(phase=phase, container_statuses=containers)
    item = SimpleNamespace(status=status, spec=None)
    assert _health_status(item, "Pod") == expected


def test_deployment_health_classification() -> None:
    def build(replicas: int, ready: int | None, available: int | None, unavailable: int = 0) -> SimpleNamespace:
        spec = SimpleNamespace(replicas=replicas)
        status = SimpleNamespace(
            ready_replicas=ready,
            available_replicas=available,
            unavailable_replicas=unavailable,
        )
        return SimpleNamespace(spec=spec, status=status)

    assert _health_status(build(3, 3, 3, 0), "Deployment") == "healthy"
    assert _health_status(build(3, 2, 2, 1), "Deployment") == "warning"
    assert _health_status(build(3, 0, 0, 3), "Deployment") == "error"
    assert _health_status(build(0, 0, 0, 0), "Deployment") == "unknown"
    assert _health_status(build(3, 3, None, 0), "Deployment") == "healthy"
    assert _health_status(build(3, 3, 3, 1), "Deployment") == "warning"


def test_replica_set_uses_replicas_health() -> None:
    spec = SimpleNamespace(replicas=2)
    status = SimpleNamespace(ready_replicas=1, available_replicas=1, unavailable_replicas=1)
    item = SimpleNamespace(spec=spec, status=status)
    assert _health_status(item, "ReplicaSet") == "warning"


@pytest.mark.parametrize(
    ("conditions", "expected"),
    [
        ([SimpleNamespace(type="Ready", status="True")], "healthy"),
        ([SimpleNamespace(type="MemoryPressure", status="True"), SimpleNamespace(type="Ready", status="True")], "healthy"),
        ([SimpleNamespace(type="Ready", status="False")], "error"),
        ([SimpleNamespace(type="Ready", status="Unknown")], "warning"),
        ([], "unknown"),
    ],
)
def test_node_health_classification(conditions, expected) -> None:
    status = SimpleNamespace(conditions=conditions)
    item = SimpleNamespace(status=status)
    assert _health_status(item, "Node") == expected


@pytest.mark.parametrize(
    ("phase", "expected"),
    [
        ("Bound", "healthy"),
        ("Available", "healthy"),
        ("Released", "error"),
        ("Failed", "error"),
        ("Pending", "warning"),
        (None, "unknown"),
    ],
)
def test_persistent_volume_health_classification(phase, expected) -> None:
    status = SimpleNamespace(phase=phase)
    item = SimpleNamespace(status=status)
    assert _health_status(item, "PersistentVolume") == expected


def test_types_without_health_signal_are_unknown() -> None:
    assert _health_status(SimpleNamespace(status=None), "Service") == "unknown"
    assert _health_status(SimpleNamespace(status=None), "StorageClass") == "unknown"
    assert _health_status(SimpleNamespace(status=None), "ClusterRole") == "unknown"


def test_resource_summary_exposes_health() -> None:
    class FakeApps:
        def list_namespaced_deployment(self, namespace: str):
            return SimpleNamespace(
                items=[
                    SimpleNamespace(
                        metadata=SimpleNamespace(namespace=namespace, name="web"),
                        spec=SimpleNamespace(replicas=2),
                        status=SimpleNamespace(ready_replicas=2, available_replicas=2, unavailable_replicas=0),
                    )
                ]
            )

    cluster = ClusterClient("test-cluster", object(), FakeApps())
    resource = cluster.resources("deployments", "default")[0]
    assert resource.status == "2"
    assert resource.health == "healthy"


def test_resources_route_returns_health_field(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KUBEPILOT_AUTH_SECRET", "x" * 32)
    monkeypatch.setenv("KUBEPILOT_DATABASE_URL", "sqlite:///:memory:")
    from app.main import create_app

    class HealthClient(ClusterClient):
        def resources(self, resource_type: str, namespace: str | None):
            return [ResourceSummary("test-cluster", namespace, "Deployment", "web", "2", "healthy")]

    app = create_app()
    app.dependency_overrides[get_current_actor] = lambda: AuthenticatedActor("ops", "admin")
    app.dependency_overrides[get_cluster_client] = lambda: HealthClient("test", object(), object())
    with TestClient(app) as client:
        response = client.get("/api/v1/cluster/resources/deployments?namespace=default")
    assert response.status_code == 200
    assert response.json()["items"][0]["health"] == "healthy"
