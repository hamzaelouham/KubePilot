import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.core.dependencies import AuthenticatedActor
from app.api.v1 import helm_releases
from app.api.v1.helm_release_schemas import HelmReleaseActionRequest, HelmReleaseUpgradeRequest
from app.jobs import worker
from app.kubernetes import helm
from app.kubernetes.helm import HelmError
from app.models.base import Base
from app.models.entities import AuditAction, ClusterConnection, HelmRepository, InstallationJob


def release(**values):
    defaults = {
        "name": "payments",
        "namespace": "production",
        "status": "deployed",
        "revision": 3,
        "chart": "payments-1.4.0",
        "app_version": "2.2.0",
        "updated": "2026-09-12 10:00:00",
        "description": "Ready",
    }
    return helm.HelmReleaseRecord(**(defaults | values))


@pytest.fixture()
def database(tmp_path):
    settings = Settings("x" * 32, f"sqlite:///{tmp_path / 'helm.db'}", worker_enabled=False)
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as session:
        cluster = ClusterConnection(
            name="production", endpoint="https://cluster.invalid", kubeconfig_ref="prod",
            kubeconfig_content="secret kubeconfig", status="active",
        )
        session.add(cluster)
        session.commit()
        yield SimpleNamespace(settings=settings, factory=factory, cluster=cluster)
    engine.dispose()


def test_adapter_whitelists_release_fields_and_uses_fixed_kubeconfig(monkeypatch):
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout=json.dumps([
            {"name": "ok", "namespace": "default", "revision": "2", "status": "deployed", "secret": "nope"},
            {"name": "missing namespace", "secret": "ignored"},
        ]), stderr="secret output")

    monkeypatch.setattr(helm.subprocess, "run", run)
    settings = Settings("x" * 32, "sqlite://", helm_install_timeout_seconds=7)
    cluster = SimpleNamespace(kubeconfig_content="token: private")
    records = helm.list_releases(settings, cluster)

    assert records[0].name == "ok"
    assert records[0].revision == 2
    assert len(records) == 1
    assert calls[0][0][:4] == ["helm", "list", "--all-namespaces", "--output"]
    assert calls[0][0][-2:] == ["--kubeconfig", calls[0][0][-1]]
    assert calls[0][1].get("shell", False) is False


@pytest.mark.parametrize("payload", [{"items": []}, "not-json"])
def test_adapter_rejects_invalid_inventory(monkeypatch, payload):
    def run(command, **kwargs):
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="unsafe")

    monkeypatch.setattr(helm.subprocess, "run", run)
    with pytest.raises(helm.HelmError) as caught:
        helm.list_releases(Settings("x" * 32, "sqlite://"), SimpleNamespace(kubeconfig_content=None))
    assert caught.value.code == "helm_error"
    assert "unsafe" not in str(caught.value)


def test_adapter_resolves_explicit_chart_source(monkeypatch):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="name: payments\nversion: 2.0.0\n", stderr="")

    monkeypatch.setattr(helm.subprocess, "run", run)
    helm.resolve_chart_source(
        Settings("x" * 32, "sqlite://", helm_install_timeout_seconds=7),
        "global-charts", "https://charts.example.test", "payments", "2.0.0",
    )

    assert calls == [
        ["helm", "repo", "add", "global-charts", "https://charts.example.test", "--force-update"],
        ["helm", "repo", "update", "global-charts"],
        ["helm", "show", "chart", "global-charts/payments", "--version", "2.0.0"],
    ]
    assert all(call for call in calls)


def test_external_release_job_uses_worker_and_distinct_audit(database, monkeypatch):
    with database.factory() as session:
        job = InstallationJob(
            package_id=None, package_name="payments", chart_name="payments",
            chart_repository=None, chart_repository_url=None, chart_version="1.4.0",
            cluster_id=database.cluster.id, namespace="production", release_name="payments",
            action="rollback", status="queued", revision=3,
            created_at=datetime.now(timezone.utc),
        )
        session.add(job)
        session.commit()
        job_id = job.id
    monkeypatch.setattr(worker, "_run_single_command", lambda command, timeout: "rollback complete")
    with database.factory() as session:
        worker.run_pending_installations(session, database.settings)
    with database.factory() as session:
        job = session.get(InstallationJob, job_id)
        assert job.status == "succeeded"
        audit = session.scalar(select(AuditAction).where(AuditAction.resource_id == str(job_id)))
        assert audit.action == "helm.release_rollback_succeeded"


def request_for(query: str):
    from starlette.requests import Request

    return Request({
        "type": "http", "method": "POST", "path": "/api/v1/cluster/helm/releases/payments/rollback",
        "query_string": query.encode(), "headers": [], "scheme": "http", "server": ("test", 80),
        "client": ("test", 1), "root_path": "",
    })


def test_queue_action_revalidates_target_confirmation_and_conflict(database, monkeypatch):
    monkeypatch.setattr(helm_releases, "list_releases", lambda settings, cluster: [release()])
    actor = AuthenticatedActor("helm@example.test", "admin")
    with database.factory() as session:
        queued = helm_releases._queue_action(
            "uninstall", "payments", request_for("cluster=production&namespace=production"),
            HelmReleaseActionRequest(confirm_name="payments"), actor, session, database.settings,
        )
        assert queued.status == "queued"
        stored = session.get(InstallationJob, queued.job_id)
        assert stored.package_id is None
        with pytest.raises(HTTPException) as caught:
            helm_releases._queue_action(
                "rollback", "payments", request_for("cluster=production&namespace=production"),
                HelmReleaseActionRequest(confirm_name="payments"), actor, session, database.settings,
            )
        assert caught.value.status_code == 409


def test_queue_action_rejects_wrong_confirmation_before_helm(database, monkeypatch):
    called = []
    monkeypatch.setattr(helm_releases, "list_releases", lambda settings, cluster: called.append(True) or [release()])
    actor = AuthenticatedActor("helm@example.test", "admin")
    with database.factory() as session:
        with pytest.raises(HTTPException) as caught:
            helm_releases._queue_action(
                "rollback", "payments", request_for("cluster=production&namespace=production"),
                HelmReleaseActionRequest(confirm_name="other"), actor, session, database.settings,
            )
        assert getattr(caught.value, "status_code", None) == 422
        assert called == []


def test_queue_upgrade_resolves_global_source_and_snapshots_job(database, monkeypatch):
    with database.factory() as session:
        repository = HelmRepository(name="global-charts", url="https://charts.example.test")
        session.add(repository)
        session.commit()
        repository_id = repository.id

    monkeypatch.setattr(helm_releases, "list_releases", lambda settings, cluster: [release()])
    resolved = []
    monkeypatch.setattr(
        helm_releases,
        "resolve_chart_source",
        lambda settings, name, url, chart, version: resolved.append((name, url, chart, version)),
    )
    actor = AuthenticatedActor("helm@example.test", "admin")
    with database.factory() as session:
        queued = helm_releases._queue_upgrade(
            "payments", request_for("cluster=production&namespace=production"),
            HelmReleaseUpgradeRequest(
                repository_id=repository_id, chart_name="payments", version="2.0.0", confirm_name="payments"
            ), actor, session, database.settings,
        )
        stored = session.get(InstallationJob, queued.job_id)
        assert stored.package_id is None
        assert stored.action == "upgrade"
        assert stored.chart_repository == "global-charts"
        assert stored.chart_repository_url == "https://charts.example.test"
        assert stored.chart_name == "payments"
        assert stored.chart_version == "2.0.0"
        audit = session.scalar(select(AuditAction).where(AuditAction.resource_id == "production/production/payments"))
        assert audit.action == "helm.release_upgrade_queued"
        assert json.loads(audit.context)["version"] == "2.0.0"
    assert resolved == [("global-charts", "https://charts.example.test", "payments", "2.0.0")]


def test_queue_upgrade_does_not_create_job_when_source_resolution_fails(database, monkeypatch):
    with database.factory() as session:
        repository = HelmRepository(name="global-charts", url="https://charts.example.test")
        session.add(repository)
        session.commit()
        repository_id = repository.id
        before = session.scalar(select(InstallationJob))

    monkeypatch.setattr(helm_releases, "list_releases", lambda settings, cluster: [release()])
    monkeypatch.setattr(
        helm_releases,
        "resolve_chart_source",
        lambda *args: (_ for _ in ()).throw(HelmError("chart_source_unavailable", "source unavailable")),
    )
    with database.factory() as session:
        with pytest.raises(HTTPException) as caught:
            helm_releases._queue_upgrade(
                "payments", request_for("cluster=production&namespace=production"),
                HelmReleaseUpgradeRequest(
                    repository_id=repository_id, chart_name="payments", version="2.0.0", confirm_name="payments"
                ), AuthenticatedActor("helm@example.test", "admin"), session, database.settings,
            )
        assert caught.value.status_code == 503
        assert session.scalar(select(InstallationJob)) is before
