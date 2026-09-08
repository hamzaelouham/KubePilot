from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select

from app.core.config import Settings
from app.db.session import create_session_factory
from app.models.base import Base
from app.models.entities import AuditAction, ClusterConnection, InstallationJob


@pytest.fixture()
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    database_url = f"sqlite:///{tmp_path / 'kubepilot-marketplace.db'}"
    monkeypatch.setenv("KUBEPILOT_AUTH_SECRET", "x" * 32)
    monkeypatch.setenv("KUBEPILOT_DATABASE_URL", database_url)
    monkeypatch.setenv("KUBEPILOT_ADMIN_EMAIL", "ops@kubepilot.io")
    monkeypatch.setenv("KUBEPILOT_ADMIN_PASSWORD", "kubepilot")
    monkeypatch.setenv("KUBEPILOT_CLUSTER_NAME", "primary")

    from app.main import create_app

    settings = Settings.from_env()
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    app = create_app()
    return SimpleNamespace(settings=settings, client=TestClient(app))


def cookie_header(cookie: str) -> dict[str, str]:
    return {"cookie": f"kubepilot_session={cookie}"}


def login(api: SimpleNamespace, email: str, password: str) -> dict:
    with api.client as client:
        response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def admin_cookie(api: SimpleNamespace) -> str:
    return login(api, api.settings.admin_email, api.settings.admin_password)["cookie"]


UPSTREAM_PACKAGE = {
    "package_id": "340e1923-7f9c-4c5d-9a1e-8c0a1b2c3d4e",
    "name": "redis",
    "normalized_name": "redis",
    "description": "Redis is an in-memory data structure store.",
    "version": "18.0.0",
    "app_version": "7.2.3",
    "logo_image_id": "abcdef123456",
    "stars": 7,
    "deprecated": False,
    "official": False,
    "signed": False,
    "license": "BSD-3-Clause",
    "containers_images": ["bitnami/redis:7.2"],
    "repository": {
        "url": "https://charts.bitnami.com/bitnami",
        "kind": 0,
        "name": "bitnami",
        "display_name": "",
        "organization_name": "bitnami",
        "organization_display_name": "Bitnami",
        "verified_publisher": True,
    },
}


class FakeUpstream:
    def __init__(self, status_code: int = 200, payload: object = None, header_total: str | None = "1"):
        self.status_code = status_code
        self.payload = payload if payload is not None else {"packages": [UPSTREAM_PACKAGE], "facets": []}
        self.headers = {"content-type": "application/json"}
        if header_total is not None:
            self.headers["Pagination-Total-Count"] = header_total

    def json(self):
        return self.payload


@pytest.fixture()
def upstream(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    captured_urls: list[str] = []
    target = {"response": FakeUpstream()}

    def install(response: FakeUpstream) -> None:
        target["response"] = response

    async def fake_fetch(url: str) -> FakeUpstream:
        captured_urls.append(url)
        return target["response"]

    monkeypatch.setattr("app.api.v1.marketplace._fetch_artifact_hub_search", fake_fetch)
    return SimpleNamespace(urls=captured_urls, install=install)


def test_requires_authentication(api: SimpleNamespace) -> None:
    with api.client as client:
        response = client.get("/api/v1/marketplace/packages")
    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


def test_returns_only_whitelisted_fields(api: SimpleNamespace, upstream: SimpleNamespace) -> None:
    with api.client as client:
        response = client.get("/api/v1/marketplace/packages", headers=cookie_header(admin_cookie(api)))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert len(body["packages"]) == 1
    package = body["packages"][0]
    assert package["name"] == "redis"
    assert package["logo_image_id"] == "abcdef123456"
    assert package["repository"]["organization_display_name"] == "Bitnami"
    assert package["repository"]["name"] == "bitnami"
    assert "containers_images" not in package
    assert "verified_publisher" not in package["repository"]
    assert "facets" not in body
    assert set(package.keys()) == {
        "package_id",
        "name",
        "normalized_name",
        "description",
        "version",
        "app_version",
        "logo_image_id",
        "stars",
        "deprecated",
        "official",
        "signed",
        "license",
        "repository",
    }


def test_pins_kind_and_deprecated(api: SimpleNamespace, upstream: SimpleNamespace) -> None:
    with api.client as client:
        response = client.get("/api/v1/marketplace/packages", headers=cookie_header(admin_cookie(api)))
    assert response.status_code == 200, response.text
    url = upstream.urls[0]
    assert "kind=0" in url
    assert "deprecated=false" in url
    assert "limit=24" in url
    assert "offset=0" in url


def test_forwards_limit_offset_search_and_sort(api: SimpleNamespace, upstream: SimpleNamespace) -> None:
    with api.client as client:
        response = client.get(
            "/api/v1/marketplace/packages?limit=12&offset=24&ts_query_web=postgresql&sort=stars",
            headers=cookie_header(admin_cookie(api)),
        )
    assert response.status_code == 200, response.text
    url = upstream.urls[0]
    assert "limit=12" in url
    assert "offset=24" in url
    assert "ts_query_web=postgresql" in url
    assert "sort=stars" in url


def test_total_defaults_to_returned_page_without_header(
    api: SimpleNamespace, upstream: SimpleNamespace
) -> None:
    upstream.install(FakeUpstream(header_total=None, payload={"packages": [UPSTREAM_PACKAGE, UPSTREAM_PACKAGE]}))
    with api.client as client:
        response = client.get("/api/v1/marketplace/packages", headers=cookie_header(admin_cookie(api)))
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 2


@pytest.mark.parametrize("query", ["limit=0", "limit=999", "limit=abc", "offset=-1"])
def test_invalid_pagination_rejected(api: SimpleNamespace, upstream: SimpleNamespace, query: str) -> None:
    with api.client as client:
        response = client.get(
            f"/api/v1/marketplace/packages?{query}",
            headers=cookie_header(admin_cookie(api)),
        )
    assert response.status_code == 400, query
    assert response.json()["code"] == "invalid_pagination"


def test_upstream_error_status_maps_to_502(api: SimpleNamespace, upstream: SimpleNamespace) -> None:
    upstream.install(FakeUpstream(status_code=429))
    with api.client as client:
        response = client.get("/api/v1/marketplace/packages", headers=cookie_header(admin_cookie(api)))
    assert response.status_code == 502
    assert response.json()["code"] == "marketplace_upstream_error"


def test_upstream_http_error_maps_to_502(api: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    async def raising_fetch(url: str) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("app.api.v1.marketplace._fetch_artifact_hub_search", raising_fetch)
    with api.client as client:
        response = client.get("/api/v1/marketplace/packages", headers=cookie_header(admin_cookie(api)))
    assert response.status_code == 502
    assert response.json()["code"] == "marketplace_upstream_error"


def test_upstream_unexpected_shape_maps_to_502(api: SimpleNamespace, upstream: SimpleNamespace) -> None:
    upstream.install(FakeUpstream(payload={"unexpected": True}))
    with api.client as client:
        response = client.get("/api/v1/marketplace/packages", headers=cookie_header(admin_cookie(api)))
    assert response.status_code == 502
    assert response.json()["code"] == "marketplace_upstream_error"


UPSTREAM_PACKAGE_DETAIL = {
    "package_id": "340e1923-7f9c-4c5d-9a1e-8c0a1b2c3d4e",
    "name": "redis",
    "normalized_name": "redis",
    "available_versions": [
        {"version": "1.0.0", "ts": 100},
        {"version": "2.0.0", "ts": 200},
        {"version": "1.5.0", "ts": 200},
        {"version": ""},
        {"bad": True},
    ],
}


def test_versions_requires_authentication(api: SimpleNamespace) -> None:
    with api.client as client:
        response = client.get("/api/v1/marketplace/packages/bitnami/redis/versions")
    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


@pytest.mark.parametrize("package_ref", ["Redis", "redis_alpha", "UPPER", "redis%21", "r" * 64])
def test_versions_invalid_package_reference_rejected(
    api: SimpleNamespace, package_ref: str
) -> None:
    with api.client as client:
        response = client.get(
            f"/api/v1/marketplace/packages/{package_ref}/redis/versions",
            headers=cookie_header(admin_cookie(api)),
        )
    assert response.status_code == 400, package_ref
    assert response.json()["code"] == "invalid_package_reference"


def test_versions_happy_path(api: SimpleNamespace, upstream: SimpleNamespace) -> None:
    upstream.install(FakeUpstream(payload=UPSTREAM_PACKAGE_DETAIL))
    with api.client as client:
        response = client.get(
            "/api/v1/marketplace/packages/bitnami/redis/versions",
            headers=cookie_header(admin_cookie(api)),
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["package_id"] == "340e1923-7f9c-4c5d-9a1e-8c0a1b2c3d4e"
    assert body["name"] == "redis"
    assert body["repository_name"] == "bitnami"
    assert body["versions"] == ["2.0.0", "1.5.0", "1.0.0"]
    assert upstream.urls[0] == "https://artifacthub.io/api/v1/packages/helm/bitnami/redis"
    assert set(body.keys()) == {"package_id", "name", "repository_name", "versions"}


def test_versions_upstream_404_maps_to_not_found(
    api: SimpleNamespace, upstream: SimpleNamespace
) -> None:
    upstream.install(FakeUpstream(status_code=404, payload={}))
    with api.client as client:
        response = client.get(
            "/api/v1/marketplace/packages/bitnami/redis/versions",
            headers=cookie_header(admin_cookie(api)),
        )
    assert response.status_code == 404
    assert response.json()["code"] == "marketplace_not_found"


def test_versions_upstream_error_maps_to_502(
    api: SimpleNamespace, upstream: SimpleNamespace
) -> None:
    upstream.install(FakeUpstream(status_code=429))
    with api.client as client:
        response = client.get(
            "/api/v1/marketplace/packages/bitnami/redis/versions",
            headers=cookie_header(admin_cookie(api)),
        )
    assert response.status_code == 502
    assert response.json()["code"] == "marketplace_upstream_error"


def test_versions_unexpected_payload_maps_to_502(
    api: SimpleNamespace, upstream: SimpleNamespace
) -> None:
    upstream.install(FakeUpstream(payload={"unexpected": True}))
    with api.client as client:
        response = client.get(
            "/api/v1/marketplace/packages/bitnami/redis/versions",
            headers=cookie_header(admin_cookie(api)),
        )
    assert response.status_code == 502
    assert response.json()["code"] == "marketplace_upstream_error"


class FakeClusterClient:
    def __init__(self, namespaces: list[tuple[str, str]]) -> None:
        self._namespaces = list(namespaces)

    def namespaces(self) -> list[tuple[str, str]]:
        return list(self._namespaces)


@pytest.fixture()
def cluster_client(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    namespaces: list[tuple[str, str]] = [("default", "Active")]
    requests: list[str | None] = []

    def fake_create(*args, **kwargs) -> FakeClusterClient:
        requests.append(kwargs.get("cluster_name"))
        return FakeClusterClient(namespaces)

    monkeypatch.setattr("app.api.v1.marketplace.create_cluster_client", fake_create)
    return SimpleNamespace(namespaces=namespaces, requests=requests)


INSTALL_BODY = {
    "package_id": "340e1923-7f9c-4c5d-9a1e-8c0a1b2c3d4e",
    "package_name": "redis",
    "version": "2.0.0",
    "repository_name": "bitnami",
    "cluster": "primary",
    "namespace": "default",
    "release_name": "my-release",
}

UPSTREAM_INSTALL_DETAIL = {
    "package_id": "340e1923-7f9c-4c5d-9a1e-8c0a1b2c3d4e",
    "name": "redis",
    "available_versions": [
        {"version": "1.0.0", "ts": 100},
        {"version": "2.0.0", "ts": 200},
        {"version": "1.5.0", "ts": 200},
    ],
    "repository": {"name": "bitnami", "url": "https://charts.bitnami.com/bitnami", "kind": 0},
}


def test_install_requires_authentication(api: SimpleNamespace) -> None:
    with api.client as client:
        response = client.post("/api/v1/marketplace/install", json=INSTALL_BODY)
    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


@pytest.mark.parametrize(
    "override",
    [
        {"namespace": "Bad_Namespace"},
        {"release_name": "Bad Name"},
        {"repository_name": "Redis"},
        {"cluster": ""},
        {"package_id": None},
    ],
)
def test_install_invalid_payload_rejected(
    api: SimpleNamespace, cluster_client: SimpleNamespace, upstream: SimpleNamespace, override: dict
) -> None:
    body = {**INSTALL_BODY, **override}
    with api.client as client:
        response = client.post(
            "/api/v1/marketplace/install", json=body, headers=cookie_header(admin_cookie(api))
        )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "validation_error"


def test_install_unknown_cluster_rejected(
    api: SimpleNamespace, cluster_client: SimpleNamespace, upstream: SimpleNamespace
) -> None:
    body = {**INSTALL_BODY, "cluster": "missing"}
    with api.client as client:
        response = client.post(
            "/api/v1/marketplace/install", json=body, headers=cookie_header(admin_cookie(api))
        )
    assert response.status_code == 404
    assert response.json()["code"] == "cluster_not_found"
    assert upstream.urls == []


def test_install_inactive_cluster_rejected(api: SimpleNamespace, upstream: SimpleNamespace) -> None:
    database = create_session_factory(api.settings)()
    try:
        database.add(
            ClusterConnection(
                name="paused", endpoint="https://paused.invalid", kubeconfig_ref="", status="inactive"
            )
        )
        database.commit()
    finally:
        database.close()
    body = {**INSTALL_BODY, "cluster": "paused"}
    with api.client as client:
        response = client.post(
            "/api/v1/marketplace/install", json=body, headers=cookie_header(admin_cookie(api))
        )
    assert response.status_code == 404
    assert response.json()["code"] == "cluster_not_found"


def test_install_namespace_not_found_rejected(
    api: SimpleNamespace, cluster_client: SimpleNamespace, upstream: SimpleNamespace
) -> None:
    body = {**INSTALL_BODY, "namespace": "kube-system"}
    with api.client as client:
        response = client.post(
            "/api/v1/marketplace/install", json=body, headers=cookie_header(admin_cookie(api))
        )
    assert response.status_code == 422
    assert response.json()["code"] == "namespace_not_found"
    assert upstream.urls == []


def test_install_upstream_404_maps_to_not_found(
    api: SimpleNamespace, cluster_client: SimpleNamespace, upstream: SimpleNamespace
) -> None:
    upstream.install(FakeUpstream(status_code=404, payload={}))
    with api.client as client:
        response = client.post(
            "/api/v1/marketplace/install", json=INSTALL_BODY, headers=cookie_header(admin_cookie(api))
        )
    assert response.status_code == 404
    assert response.json()["code"] == "marketplace_not_found"


def test_install_upstream_error_maps_to_502(
    api: SimpleNamespace, cluster_client: SimpleNamespace, upstream: SimpleNamespace
) -> None:
    upstream.install(FakeUpstream(status_code=429))
    with api.client as client:
        response = client.post(
            "/api/v1/marketplace/install", json=INSTALL_BODY, headers=cookie_header(admin_cookie(api))
        )
    assert response.status_code == 502
    assert response.json()["code"] == "marketplace_upstream_error"


def test_install_version_not_available(
    api: SimpleNamespace, cluster_client: SimpleNamespace, upstream: SimpleNamespace
) -> None:
    upstream.install(FakeUpstream(payload=UPSTREAM_INSTALL_DETAIL))
    body = {**INSTALL_BODY, "version": "9.9.9"}
    with api.client as client:
        response = client.post(
            "/api/v1/marketplace/install", json=body, headers=cookie_header(admin_cookie(api))
        )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "version_not_available"


def test_install_happy_path(
    api: SimpleNamespace, cluster_client: SimpleNamespace, upstream: SimpleNamespace
) -> None:
    upstream.install(FakeUpstream(payload=UPSTREAM_INSTALL_DETAIL))
    with api.client as client:
        response = client.post(
            "/api/v1/marketplace/install", json=INSTALL_BODY, headers=cookie_header(admin_cookie(api))
        )
    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body.keys()) == {"job_id", "status"}
    assert body["status"] == "queued"
    job_id = UUID(body["job_id"])
    assert upstream.urls == ["https://artifacthub.io/api/v1/packages/helm/bitnami/redis"]
    assert cluster_client.requests == ["primary"]

    database = create_session_factory(api.settings)()
    try:
        job = database.get(InstallationJob, job_id)
        assert job is not None
        assert job.status == "queued"
        assert job.package_id == INSTALL_BODY["package_id"]
        assert job.package_name == "redis"
        assert job.chart_name == "redis"
        assert job.chart_repository == "bitnami"
        assert job.chart_version == "2.0.0"
        assert job.namespace == "default"
        assert job.release_name == "my-release"
        assert job.error_message is None
        assert job.started_at is None
        assert job.completed_at is None
        cluster = database.scalar(select(ClusterConnection).where(ClusterConnection.name == "primary"))
        assert job.cluster_id == cluster.id
        audit = database.scalar(
            select(AuditAction).where(AuditAction.resource_id == str(job.id))
        )
        assert audit is not None
        assert audit.action == "marketplace.install_queued"
    finally:
        database.close()