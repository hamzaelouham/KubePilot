import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select

from app.core.config import Settings
from app.db.session import create_session_factory
from app.models.base import Base
from app.models.entities import AuditAction, ClusterConnection, InstallationJob, UserAccount




os.environ.setdefault("KUBEPILOT_WORKER_ENABLED", "false")
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


def _seed_user(
    api: SimpleNamespace, email: str, role: str, restricted: bool = False
) -> str:
    from app.core.passwords import hash_password

    database = create_session_factory(api.settings)()
    try:
        user = UserAccount(
            email=email,
            password_hash=hash_password("correct-horse-00"),
            role=role,
            must_change_password=restricted,
        )
        database.add(user)
        database.commit()
    finally:
        database.close()
    return login(api, email, "correct-horse-00")["cookie"]


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


def test_install_viewer_denied(
    api: SimpleNamespace, cluster_client: SimpleNamespace, upstream: SimpleNamespace
) -> None:
    cookie = _seed_user(api, "viewer@example.com", role="viewer")
    with api.client as client:
        response = client.post(
            "/api/v1/marketplace/install", json=INSTALL_BODY, headers=cookie_header(cookie)
        )
    assert response.status_code == 403
    assert response.json()["code"] == "insufficient_permissions"
    assert upstream.urls == []
    assert cluster_client.requests == []

    database = create_session_factory(api.settings)()
    try:
        count = database.scalar(select(func.count()).select_from(InstallationJob))
    finally:
        database.close()
    assert count == 0


def test_install_restricted_operator_denied(
    api: SimpleNamespace, cluster_client: SimpleNamespace, upstream: SimpleNamespace
) -> None:
    cookie = _seed_user(api, "ops-restricted@example.com", role="operator", restricted=True)
    with api.client as client:
        response = client.post(
            "/api/v1/marketplace/install", json=INSTALL_BODY, headers=cookie_header(cookie)
        )
    assert response.status_code == 403
    assert response.json()["code"] == "password_change_required"
    assert upstream.urls == []


def test_install_operator_allowed(
    api: SimpleNamespace, cluster_client: SimpleNamespace, upstream: SimpleNamespace
) -> None:
    upstream.install(FakeUpstream(payload=UPSTREAM_INSTALL_DETAIL))
    cookie = _seed_user(api, "operator@example.com", role="operator")
    with api.client as client:
        response = client.post(
            "/api/v1/marketplace/install", json=INSTALL_BODY, headers=cookie_header(cookie)
        )
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "queued"
    assert upstream.urls == ["https://artifacthub.io/api/v1/packages/helm/bitnami/redis"]


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
    body = {**INSTALL_BODY, "namespace": "analytics"}
    with api.client as client:
        response = client.post(
            "/api/v1/marketplace/install", json=body, headers=cookie_header(admin_cookie(api))
        )
    assert response.status_code == 422
    assert response.json()["code"] == "namespace_not_found"
    assert upstream.urls == []


def test_install_kube_system_protected(
    api: SimpleNamespace, cluster_client: SimpleNamespace, upstream: SimpleNamespace
) -> None:
    cluster_client.namespaces.append(("kube-system", "Active"))
    body = {**INSTALL_BODY, "namespace": "kube-system"}
    with api.client as client:
        response = client.post(
            "/api/v1/marketplace/install", json=body, headers=cookie_header(admin_cookie(api))
        )
    assert response.status_code == 422
    assert response.json()["code"] == "namespace_protected"
    assert upstream.urls == []


def test_install_package_id_mismatch(
    api: SimpleNamespace, cluster_client: SimpleNamespace, upstream: SimpleNamespace
) -> None:
    payload = {**UPSTREAM_INSTALL_DETAIL, "package_id": "11111111-1111-1111-1111-111111111111"}
    upstream.install(FakeUpstream(payload=payload))
    with api.client as client:
        response = client.post(
            "/api/v1/marketplace/install", json=INSTALL_BODY, headers=cookie_header(admin_cookie(api))
        )
    assert response.status_code == 422
    assert response.json()["code"] == "package_mismatch"


@pytest.mark.parametrize(
    "override",
    [
        {"name": "Bad_Chart"},
        {"repository": {"name": "Bad_Repo", "url": "https://charts.bitnami.com/bitnami", "kind": 0}},
        {"repository": {"name": "bitnami", "url": "file:///etc/passwd", "kind": 0}},
    ],
)
def test_install_untrusted_package_source(
    api: SimpleNamespace,
    cluster_client: SimpleNamespace,
    upstream: SimpleNamespace,
    override: dict,
) -> None:
    payload = {**UPSTREAM_INSTALL_DETAIL, **override}
    upstream.install(FakeUpstream(payload=payload))
    with api.client as client:
        response = client.post(
            "/api/v1/marketplace/install", json=INSTALL_BODY, headers=cookie_header(admin_cookie(api))
        )
    assert response.status_code == 502
    assert response.json()["code"] == "invalid_package_source"


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
        assert job.chart_repository_url == "https://charts.bitnami.com/bitnami"
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


def _seed_installation(
    api: SimpleNamespace,
    status: str = "succeeded",
    error_message: str | None = None,
    log_output: str | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    created_at: datetime | None = None,
) -> UUID:
    database = create_session_factory(api.settings)()
    try:
        cluster = database.scalar(
            select(ClusterConnection).where(ClusterConnection.name == "primary")
        )
        if cluster is None:
            cluster = ClusterConnection(
                name="primary",
                endpoint="https://k8s.example",
                kubeconfig_ref="primary",
                status="active",
            )
            database.add(cluster)
            database.commit()
            database.refresh(cluster)
        job = InstallationJob(
            package_id="340e1923-7f9c-4c5d-9a1e-8c0a1b2c3d4e",
            package_name="redis",
            chart_name="redis",
            chart_repository="bitnami",
            chart_repository_url="https://charts.bitnami.com/bitnami",
            chart_version="2.0.0",
            cluster_id=cluster.id,
            namespace="default",
            release_name="my-release",
            status=status,
            error_message=error_message,
            log_output=log_output,
            started_at=started_at,
            completed_at=completed_at,
            **({"created_at": created_at} if created_at is not None else {}),
        )
        database.add(job)
        database.commit()
        database.refresh(job)
        return job.id
    finally:
        database.close()


def _get_installation_status(
    client: TestClient, job_id: UUID, cookie: str | None = None
) -> httpx.Response:
    headers = cookie_header(cookie) if cookie else {}
    return client.get(f"/api/v1/marketplace/installations/{job_id}", headers=headers)


def test_installation_status_requires_authentication(api: SimpleNamespace) -> None:
    job_id = _seed_installation(api)
    with api.client as client:
        response = _get_installation_status(client, job_id)
    assert response.status_code == 401


def test_installation_status_not_found(api: SimpleNamespace) -> None:
    cookie = admin_cookie(api)
    job_id = UUID("00000000-0000-0000-0000-000000000000")
    with api.client as client:
        response = _get_installation_status(client, job_id, cookie)
    assert response.status_code == 404
    assert response.json()["code"] == "installation_not_found"


def test_installation_logs_require_authentication(api: SimpleNamespace) -> None:
    job_id = _seed_installation(api, log_output="helm install complete")
    with api.client as client:
        response = client.get(f"/api/v1/marketplace/installations/{job_id}/logs")
    assert response.status_code == 401


def test_installation_logs_return_bounded_job_output(api: SimpleNamespace) -> None:
    cookie = admin_cookie(api)
    job_id = _seed_installation(api, log_output="helm install complete\nrelease deployed")
    with api.client as client:
        response = client.get(
            f"/api/v1/marketplace/installations/{job_id}/logs",
            headers=cookie_header(cookie),
        )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "job_id": str(job_id),
        "log_output": "helm install complete\nrelease deployed",
    }


def test_installation_logs_not_found(api: SimpleNamespace) -> None:
    cookie = admin_cookie(api)
    job_id = UUID("00000000-0000-0000-0000-000000000000")
    with api.client as client:
        response = client.get(
            f"/api/v1/marketplace/installations/{job_id}/logs",
            headers=cookie_header(cookie),
        )
    assert response.status_code == 404
    assert response.json()["code"] == "installation_not_found"


def test_installation_status_succeeded(api: SimpleNamespace) -> None:
    cookie = admin_cookie(api)
    started = datetime.now(timezone.utc) - timedelta(minutes=2)
    completed = datetime.now(timezone.utc)
    job_id = _seed_installation(
        api, error_message=None, started_at=started, completed_at=completed
    )
    with api.client as client:
        response = _get_installation_status(client, job_id, cookie)
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body.keys()) == {
        "job_id",
        "package_name",
        "cluster",
        "namespace",
        "release_name",
        "action",
        "status",
        "error_message",
        "created_at",
        "started_at",
        "completed_at",
        "can_manage_release",
    }
    assert body["job_id"] == str(job_id)
    assert body["package_name"] == "redis"
    assert body["cluster"] == "primary"
    assert body["namespace"] == "default"
    assert body["release_name"] == "my-release"
    assert body["status"] == "succeeded"
    assert body["error_message"] is None
    assert datetime.fromisoformat(body["started_at"]).replace(tzinfo=None) == started.replace(tzinfo=None)
    assert datetime.fromisoformat(body["completed_at"]).replace(tzinfo=None) == completed.replace(tzinfo=None)


def test_installation_status_queued(api: SimpleNamespace) -> None:
    cookie = admin_cookie(api)
    job_id = _seed_installation(api, status="queued")
    with api.client as client:
        response = _get_installation_status(client, job_id, cookie)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"
    assert body["error_message"] is None
    assert body["started_at"] is None
    assert body["completed_at"] is None


def test_installation_status_running(api: SimpleNamespace) -> None:
    cookie = admin_cookie(api)
    started = datetime.now(timezone.utc) - timedelta(seconds=30)
    with api.client as client:
        job_id = _seed_installation(api, status="running", started_at=started)
        response = _get_installation_status(client, job_id, cookie)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "running"
    assert datetime.fromisoformat(body["started_at"]).replace(tzinfo=None) == started.replace(tzinfo=None)
    assert body["completed_at"] is None


def test_installation_status_failed(api: SimpleNamespace) -> None:
    cookie = admin_cookie(api)
    started = datetime.now(timezone.utc) - timedelta(minutes=2)
    completed = datetime.now(timezone.utc)
    job_id = _seed_installation(
        api,
        status="failed",
        error_message="helm install failed: release not found",
        started_at=started,
        completed_at=completed,
    )
    with api.client as client:
        response = _get_installation_status(client, job_id, cookie)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["error_message"] == "helm install failed: release not found"
    assert datetime.fromisoformat(body["completed_at"]).replace(tzinfo=None) == completed.replace(tzinfo=None)


def _list_installations(
    client: TestClient, cookie: str | None = None, query: str = ""
) -> httpx.Response:
    headers = cookie_header(cookie) if cookie else {}
    return client.get(f"/api/v1/marketplace/installations{query}", headers=headers)


def test_installation_history_requires_authentication(api: SimpleNamespace) -> None:
    with api.client as client:
        response = _list_installations(client)
    assert response.status_code == 401


def test_installation_history_empty(api: SimpleNamespace) -> None:
    cookie = admin_cookie(api)
    with api.client as client:
        response = _list_installations(client, cookie)
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


def test_installation_history_orders_most_recent_first(api: SimpleNamespace) -> None:
    cookie = admin_cookie(api)
    base = datetime.now(timezone.utc) - timedelta(days=1)
    older = _seed_installation(api, status="succeeded", created_at=base)
    newer = _seed_installation(
        api,
        status="failed",
        created_at=base + timedelta(minutes=5),
    )
    with api.client as client:
        response = _list_installations(client, cookie)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    job_ids = [item["job_id"] for item in body["items"]]
    assert job_ids == [str(newer), str(older)]
    first = body["items"][0]
    assert set(first.keys()) == {
        "job_id",
        "package_name",
        "cluster",
        "namespace",
        "release_name",
        "action",
        "can_manage_release",
        "status",
        "error_message",
        "created_at",
        "started_at",
        "completed_at",
    }
    assert first["package_name"] == "redis"
    assert first["cluster"] == "primary"
    assert first["namespace"] == "default"
    assert first["release_name"] == "my-release"
    assert first["status"] == "failed"
    assert first["error_message"] is None
    assert first["can_manage_release"] is False


def test_installation_history_supports_offset_pagination(api: SimpleNamespace) -> None:
    cookie = admin_cookie(api)
    base = datetime.now(timezone.utc) - timedelta(days=1)
    oldest = _seed_installation(api, created_at=base)
    middle = _seed_installation(api, created_at=base + timedelta(minutes=1))
    _seed_installation(api, created_at=base + timedelta(minutes=2))
    with api.client as client:
        response = _list_installations(client, cookie, "?limit=1&offset=1")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert [item["job_id"] for item in body["items"]] == [str(middle)]
    assert str(oldest) not in [item["job_id"] for item in body["items"]]


def test_installation_history_status_filter(api: SimpleNamespace) -> None:
    cookie = admin_cookie(api)
    _seed_installation(api, status="succeeded")
    _seed_installation(api, status="running")
    with api.client as client:
        response = _list_installations(client, cookie, "?status=succeeded")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [item["status"] for item in body["items"]] == ["succeeded"]


def test_installation_history_invalid_status_filter(api: SimpleNamespace) -> None:
    cookie = admin_cookie(api)
    with api.client as client:
        response = _list_installations(client, cookie, "?status=invalid")
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_status_filter"


def test_installation_history_limit_bounds(api: SimpleNamespace) -> None:
    cookie = admin_cookie(api)
    with api.client as client:
        too_small = _list_installations(client, cookie, "?limit=0")
        too_large = _list_installations(client, cookie, "?limit=201")
    assert too_small.status_code == 422
    assert too_large.status_code == 422


def _post_release_action(
    client: TestClient, endpoint: str, job_id: UUID, cookie: str | None = None
) -> httpx.Response:
    headers = cookie_header(cookie) if cookie else {}
    return client.post(f"/api/v1/marketplace/installations/{job_id}/{endpoint}", headers=headers)


def _job_row(api: SimpleNamespace, job_id: UUID):
    database = create_session_factory(api.settings)()
    try:
        return database.get(InstallationJob, job_id)
    finally:
        database.close()


def test_release_actions_require_authentication(api: SimpleNamespace) -> None:
    job_id = _seed_installation(api)
    with api.client as client:
        rollback = _post_release_action(client, "rollback", job_id)
        uninstall = _post_release_action(client, "uninstall", job_id)
    assert rollback.status_code == 401
    assert uninstall.status_code == 401


def test_release_actions_viewer_denied(api: SimpleNamespace) -> None:
    cookie = _seed_user(api, "viewer@example.com", role="viewer")
    job_id = _seed_installation(api)
    with api.client as client:
        rollback = _post_release_action(client, "rollback", job_id, cookie)
        uninstall = _post_release_action(client, "uninstall", job_id, cookie)
    assert rollback.status_code == 403
    assert rollback.json()["code"] == "insufficient_permissions"
    assert uninstall.status_code == 403
    assert uninstall.json()["code"] == "insufficient_permissions"

    database = create_session_factory(api.settings)()
    try:
        count = database.scalar(select(func.count()).select_from(InstallationJob))
    finally:
        database.close()
    assert count == 1


def test_release_actions_restricted_operator_denied(api: SimpleNamespace) -> None:
    cookie = _seed_user(api, "ops-restricted@example.com", role="operator", restricted=True)
    job_id = _seed_installation(api)
    with api.client as client:
        response = _post_release_action(client, "rollback", job_id, cookie)
    assert response.status_code == 403
    assert response.json()["code"] == "password_change_required"


def test_rollback_unknown_job_rejected(api: SimpleNamespace) -> None:
    cookie = admin_cookie(api)
    job_id = UUID("00000000-0000-0000-0000-000000000000")
    with api.client as client:
        response = _post_release_action(client, "rollback", job_id, cookie)
    assert response.status_code == 404
    assert response.json()["code"] == "installation_not_found"


def test_rollback_non_install_source_rejected(api: SimpleNamespace) -> None:
    cookie = admin_cookie(api)
    source_id = _seed_installation(api, status="succeeded")
    with api.client as client:
        first = _post_release_action(client, "rollback", source_id, cookie)
    assert first.status_code == 201
    rollback_id = UUID(first.json()["job_id"])
    with api.client as client:
        response = _post_release_action(client, "rollback", rollback_id, cookie)
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_source_job"


def test_rollback_uncompleted_install_rejected(api: SimpleNamespace) -> None:
    cookie = admin_cookie(api)
    job_id = _seed_installation(api, status="failed")
    with api.client as client:
        response = _post_release_action(client, "rollback", job_id, cookie)
    assert response.status_code == 422
    assert response.json()["code"] == "install_not_completed"


def test_release_action_conflict_rejected(api: SimpleNamespace) -> None:
    cookie = admin_cookie(api)
    job_id = _seed_installation(api, status="succeeded")
    _seed_installation(api, status="queued")
    with api.client as client:
        response = _post_release_action(client, "uninstall", job_id, cookie)
    assert response.status_code == 409
    assert response.json()["code"] == "release_action_conflict"


def test_release_action_inactive_cluster_rejected(api: SimpleNamespace) -> None:
    cookie = admin_cookie(api)
    job_id = _seed_installation(api)
    database = create_session_factory(api.settings)()
    try:
        source = database.get(InstallationJob, job_id)
        source.cluster.status = "inactive"
        database.commit()
    finally:
        database.close()
    with api.client as client:
        response = _post_release_action(client, "rollback", job_id, cookie)
    assert response.status_code == 404
    assert response.json()["code"] == "cluster_not_found"


def test_rollback_queued_success(api: SimpleNamespace) -> None:
    cookie = admin_cookie(api)
    source_id = _seed_installation(api)
    with api.client as client:
        response = _post_release_action(client, "rollback", source_id, cookie)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "queued"
    action_id = UUID(body["job_id"])
    assert action_id != source_id

    job = _job_row(api, action_id)
    assert job.action == "rollback"
    assert job.cluster_id is not None
    assert job.namespace == "default"
    assert job.release_name == "my-release"
    assert job.package_name == "redis"
    assert job.chart_name == "redis"
    assert job.chart_repository == "bitnami"
    assert job.chart_repository_url is None

    database = create_session_factory(api.settings)()
    try:
        audit = database.scalar(select(AuditAction).where(AuditAction.resource_id == str(action_id)))
        assert audit is not None
        assert audit.action == "marketplace.rollback_queued"
        assert audit.actor_id is not None
        assert audit.result == "success"
    finally:
        database.close()

    with api.client as client:
        status = _get_installation_status(client, action_id, cookie)
    assert status.status_code == 200
    assert status.json()["action"] == "rollback"
    assert status.json()["status"] == "queued"


def test_uninstall_queued_success_operator(api: SimpleNamespace) -> None:
    cookie = _seed_user(api, "ops-operator@example.com", role="operator")
    source_id = _seed_installation(api)
    with api.client as client:
        response = _post_release_action(client, "uninstall", source_id, cookie)
    assert response.status_code == 201, response.text
    action_id = UUID(response.json()["job_id"])

    job = _job_row(api, action_id)
    assert job.action == "uninstall"
    assert job.release_name == "my-release"
    assert job.chart_repository_url is None

    database = create_session_factory(api.settings)()
    try:
        audit = database.scalar(select(AuditAction).where(AuditAction.resource_id == str(action_id)))
        assert audit is not None
        assert audit.action == "marketplace.uninstall_queued"
        assert audit.result == "success"
    finally:
        database.close()


def test_completed_uninstall_disables_release_actions_and_remains_in_history(
    api: SimpleNamespace,
) -> None:
    cookie = admin_cookie(api)
    source_id = _seed_installation(api)
    with api.client as client:
        queued = _post_release_action(client, "uninstall", source_id, cookie)
    assert queued.status_code == 201
    uninstall_id = UUID(queued.json()["job_id"])

    database = create_session_factory(api.settings)()
    try:
        uninstall = database.get(InstallationJob, uninstall_id)
        assert uninstall is not None
        uninstall.status = "succeeded"
        database.commit()
    finally:
        database.close()

    with api.client as client:
        repeated = _post_release_action(client, "uninstall", source_id, cookie)
        history = _list_installations(client, cookie)
    assert repeated.status_code == 422
    assert repeated.json()["code"] == "release_not_active"
    assert history.status_code == 200
    items = {item["job_id"]: item for item in history.json()["items"]}
    assert items[str(source_id)]["can_manage_release"] is False
    assert items[str(uninstall_id)]["action"] == "uninstall"
