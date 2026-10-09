"""Validate externally provisioned Kubernetes Secret JSON without printing values."""

import base64
import json
import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.core.config import ConfigurationError, Settings


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
    database_url = urlsplit(values["KUBEPILOT_DATABASE_URL"])
    if (
        unquote(database_url.username or "") != values["POSTGRES_USER"]
        or unquote(database_url.password or "") != values["POSTGRES_PASSWORD"]
        or unquote(database_url.path.removeprefix("/")) != values["POSTGRES_DB"]
    ):
        raise ConfigurationError("Database URL must match the PostgreSQL credentials and database")
    os.environ.update({k: v for k, v in values.items() if k.startswith("KUBEPILOT_")})
    os.environ["KUBEPILOT_LOCAL_DEVELOPMENT"] = "false"
    Settings.from_env()


if __name__ == "__main__":
    try:
        validate_secret(json.load(sys.stdin))
    except (ConfigurationError, ValueError, KeyError, TypeError, UnicodeError):
        print("Deployment Secret is missing or unsafe; provision unique credentials and a valid encryption key.", file=sys.stderr)
        sys.exit(1)
