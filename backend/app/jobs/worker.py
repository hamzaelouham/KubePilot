"""Background installation worker for queued Marketplace installs."""

import asyncio
import logging
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from urllib.parse import urlsplit

from sqlalchemy import select, update

from app.core.audit import AuditEvent, record_audit
from app.core.config import Settings
from app.db.session import create_session_factory
from app.models.entities import InstallationJob

logger = logging.getLogger(__name__)

_ERROR_CAP = 4096
_LOG_CAP = 32768
_DNS_1123_PATTERN = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
_ALLOWED_REPOSITORY_SCHEMES = ("http", "https")


_SUCCESS_EVENTS = {
    "install": AuditEvent.MARKETPLACE_INSTALL_SUCCEEDED,
    "rollback": AuditEvent.MARKETPLACE_ROLLBACK_SUCCEEDED,
    "uninstall": AuditEvent.MARKETPLACE_UNINSTALL_SUCCEEDED,
}

_HELM_RELEASE_SUCCESS_EVENTS = {
    "rollback": AuditEvent.HELM_RELEASE_ROLLBACK_SUCCEEDED,
    "uninstall": AuditEvent.HELM_RELEASE_UNINSTALL_SUCCEEDED,
}

_FAILED_EVENTS = {
    "install": AuditEvent.MARKETPLACE_INSTALL_FAILED,
    "rollback": AuditEvent.MARKETPLACE_ROLLBACK_FAILED,
    "uninstall": AuditEvent.MARKETPLACE_UNINSTALL_FAILED,
}

_HELM_RELEASE_FAILED_EVENTS = {
    "rollback": AuditEvent.HELM_RELEASE_ROLLBACK_FAILED,
    "uninstall": AuditEvent.HELM_RELEASE_UNINSTALL_FAILED,
}


def _invalid_job_field(job) -> str | None:
    for field in ("chart_name", "chart_repository", "namespace", "release_name"):
        if not _DNS_1123_PATTERN.fullmatch(getattr(job, field) or ""):
            return field
    if urlsplit(job.chart_repository_url or "").scheme not in _ALLOWED_REPOSITORY_SCHEMES:
        return "chart_repository_url"
    return None


def _invalid_release_target(job) -> str | None:
    for field in ("namespace", "release_name"):
        if not _DNS_1123_PATTERN.fullmatch(getattr(job, field) or ""):
            return field
    return None


class HelmInstallError(RuntimeError):
    """Raised when a helm command fails or times out."""


def _trim(value: str, limit: int = _ERROR_CAP) -> str:
    value = (value or "").strip()
    if len(value) > limit:
        value = value[:limit] + "..."
    return value


def requeue_running_jobs(database) -> None:
    database.execute(
        update(InstallationJob)
        .where(InstallationJob.status == "running")
        .values(status="queued", started_at=None)
    )
    database.commit()


def claim_next_job(database) -> InstallationJob | None:
    row = database.scalar(
        select(InstallationJob)
        .where(InstallationJob.status == "queued")
        .order_by(InstallationJob.created_at, InstallationJob.id)
        .limit(1)
    )
    if row is None:
        return None
    now = datetime.now(timezone.utc)
    result = database.execute(
        update(InstallationJob)
        .where(InstallationJob.id == row.id, InstallationJob.status == "queued")
        .values(status="running", started_at=now)
    )
    if result.rowcount == 0:
        return None
    row.status = "running"
    row.started_at = now
    database.commit()
    return row


def _run_single_command(command: list[str], timeout: int) -> str:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        message = f"helm command timed out after {timeout}s"
        timeout_output = _trim(
            "\n".join(
                part.decode(errors="replace") if isinstance(part, bytes) else (part or "")
                for part in (error.stdout, error.stderr)
            )
        )
        failure = HelmInstallError(message)
        failure.output = timeout_output
        raise failure from error
    except OSError as error:
        failure = HelmInstallError(f"failed to run helm: {error}")
        failure.output = ""
        raise failure from error
    combined = _trim("\n".join(part for part in (completed.stdout, completed.stderr) if part))
    if completed.returncode != 0:
        message = combined or f"helm exited with code {completed.returncode}"
        failure = HelmInstallError(message)
        failure.output = combined
        raise failure
    return combined


def _run_helm_install(settings: Settings, job, repository_url: str, kubeconfig_path: str | None) -> str:
    binary = settings.helm_binary
    timeout = settings.helm_install_timeout_seconds
    seconds = f"{timeout}s"
    commands = [
        [binary, "repo", "add", job.chart_repository, repository_url, "--force-update"],
        [binary, "repo", "update", job.chart_repository],
        [
            binary,
            "install",
            job.release_name,
            f"{job.chart_repository}/{job.chart_name}",
            "--version",
            job.chart_version,
            "--namespace",
            job.namespace,
            "--wait",
            "--timeout",
            seconds,
        ],
    ]
    if kubeconfig_path:
        commands[2] = [*commands[2], "--kubeconfig", kubeconfig_path]

    output_parts: list[str] = []
    for command in commands:
        try:
            output_parts.append(_run_single_command(command, timeout))
        except HelmInstallError as error:
            error.output = "\n".join(part for part in (*output_parts, getattr(error, "output", "")) if part)
            raise
    return "\n".join(part for part in output_parts if part)


def _run_helm_rollback(settings: Settings, job, kubeconfig_path: str | None) -> str:
    timeout = settings.helm_install_timeout_seconds
    command = [
        settings.helm_binary,
        "rollback",
        job.release_name,
        "--namespace",
        job.namespace,
        "--wait",
        "--timeout",
        f"{timeout}s",
    ]
    if kubeconfig_path:
        command.extend(["--kubeconfig", kubeconfig_path])
    return _run_single_command(command, timeout)


def _run_helm_uninstall(settings: Settings, job, kubeconfig_path: str | None) -> str:
    timeout = settings.helm_install_timeout_seconds
    command = [
        settings.helm_binary,
        "uninstall",
        job.release_name,
        "--namespace",
        job.namespace,
    ]
    if kubeconfig_path:
        command.extend(["--kubeconfig", kubeconfig_path])
    return _run_single_command(command, timeout)


def _write_kubeconfig(cluster) -> str | None:
    if not cluster.kubeconfig_content:
        return None
    handle = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    handle.write(cluster.kubeconfig_content)
    handle.close()
    os.chmod(handle.name, 0o600)
    return handle.name


def _unlink_kubeconfig(kubeconfig_path: str | None) -> None:
    if kubeconfig_path:
        try:
            os.unlink(kubeconfig_path)
        except OSError:
            pass


def _fail_job(
    database,
    job,
    message: str,
    event: str = AuditEvent.MARKETPLACE_INSTALL_FAILED,
    log_output: str | None = None,
) -> None:
    database.rollback()
    job.status = "failed"
    job.error_message = _trim(message)
    if log_output:
        job.log_output = _trim(log_output, _LOG_CAP)
    job.completed_at = datetime.now(timezone.utc)
    database.commit()
    record_audit(
        database,
        event,
        None,
        "installation_job",
        str(job.id),
        result="failure",
        context={
            "cluster_id": str(job.cluster_id),
            "cluster": job.cluster.name,
            "namespace": job.namespace,
            "release": job.release_name,
            "action": job.action,
        },
    )
    database.commit()


def _process_install_job(database, job, settings: Settings) -> None:
    if not job.chart_repository_url:
        _fail_job(database, job, "chart repository URL is not set; the job cannot be processed")
        return

    invalid_field = _invalid_job_field(job)
    if invalid_field is not None:
        _fail_job(
            database,
            job,
            f"refusing to run helm: invalid job field '{invalid_field}'",
        )
        return

    kubeconfig_path: str | None = None
    try:
        kubeconfig_path = _write_kubeconfig(job.cluster)

        job.log_output = _trim(
            _run_helm_install(settings, job, job.chart_repository_url, kubeconfig_path),
            _LOG_CAP,
        )
        job.status = "succeeded"
        job.completed_at = datetime.now(timezone.utc)
        database.commit()
        record_audit(
            database,
            AuditEvent.MARKETPLACE_INSTALL_SUCCEEDED,
            None,
            "installation_job",
            str(job.id),
            result="success",
        )
        database.commit()
    except Exception as error:  # noqa: BLE001
        logger.exception("Installation job %s failed: %s", job.id, type(error).__name__)
        _fail_job(database, job, str(error), log_output=getattr(error, "output", None))
    finally:
        _unlink_kubeconfig(kubeconfig_path)


def _process_release_job(database, job, settings: Settings) -> None:
    success_event = (_HELM_RELEASE_SUCCESS_EVENTS if job.package_id is None else _SUCCESS_EVENTS)[job.action]
    failed_event = (_HELM_RELEASE_FAILED_EVENTS if job.package_id is None else _FAILED_EVENTS)[job.action]
    invalid_field = _invalid_release_target(job)
    if invalid_field is not None:
        _fail_job(
            database,
            job,
            f"refusing to run helm: invalid job field '{invalid_field}'",
            failed_event,
        )
        return

    kubeconfig_path: str | None = None
    try:
        kubeconfig_path = _write_kubeconfig(job.cluster)

        if job.action == "rollback":
            job.log_output = _trim(_run_helm_rollback(settings, job, kubeconfig_path), _LOG_CAP)
        else:
            job.log_output = _trim(_run_helm_uninstall(settings, job, kubeconfig_path), _LOG_CAP)
        job.status = "succeeded"
        job.completed_at = datetime.now(timezone.utc)
        database.commit()
        record_audit(
            database,
            success_event,
            None,
            "installation_job",
            str(job.id),
            result="success",
            context={
                "cluster_id": str(job.cluster_id),
                "cluster": job.cluster.name,
                "namespace": job.namespace,
                "release": job.release_name,
                "action": job.action,
            },
        )
        database.commit()
    except Exception as error:  # noqa: BLE001
        logger.exception("Release job %s failed: %s", job.id, type(error).__name__)
        _fail_job(
            database,
            job,
            str(error),
            failed_event,
            getattr(error, "output", None),
        )
    finally:
        _unlink_kubeconfig(kubeconfig_path)


def _process_claimed_job(database, job, settings: Settings) -> None:
    if job.action == "install":
        _process_install_job(database, job, settings)
        return
    if job.action in ("rollback", "uninstall"):
        _process_release_job(database, job, settings)
        return
    _fail_job(database, job, f"unknown job action '{job.action}'")


def run_pending_installations(database, settings: Settings) -> None:
    while True:
        job = claim_next_job(database)
        if job is None:
            return
        _process_claimed_job(database, job, settings)


def _run_cycle(settings: Settings) -> None:
    database = create_session_factory(settings)()
    try:
        run_pending_installations(database, settings)
    finally:
        database.close()


async def _worker_loop(settings: Settings) -> None:
    while True:
        try:
            await asyncio.to_thread(_run_cycle, settings)
        except Exception as error:  # noqa: BLE001
            logger.exception("Installation worker cycle failed: %s", type(error).__name__)
        await asyncio.sleep(settings.worker_poll_seconds)
