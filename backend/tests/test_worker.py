import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select

from app.core.config import Settings
from app.db.session import create_session_factory
from app.jobs import worker
from app.jobs.worker import (
    HelmInstallError,
    claim_next_job,
    requeue_running_jobs,
    run_pending_installations,
)
from app.models.base import Base
from app.models.entities import AuditAction, ClusterConnection, InstallationJob

os.environ.setdefault("KUBEPILOT_WORKER_ENABLED", "false")

CLUSTER = {
    "name": "worker-cluster",
    "endpoint": "https://worker.invalid",
    "kubeconfig_ref": "kubeconfig",
    "status": "active",
    "kubeconfig_content": "apiVersion: v1\nkind: Config\n",
}

JOB_KWARGS = {
    "package_id": "340e1923-7f9c-4c5d-9a1e-8c0a1b2c3d4e",
    "package_name": "redis",
    "chart_name": "redis",
    "chart_repository": "bitnami",
    "chart_repository_url": "https://charts.bitnami.com/bitnami",
    "chart_version": "2.0.0",
    "namespace": "default",
    "release_name": "my-release",
    "status": "queued",
}


@pytest.fixture()
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    database_url = f"sqlite:///{tmp_path / 'kubepilot-worker.db'}"
    monkeypatch.setenv("KUBEPILOT_AUTH_SECRET", "x" * 32)
    monkeypatch.setenv("KUBEPILOT_DATABASE_URL", database_url)
    settings = Settings.from_env()
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    return SimpleNamespace(settings=settings)


@pytest.fixture()
def seed(api: SimpleNamespace) -> SimpleNamespace:
    database = create_session_factory(api.settings)()
    cluster = ClusterConnection(**CLUSTER)
    database.add(cluster)
    database.commit()
    return SimpleNamespace(cluster=cluster.id)


def _add_job(api: SimpleNamespace, cluster_id, **overrides) -> uuid.UUID:
    database = create_session_factory(api.settings)()
    job = InstallationJob(cluster_id=cluster_id, created_at=datetime.now(timezone.utc), **{**JOB_KWARGS, **overrides})
    database.add(job)
    database.commit()
    job_id = job.id
    database.close()
    return job_id


def test_claim_marks_running_and_started(api: SimpleNamespace, seed: SimpleNamespace) -> None:
    job_id = _add_job(api, seed.cluster)
    database = create_session_factory(api.settings)()
    try:
        job = claim_next_job(database)
        assert job is not None
        assert job.status == "running"
        assert job.started_at is not None
        database.commit()
    finally:
        database.close()

    database = create_session_factory(api.settings)()
    try:
        job = database.get(InstallationJob, job_id)
        assert job.status == "running"
        assert job.started_at is not None
        assert claim_next_job(database) is None
    finally:
        database.close()


def test_requeue_running_jobs(api: SimpleNamespace, seed: SimpleNamespace) -> None:
    started = datetime.now(timezone.utc) - timedelta(minutes=2)
    _add_job(api, seed.cluster, status="running", started_at=started)
    database = create_session_factory(api.settings)()
    try:
        requeue_running_jobs(database)
    finally:
        database.close()

    database = create_session_factory(api.settings)()
    try:
        row = database.scalar(select(InstallationJob))
        assert row.status == "queued"
        assert row.started_at is None
    finally:
        database.close()


def test_success_path_records_audit(
    api: SimpleNamespace, seed: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    job_id = _add_job(api, seed.cluster)
    calls: list[tuple] = []

    def fake_helm(settings, job, repository_url, kubeconfig_path):
        calls.append((settings.helm_binary, job.chart_repository, repository_url, job.chart_version, job.release_name, job.namespace, kubeconfig_path))
        return "install complete"

    monkeypatch.setattr(worker, "_run_helm_install", fake_helm)
    database = create_session_factory(api.settings)()
    try:
        run_pending_installations(database, api.settings)
    finally:
        database.close()

    assert len(calls) == 1
    helm_binary, repository, url, version, release, namespace, kubeconfig = calls[0]
    assert helm_binary == "helm"
    assert repository == "bitnami"
    assert url == "https://charts.bitnami.com/bitnami"
    assert version == "2.0.0"
    assert release == "my-release"
    assert namespace == "default"
    assert kubeconfig is not None and os.path.exists(kubeconfig) is False

    database = create_session_factory(api.settings)()
    try:
        job = database.get(InstallationJob, job_id)
        assert job.status == "succeeded"
        assert job.completed_at is not None
        audit = database.scalar(select(AuditAction).where(AuditAction.resource_id == str(job.id)))
        assert audit is not None
        assert audit.action == "marketplace.install_succeeded"
        assert audit.actor_id is None
        assert audit.result == "success"
    finally:
        database.close()


def test_failure_path_records_audit(
    api: SimpleNamespace, seed: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    job_id = _add_job(api, seed.cluster)

    def fake_helm(settings, job, repository_url, kubeconfig_path):
        raise HelmInstallError("release existed")

    monkeypatch.setattr(worker, "_run_helm_install", fake_helm)
    database = create_session_factory(api.settings)()
    try:
        run_pending_installations(database, api.settings)
    finally:
        database.close()

    database = create_session_factory(api.settings)()
    try:
        job = database.get(InstallationJob, job_id)
        assert job.status == "failed"
        assert job.error_message == "release existed"
        assert job.completed_at is not None
        audit = database.scalar(select(AuditAction).where(AuditAction.resource_id == str(job.id)))
        assert audit is not None
        assert audit.action == "marketplace.install_failed"
        assert audit.actor_id is None
        assert audit.result == "failure"
    finally:
        database.close()


def test_missing_repository_url_fails_without_helm(
    api: SimpleNamespace, seed: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    job_id = _add_job(api, seed.cluster, chart_repository_url=None)
    called: list[bool] = []

    def fake_helm(settings, job, repository_url, kubeconfig_path):
        called.append(True)
        return "unreachable"

    monkeypatch.setattr(worker, "_run_helm_install", fake_helm)
    database = create_session_factory(api.settings)()
    try:
        run_pending_installations(database, api.settings)
    finally:
        database.close()

    assert called == []
    database = create_session_factory(api.settings)()
    try:
        job = database.get(InstallationJob, job_id)
        assert job.status == "failed"
        assert "chart repository URL" in job.error_message
    finally:
        database.close()


def test_no_kubeconfig_for_incluster_cluster(
    api: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = create_session_factory(api.settings)()
    cluster = ClusterConnection(
        name="in-cluster",
        endpoint="in-cluster",
        kubeconfig_ref="in-cluster",
        status="active",
        kubeconfig_content=None,
    )
    database.add(cluster)
    database.commit()
    cluster_id = cluster.id
    database.close()

    job_id = _add_job(api, cluster_id)
    calls: list[tuple] = []

    def fake_helm(settings, job, repository_url, kubeconfig_path):
        calls.append(kubeconfig_path)
        return "ok"

    monkeypatch.setattr(worker, "_run_helm_install", fake_helm)
    database = create_session_factory(api.settings)()
    try:
        run_pending_installations(database, api.settings)
    finally:
        database.close()

    assert calls == [None]
    database = create_session_factory(api.settings)()
    try:
        assert database.get(InstallationJob, job_id).status == "succeeded"
    finally:
        database.close()


def test_lifespan_requeues_running_on_boot(
    api: SimpleNamespace, seed: SimpleNamespace
) -> None:
    started = datetime.now(timezone.utc) - timedelta(minutes=1)
    job_id = _add_job(api, seed.cluster, status="running", started_at=started)

    from app.main import create_app

    app = create_app()
    with TestClient(app) as client:
        assert client.get("/api/v1/health").status_code == 200

    database = create_session_factory(api.settings)()
    try:
        job = database.get(InstallationJob, job_id)
        assert job.status == "queued"
        assert job.started_at is None
    finally:
        database.close()


def test_lifespan_worker_on_boots_and_stops(
    api: SimpleNamespace, seed: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KUBEPILOT_WORKER_ENABLED", "true")
    monkeypatch.setenv("KUBEPILOT_WORKER_POLL_SECONDS", "3600")

    from app.main import create_app

    app = create_app()
    with TestClient(app) as client:
        assert client.get("/api/v1/health").status_code == 200

    database = create_session_factory(api.settings)()
    try:
        assert database.scalar(select(InstallationJob)) is None
    finally:
        database.close()