"""Validate deployment Secrets and safely apply an optional local manifest."""

import argparse
import base64
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.core.config import ConfigurationError, Settings

SECRET_NAME = "kubepilot-secret"
NAMESPACE = "kubepilot"


def validate_secret(document):
    data = document["data"]
    values = {name: base64.b64decode(value, validate=True).decode() for name, value in data.items()}
    for name in ("KUBEPILOT_AUTH_SECRET", "KUBEPILOT_ADMIN_PASSWORD", "KUBEPILOT_DATABASE_URL", "KUBEPILOT_ENCRYPTION_KEY", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"):
        if not values.get(name, "").strip():
            raise ConfigurationError("Deployment Secret is incomplete")
    key = values["KUBEPILOT_ENCRYPTION_KEY"].encode("ascii")
    decoded = base64.urlsafe_b64decode(key)
    if len(decoded) != 32 or base64.urlsafe_b64encode(decoded) != key:
        raise ConfigurationError("Deployment encryption key is invalid")
    if len(values["POSTGRES_PASSWORD"]) < 10 or values["POSTGRES_PASSWORD"].lower() in {"change-me", "kubepilot", "password"}:
        raise ConfigurationError("Configure a non-default database password")
    try:
        database_url = urlsplit(values["KUBEPILOT_DATABASE_URL"])
        port = database_url.port
        if (
            database_url.scheme != "postgresql+psycopg"
            or database_url.geturl() != values["KUBEPILOT_DATABASE_URL"]
            or database_url.query
            or database_url.fragment
            or database_url.netloc.count("@") != 1
            or not database_url.hostname
            or database_url.netloc.endswith(":")
            or (port is not None and port < 1)
        ):
            raise ValueError
    except ValueError:
        raise ConfigurationError("Deployment database URL requires PostgreSQL with psycopg, a host, a valid port and no query or fragment") from None
    if (
        unquote(database_url.username or "") != values["POSTGRES_USER"]
        or unquote(database_url.password or "") != values["POSTGRES_PASSWORD"]
        # SQLAlchemy decodes credentials, but passes the database name literally.
        or database_url.path.removeprefix("/") != values["POSTGRES_DB"]
    ):
        raise ConfigurationError("Database URL must match the PostgreSQL credentials and database")
    os.environ.update({k: v for k, v in values.items() if k.startswith("KUBEPILOT_")})
    os.environ["KUBEPILOT_LOCAL_DEVELOPMENT"] = "false"
    Settings.from_env()


def prepare_local_secret(document, existing=None):
    for name in ("metadata", "data", "stringData"):
        if not isinstance(document.get(name, {}), dict):
            raise ConfigurationError("Local Secret fields must be mappings")
    metadata = document.get("metadata", {})
    if (
        document.get("apiVersion") != "v1"
        or document.get("kind") != "Secret"
        or metadata.get("name") != SECRET_NAME
        or metadata.get("namespace", NAMESPACE) != NAMESPACE
        or document.get("type", "Opaque") != "Opaque"
    ):
        raise ConfigurationError("Local deployment Secret has the wrong identity")
    data = dict(document.get("data", {}))
    for name, value in document.get("stringData", {}).items():
        if not isinstance(value, str):
            raise ConfigurationError("Secret values must be strings")
        data[name] = base64.b64encode(value.encode()).decode()
    requested_key = os.getenv("KUBEPILOT_ENCRYPTION_KEY", "").strip()
    if requested_key and base64.b64decode(data["KUBEPILOT_ENCRYPTION_KEY"], validate=True).decode() != requested_key:
        raise ConfigurationError("Local Secret differs from the requested encryption key")
    payload = {"apiVersion": "v1", "kind": "Secret", "type": "Opaque", "data": data}
    validate_secret(payload)
    if existing:
        for name in ("KUBEPILOT_ENCRYPTION_KEY", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "KUBEPILOT_DATABASE_URL"):
            if base64.b64decode(existing["data"][name], validate=True) != base64.b64decode(data[name], validate=True):
                raise ConfigurationError("Coordinate credential or encryption-key changes before deployment")
        payload["data"] = {**existing["data"], **data}
    payload["metadata"] = dict(existing["metadata"]) if existing else {}
    payload["metadata"].update(name=SECRET_NAME, namespace=NAMESPACE)
    for name in ("labels", "annotations"):
        if name in metadata:
            if not isinstance(metadata[name], dict):
                raise ConfigurationError("Secret metadata must be mappings")
            payload["metadata"][name] = {**payload["metadata"].get(name, {}), **metadata[name]}
    payload["metadata"].get("annotations", {}).pop("kubectl.kubernetes.io/last-applied-configuration", None)
    return payload


def apply_local_secret(path):
    import yaml

    def kubectl(*arguments, payload=None):
        result = subprocess.run(
            ["minikube", "kubectl", "--", *arguments],
            input=payload, capture_output=True, text=True, timeout=30,
        )
        if result.returncode:
            raise ConfigurationError("Kubernetes Secret operation failed")
        return result.stdout

    try:
        document = yaml.safe_load(Path(path).read_text())
    except yaml.YAMLError:
        raise ConfigurationError("Local Secret YAML is invalid") from None
    if not isinstance(document, dict):
        raise ConfigurationError("Local Secret must contain one object")
    raw = kubectl("get", "secret", SECRET_NAME, "-n", NAMESPACE, "--ignore-not-found", "-o", "json")
    existing = json.loads(raw) if raw.strip() else None
    if existing is None:
        claims = json.loads(kubectl("get", "pvc", "-n", NAMESPACE, "-l", "app=postgres", "-o", "json"))
        if claims["items"]:
            raise ConfigurationError("Existing PostgreSQL storage needs its original credentials")
    payload = prepare_local_secret(document, existing)
    # Replace with the read resourceVersion; concurrent changes fail instead of overwriting.
    kubectl("replace" if existing else "create", "-n", NAMESPACE, "-f", "-", payload=json.dumps(payload))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply-local", metavar="PATH")
    arguments = parser.parse_args()
    try:
        if arguments.apply_local:
            apply_local_secret(arguments.apply_local)
        else:
            validate_secret(json.load(sys.stdin))
    except (ConfigurationError, ValueError, KeyError, TypeError, UnicodeError, OSError, subprocess.TimeoutExpired):
        print("Deployment Secret is missing or unsafe; provision unique credentials and a valid encryption key.", file=sys.stderr)
        sys.exit(1)
