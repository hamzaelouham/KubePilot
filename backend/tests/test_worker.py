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


@pytest.mark.parametrize(
    "overrides, expected_field",
    [
        ({"release_name": "Bad Name"}, "release_name"),
        ({"chart_name": "Bad_Chart"}, "chart_name"),
        ({"chart_repository": "Repo"}, "chart_repository"),
        ({"namespace": "Default"}, "namespace"),
        ({"chart_repository_url": "file:///etc/passwd"}, "chart_repository_url"),
        ({"chart_repository_url": "ftp://charts.example.com"}, "chart_repository_url"),
    ],
)
def test_invalid_job_fields_fail_without_helm(
    api: SimpleNamespace,
    seed: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    overrides: dict,
    expected_field: str,
) -> None:
    job_id = _add_job(api, seed.cluster, **overrides)
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
    finally:
        database.close()
    assert job.status == "failed"
    assert expected_field in job.error_message
    assert "refusing to run helm" in job.error_message


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


def _capture_helm_call(
    monkeypatch: pytest.MonkeyPatch, calls: list[tuple]
) -> None:
    def fake_run(command: list[str], timeout: int) -> str:
        calls.append((command, timeout))
        return f"helm {command[1]} complete"
    monkeypatch.setattr(worker, "_run_single_command", fake_run)


def test_rollback_success_records_audit(
    api: SimpleNamespace, seed: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple] = []
    _capture_helm_call(monkeypatch, calls)
    job_id = _add_job(api, seed.cluster, action="rollback")
    database = create_session_factory(api.settings)()
    try:
        run_pending_installations(database, api.settings)
    finally:
        database.close()

    assert len(calls) == 1
    command, timeout = calls[0]
    assert command[0] == "helm"
    assert command[:6] == ["helm", "rollback", "my-release", "--namespace", "default", "--wait"]
    assert command[6] == "--timeout"
    assert command[7] == f"{api.settings.helm_install_timeout_seconds}s"
    assert timeout == api.settings.helm_install_timeout_seconds
    assert "--kubeconfig" in command
    kubeconfig = command[command.index("--kubeconfig") + 1]
    assert os.path.exists(kubeconfig) is False

    database = create_session_factory(api.settings)()
    try:
        job = database.get(InstallationJob, job_id)
        assert job.status == "succeeded"
        assert job.completed_at is not None
        audit = database.scalar(select(AuditAction).where(AuditAction.resource_id == str(job.id)))
        assert audit is not None
        assert audit.action == "marketplace.rollback_succeeded"
        assert audit.actor_id is None
        assert audit.result == "success"
    finally:
        database.close()


def test_uninstall_success_records_audit(
    api: SimpleNamespace, seed: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple] = []
    _capture_helm_call(monkeypatch, calls)
    job_id = _add_job(api, seed.cluster, action="uninstall")
    database = create_session_factory(api.settings)()
    try:
        run_pending_installations(database, api.settings)
    finally:
        database.close()

    assert len(calls) == 1
    command, timeout = calls[0]
    assert command[0] == "helm"
    assert command[:4] == ["helm", "uninstall", "my-release", "--namespace"]
    assert command[4] == "default"
    assert "--wait" not in command
    assert timeout == api.settings.helm_install_timeout_seconds
    assert "--kubeconfig" in command
    kubeconfig = command[command.index("--kubeconfig") + 1]
    assert os.path.exists(kubeconfig) is False

    database = create_session_factory(api.settings)()
    try:
        job = database.get(InstallationJob, job_id)
        assert job.status == "succeeded"
        audit = database.scalar(select(AuditAction).where(AuditAction.resource_id == str(job.id)))
        assert audit.action == "marketplace.uninstall_succeeded"
        assert audit.result == "success"
    finally:
        database.close()


def test_rollback_failure_records_audit(
    api: SimpleNamespace, seed: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run(command: list[str], timeout: int) -> str:
        raise HelmInstallError("release: not found")
    monkeypatch.setattr(worker, "_run_single_command", fake_run)
    job_id = _add_job(api, seed.cluster, action="rollback")
    database = create_session_factory(api.settings)()
    try:
        run_pending_installations(database, api.settings)
    finally:
        database.close()

    database = create_session_factory(api.settings)()
    try:
        job = database.get(InstallationJob, job_id)
        assert job.status == "failed"
        assert "release: not found" in job.error_message
        audit = database.scalar(select(AuditAction).where(AuditAction.resource_id == str(job.id)))
        assert audit.action == "marketplace.rollback_failed"
        assert audit.result == "failure"
    finally:
        database.close()


def test_rollback_invalid_namespace_fails_without_helm(
    api: SimpleNamespace, seed: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    called = []

    def boom(command: list[str], timeout: int) -> str:
        called.append(command)
        raise AssertionError("helm must not run")

    monkeypatch.setattr(worker, "_run_single_command", boom)
    job_id = _add_job(api, seed.cluster, action="rollback", namespace="Bad_Namespace")
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
        assert "invalid job field 'namespace'" in job.error_message
        audit = database.scalar(select(AuditAction).where(AuditAction.resource_id == str(job.id)))
        assert audit.action == "marketplace.rollback_failed"
    finally:
        database.close()


def test_unknown_action_fails_job(
    api: SimpleNamespace, seed: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    called = []

    def boom(command: list[str], timeout: int) -> str:
        called.append(command)
        raise AssertionError("helm must not run")

    monkeypatch.setattr(worker, "_run_single_command", boom)
    job_id = _add_job(api, seed.cluster, action="upgrade")
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
        assert "unknown job action 'upgrade'" in job.error_message
        audit = database.scalar(select(AuditAction).where(AuditAction.resource_id == str(job.id)))
        assert audit.action == "marketplace.install_failed"
    finally:
        database.close()