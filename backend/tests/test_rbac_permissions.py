import os
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import AuthenticatedActor, get_cluster_client, get_current_actor
from app.core.rbac import ALL_PERMISSIONS, Permission, Role, ROLE_PERMISSIONS, has_permission

os.environ.setdefault("KUBEPILOT_AUTH_SECRET", "x" * 32)
os.environ.setdefault("KUBEPILOT_DATABASE_URL", "sqlite:///:memory:")


class FakeCluster:
    cluster_name = "test-cluster"

    def namespaces(self):
        return [("default", "Active"), ("kube-system", "Active")]

    def resources(self, resource_type: str, namespace: str | None):
        return [
            SimpleNamespace(
                cluster="test-cluster",
                namespace=namespace or "default",
                kind=resource_type.title(),
                name="sample",
                status="Running",
                health="healthy",
            )
        ]


def _client(role: str, restricted: bool = False) -> TestClient:
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_current_actor] = lambda: AuthenticatedActor(
        "ops@example.com", role, restricted=restricted
    )
    app.dependency_overrides[get_cluster_client] = lambda: FakeCluster()
    return TestClient(app)


@pytest.mark.parametrize(
    ("role", "allowed", "denied"),
    [
        (
            Role.ADMIN,
            set(ALL_PERMISSIONS),
            set(),
        ),
        (
            Role.OPERATOR,
            {
                Permission.CLUSTERS_READ,
                Permission.CLUSTERS_CREATE,
                Permission.CLUSTERS_UPDATE,
                Permission.RESOURCES_READ,
                Permission.RESOURCES_CREATE,
                Permission.RESOURCES_UPDATE,
                Permission.RESOURCES_DELETE,
            },
            {
                Permission.CLUSTERS_DELETE,
                Permission.USERS_READ,
                Permission.USERS_CREATE,
                Permission.USERS_UPDATE,
                Permission.USERS_DELETE,
                Permission.USERS_RESET_PASSWORD,
                Permission.USERS_FORCE_PASSWORD_CHANGE,
            },
        ),
        (
            Role.VIEWER,
            {
                Permission.CLUSTERS_READ,
                Permission.RESOURCES_READ,
            },
            set(ALL_PERMISSIONS)
            - {Permission.CLUSTERS_READ, Permission.RESOURCES_READ},
        ),
    ],
)
def test_role_permission_matrix(role: Role, allowed: set[str], denied: set[str]) -> None:
    assert ROLE_PERMISSIONS[role] == frozenset(allowed)
    for permission in allowed:
        assert has_permission(role.value, permission) is True
    for permission in denied:
        assert has_permission(role.value, permission) is False


def test_unknown_role_grants_no_permissions() -> None:
    assert ROLE_PERMISSIONS.get("root") is None
    assert has_permission("root", Permission.CLUSTERS_READ) is False


@pytest.mark.parametrize("role", ["admin", "operator", "viewer"])
def test_all_roles_can_read_cluster_endpoints(role: str) -> None:
    with _client(role) as client:
        namespaces = client.get("/api/v1/cluster/namespaces")
        resources = client.get("/api/v1/cluster/resources/pods?namespace=default")
    assert namespaces.status_code == 200
    assert namespaces.json()["items"][0]["name"] == "default"
    assert resources.status_code == 200
    assert resources.json()["items"][0]["name"] == "sample"


def test_cluster_read_requires_authentication() -> None:
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_cluster_client] = lambda: FakeCluster()
    with TestClient(app) as client:
        response = client.get("/api/v1/cluster/namespaces")
    assert response.status_code == 401
    assert response.json() == {
        "code": "authentication_required",
        "message": "Authentication is required",
    }


def test_restricted_session_is_blocked_from_cluster_operations() -> None:
    with _client("admin", restricted=True) as client:
        response = client.get("/api/v1/cluster/namespaces")
    assert response.status_code == 403
    assert response.json() == {
        "code": "password_change_required",
        "message": "Password change required before accessing this resource",
    }