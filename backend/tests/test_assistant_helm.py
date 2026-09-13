from uuid import UUID

import pytest
from sqlalchemy import select

from app.kubernetes.helm import HelmHistoryRecord, HelmReleaseRecord
from app.models.entities import HelmRepository, InstallationJob
from tests.test_assistant import api, decide, proposal


@pytest.fixture
def helm(api, monkeypatch):
    revision = [3]
    monkeypatch.setattr("app.api.v1.helm_releases.list_releases", lambda *args: [HelmReleaseRecord("web", "default", "deployed", revision[0], "web-1.0.0", "1", None, None)])
    monkeypatch.setattr("app.api.v1.helm_releases.history", lambda *args: [HelmHistoryRecord(revision[0], None, "deployed", "web-1.0.0", "1", None)])
    return revision


@pytest.mark.parametrize("action", ["rollback", "uninstall", "upgrade"])
def test_approved_helm_action_queues_existing_job(api, helm, monkeypatch, action):
    fields = {}
    if action == "upgrade":
        with api.db() as db:
            repository = HelmRepository(name="public-charts", url="https://charts.example.test")
            db.add(repository); db.commit()
            fields = {"repository_id": str(repository.id), "chart_name": "web", "version": "2.0.0"}
        monkeypatch.setattr("app.api.v1.helm_releases.resolve_chart_source", lambda *args: None)
    identity = proposal(api, action=action, replicas=None, **fields)
    with api.db() as db:
        assert db.scalar(select(InstallationJob)) is None
    response = decide(api, identity)
    result = response.json()
    assert result["status"] == "submitted", response.text
    assert result["result"]["status"] == "queued"
    with api.db() as db:
        job = db.get(InstallationJob, UUID(result["result"]["job_id"]))
        assert job.action == action and job.namespace == "default" and job.release_name == "web"
    status = api.client.post("/api/v1/assistant/read", json={"tool": "getJobStatus", "cluster": "primary", "name": result["result"]["job_id"]})
    assert status.status_code == 200, status.text
    assert status.json()["result"]["status"] == "queued"


def test_helm_changed_revision_prevents_queueing(api, helm):
    identity = proposal(api, action="rollback", replicas=None)
    helm[0] += 1
    result = decide(api, identity).json()
    assert result["status"] == "failed" and result["result"]["code"] == "stale_target"
    with api.db() as db:
        assert db.scalar(select(InstallationJob)) is None


def test_install_reuses_marketplace_validation_and_job_pipeline(api, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr("app.api.v1.marketplace.create_cluster_client", lambda *args, **kwargs: SimpleNamespace(namespaces=lambda: [("default", "Active")]))
    async def detail(*args):
        return {"package_id": "package-id", "versions": ["1.0.0"], "chart_name": "web", "chart_repository": "public", "chart_repository_url": "https://charts.example.test"}
    monkeypatch.setattr("app.api.v1.marketplace._fetch_package_detail", detail)
    identity = proposal(api, action="install", replicas=None, package_id="package-id", package_name="web", repository_name="public", version="1.0.0")
    response = decide(api, identity)
    assert response.json()["status"] == "submitted", response.text
    assert response.json()["result"]["status"] == "queued"


def test_cluster_list_projection_omits_endpoints_and_kubeconfig(api):
    response = api.client.post("/api/v1/assistant/read", json={"tool": "listClusters", "cluster": "primary"})
    assert response.status_code == 200, response.text
    assert response.json()["result"] == {"items": [{"name": "primary", "status": "active"}]}
