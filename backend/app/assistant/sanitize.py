"""Output minimization first; text scrubbing is defense in depth, not a secret detector."""
import re
from typing import Any

SENSITIVE = re.compile(r"password|token|secret|credential|kubeconfig|authorization|cookie|private.?key|client.?key|certificate|^data$|^string_data$|^env$|^annotations$", re.I)


def safe_text(value: str, limit: int = 2000) -> str:
    value = re.sub(r"-----BEGIN [^-]+-----.*?-----END [^-]+-----", "[REDACTED PEM]", value, flags=re.S)
    value = re.sub(r"(?i)(bearer\s+)\S+", r"\1[REDACTED]", value)
    value = re.sub(r"(?i)((?:password|passwd|pwd|token|secret|api[_-]?key|authorization|cookie|credential)[\w-]*[\s\"']*[:=][\s\"']*)[^\s,;\"']+", r"\1[REDACTED]", value)
    value = re.sub(r"(https?://)[^/\s:@]+:[^/\s@]+@", r"\1[REDACTED]@", value)
    value = re.sub(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "[REDACTED JWT]", value)
    value = re.sub(r"\b[A-Za-z0-9_+/=-]{40,}\b", "[REDACTED LONG VALUE]", value)
    return value[:limit]


def sanitize(value: Any, depth: int = 0) -> Any:
    if depth > 12:
        return "[depth limit]"
    if isinstance(value, dict):
        return {key: sanitize(item, depth + 1) for key, item in value.items() if not SENSITIVE.search(str(key))}
    if isinstance(value, list):
        return [sanitize(item, depth + 1) for item in value[:100]]
    if isinstance(value, str):
        return safe_text(value)
    return value if value is None or isinstance(value, (int, float, bool)) else str(value)[:100]


def diagnostic_projection(raw: dict, resource_type: str) -> dict:
    """Never serialize an entire Kubernetes spec or arbitrary metadata to the LLM."""
    metadata, spec, status = (raw.get(key) or {} for key in ("metadata", "spec", "status"))
    result = {key: metadata.get(key) for key in ("name", "namespace", "uid", "resource_version", "creation_timestamp", "owner_references")}
    result["resource_type"] = resource_type
    if resource_type in {"secrets", "configmaps"}:
        result["notice"] = "Metadata only. Configuration and Secret contents are never exposed."
        return sanitize(result)
    # No selectors, annotations, environment, command args, probe HTTP headers or volume credentials.
    status_fields = ("phase", "replicas", "ready_replicas", "available_replicas", "unavailable_replicas", "updated_replicas", "desired_number_scheduled", "number_ready", "active", "succeeded", "failed", "conditions", "capacity")
    result["status"] = {key: status[key] for key in status_fields if key in status}
    result["spec"] = {key: spec[key] for key in ("replicas", "node_name", "storage_class_name", "volume_name", "access_modes") if key in spec}
    result["containers"] = []
    for key in ("init_container_statuses", "container_statuses"):
        for container in status.get(key) or []:
            result["containers"].append({field: container.get(field) for field in ("name", "ready", "restart_count", "state", "last_state")})
    return sanitize(result)
