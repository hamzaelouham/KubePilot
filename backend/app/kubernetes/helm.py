"""Small, allowlisted Helm adapter used by the live release API."""

import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from app.core.config import Settings

_CAP = 4096
_DNS_LABEL = re.compile(r"^[a-z0-9](?:[-a-z0-9]{0,61}[a-z0-9])?$")
_VERSION = re.compile(r"^[^\s\x00-\x1f\x7f]{1,64}$")


class HelmError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class HelmReleaseRecord:
    name: str
    namespace: str
    status: str | None
    revision: int | None
    chart: str | None
    app_version: str | None
    updated: str | None
    description: str | None


@dataclass(frozen=True)
class HelmHistoryRecord:
    revision: int
    updated: str | None
    status: str | None
    chart: str | None
    app_version: str | None
    description: str | None


def validate_target_name(value: str, label: str) -> str:
    if not value or len(value) > 253 or not _DNS_LABEL.fullmatch(value):
        raise ValueError(f"Invalid {label}.")
    return value


def validate_chart_version(value: str) -> str:
    if not _VERSION.fullmatch(value):
        raise ValueError("Invalid chart version.")
    return value


def _safe_text(value: Any, limit: int = _CAP) -> str | None:
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:limit] + ("..." if len(text) > limit else "")


def _safe_revision(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        revision = int(value)
    except (TypeError, ValueError):
        return None
    return revision if 0 <= revision <= 2_147_483_647 else None


def _command_error(error: Exception, *, timed_out: bool = False) -> HelmError:
    if timed_out:
        return HelmError("helm_unavailable", "Helm did not respond before the operation timed out.")
    if isinstance(error, OSError):
        return HelmError("helm_unavailable", "The Helm binary is unavailable.")
    return HelmError("helm_error", "Helm could not read the release inventory.")


def _run_json(settings: Settings, args: list[str], kubeconfig_path: str | None) -> Any:
    command = [settings.helm_binary, *args, "--output", "json"]
    if kubeconfig_path:
        command.extend(["--kubeconfig", kubeconfig_path])
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=settings.helm_install_timeout_seconds,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired as error:
        raise _command_error(error, timed_out=True) from error
    except OSError as error:
        raise _command_error(error) from error
    if result.returncode != 0:
        raise _command_error(RuntimeError())
    try:
        return json.loads(result.stdout)
    except (TypeError, ValueError) as error:
        raise HelmError("helm_error", "Helm returned an unreadable release response.") from error


def _run_source_command(settings: Settings, args: list[str]) -> str:
    try:
        result = subprocess.run(
            [settings.helm_binary, *args],
            capture_output=True,
            text=True,
            timeout=settings.helm_install_timeout_seconds,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired as error:
        raise HelmError("chart_source_unavailable", "Helm could not resolve the selected chart source in time.") from error
    except OSError as error:
        raise HelmError("helm_unavailable", "The Helm binary is unavailable.") from error
    if result.returncode != 0:
        raise HelmError("chart_source_unavailable", "The selected chart and version could not be resolved.")
    output = (result.stdout or "").strip()
    if len(output) > _CAP:
        output = output[:_CAP] + "..."
    return output


def resolve_chart_source(
    settings: Settings,
    repository_name: str,
    repository_url: str,
    chart_name: str,
    version: str,
) -> None:
    """Verify an explicit global repository/chart/version before queueing."""
    try:
        validate_target_name(repository_name, "repository name")
        validate_target_name(chart_name, "chart name")
        validate_chart_version(version)
        parsed = urlsplit(repository_url)
        hostname = parsed.hostname
    except (TypeError, ValueError) as error:
        raise HelmError("invalid_chart_source", "The selected chart source is invalid.") from error
    if (
        parsed.scheme not in ("http", "https")
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise HelmError("invalid_chart_source", "The selected chart source is invalid.")

    _run_source_command(settings, ["repo", "add", repository_name, repository_url, "--force-update"])
    _run_source_command(settings, ["repo", "update", repository_name])
    chart = f"{repository_name}/{chart_name}"
    if not _run_source_command(settings, ["show", "chart", chart, "--version", version]):
        raise HelmError("chart_source_unavailable", "The selected chart and version could not be resolved.")


def _kubeconfig(cluster) -> str | None:
    if not cluster.kubeconfig_content:
        return None
    handle = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    try:
        handle.write(cluster.kubeconfig_content)
        handle.close()
        os.chmod(handle.name, 0o600)
        return handle.name
    except Exception:
        handle.close()
        try:
            os.unlink(handle.name)
        except OSError:
            pass
        raise


def _with_cluster(settings: Settings, cluster, args: list[str]) -> Any:
    path = _kubeconfig(cluster)
    try:
        return _run_json(settings, args, path)
    finally:
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass


def _record(raw: Any) -> HelmReleaseRecord | None:
    if not isinstance(raw, dict):
        return None
    name = _safe_text(raw.get("name"), 253)
    namespace = _safe_text(raw.get("namespace"), 253)
    if not name or not namespace:
        return None
    return HelmReleaseRecord(
        name=name,
        namespace=namespace,
        status=_safe_text(raw.get("status")),
        revision=_safe_revision(raw.get("revision")),
        chart=_safe_text(raw.get("chart")),
        app_version=_safe_text(raw.get("app_version")),
        updated=_safe_text(raw.get("updated")),
        description=_safe_text(raw.get("description")),
    )


def list_releases(settings: Settings, cluster) -> list[HelmReleaseRecord]:
    payload = _with_cluster(settings, cluster, ["list", "--all-namespaces"])
    if not isinstance(payload, list):
        raise HelmError("helm_error", "Helm returned an invalid release inventory.")
    return [record for item in payload if (record := _record(item)) is not None]


def history(settings: Settings, cluster, release_name: str, namespace: str) -> list[HelmHistoryRecord]:
    payload = _with_cluster(settings, cluster, ["history", release_name, "--namespace", namespace])
    if not isinstance(payload, list):
        raise HelmError("helm_error", "Helm returned an invalid release history.")
    records: list[HelmHistoryRecord] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        revision = _safe_revision(item.get("revision"))
        if revision is None:
            continue
        records.append(HelmHistoryRecord(
            revision=revision,
            updated=_safe_text(item.get("updated")),
            status=_safe_text(item.get("status")),
            chart=_safe_text(item.get("chart")),
            app_version=_safe_text(item.get("app_version")),
            description=_safe_text(item.get("description")),
        ))
    return records
