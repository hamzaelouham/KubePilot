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
_DNS_1123_PATTERN = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
_ALLOWED_REPOSITORY_SCHEMES = ("http", "https")


def _invalid_job_field(job) -> str | None:
    for field in ("chart_name", "chart_repository", "namespace", "release_name"):
        if not _DNS_1123_PATTERN.fullmatch(getattr(job, field) or ""):
            return field
    if urlsplit(job.chart_repository_url or "").scheme not in _ALLOWED_REPOSITORY_SCHEMES:
        return "chart_repository_url"
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
            completed = subprocess.run(
                command, capture_output=True, text=True, timeout=timeout
            )
        except subprocess.TimeoutExpired:
            raise HelmInstallError(f"helm command timed out after {timeout}s")
        except OSError as error:
            raise HelmInstallError(f"failed to run helm: {error}")
        combined = _trim(
            "\n".join(part for part in (completed.stdout, completed.stderr) if part)
        )
        output_parts.append(combined)
        if completed.returncode != 0:
            message = combined or f"helm exited with code {completed.returncode}"
            raise HelmInstallError(message)
    return "\n".join(part for part in output_parts if part)


def _fail_job(database, job, message: str) -> None:
    database.rollback()
    job.status = "failed"
    job.error_message = _trim(message)
    job.completed_at = datetime.now(timezone.utc)
    database.commit()
    record_audit(
        database,
        AuditEvent.MARKETPLACE_INSTALL_FAILED,
        None,
        "installation_job",
        str(job.id),
        result="failure",
    )
    database.commit()


def _process_claimed_job(database, job, settings: Settings) -> None:
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
        cluster = job.cluster
        if cluster.kubeconfig_content:
            handle = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
            handle.write(cluster.kubeconfig_content)
            handle.close()
            os.chmod(handle.name, 0o600)
            kubeconfig_path = handle.name

        _run_helm_install(settings, job, job.chart_repository_url, kubeconfig_path)
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
        _fail_job(database, job, str(error))
    finally:
        if kubeconfig_path:
            try:
                os.unlink(kubeconfig_path)
            except OSError:
                pass


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