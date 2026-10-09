import base64
import importlib.util
import subprocess
from pathlib import Path

from cryptography.fernet import Fernet
import pytest

from app.core.config import ConfigurationError, Settings


@pytest.fixture
def production(monkeypatch):
    monkeypatch.setenv("KUBEPILOT_LOCAL_DEVELOPMENT", "false")
    monkeypatch.setenv("KUBEPILOT_AUTH_SECRET", "0123456789abcdef" * 4)
    monkeypatch.setenv("KUBEPILOT_ADMIN_PASSWORD", "unique-admin-password")
    monkeypatch.setenv("KUBEPILOT_DATABASE_URL", "postgresql+psycopg://user:unique-database-password@db/app")


def test_valid_production_and_explicit_local_bootstrap(production, monkeypatch):
    assert Settings.from_env().admin_password == "unique-admin-password"
    monkeypatch.setenv("KUBEPILOT_ADMIN_PASSWORD", "kubepilot")
    with pytest.raises(ConfigurationError):
        Settings.from_env()
    monkeypatch.setenv("KUBEPILOT_LOCAL_DEVELOPMENT", "true")
    assert Settings.from_env().admin_password == "kubepilot"


@pytest.mark.parametrize("name,value", [
    ("KUBEPILOT_ADMIN_PASSWORD", ""), ("KUBEPILOT_ADMIN_PASSWORD", "kubepilot"),
    ("KUBEPILOT_AUTH_SECRET", "local-minikube-dev-secret-0123456789abcdef"),
    ("KUBEPILOT_DATABASE_URL", "postgresql+psycopg://user:change-me@db/app"),
    ("KUBEPILOT_DATABASE_URL", "postgresql+psycopg://user:change%2Dme@db/app"),
])
def test_production_rejects_defaults(production, monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ConfigurationError):
        Settings.from_env()


@pytest.fixture
def secret_validator():
    path = Path(__file__).parents[2] / "scripts/validate-deployment-secret.py"
    spec = importlib.util.spec_from_file_location("secret_validator", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate_secret


@pytest.fixture
def deployment_secret():
    return {
        "KUBEPILOT_AUTH_SECRET": "0123456789abcdef" * 4,
        "KUBEPILOT_ADMIN_PASSWORD": "unique-admin-password",
        "KUBEPILOT_DATABASE_URL": "postgresql+psycopg://user:unique-database-password@db/app",
        "POSTGRES_USER": "user",
        "POSTGRES_PASSWORD": "unique-database-password",
        "POSTGRES_DB": "app",
        "KUBEPILOT_ENCRYPTION_KEY": Fernet.generate_key().decode(),
    }


def secret_document(values):
    return {"data": {k: base64.b64encode(v.encode()).decode() for k, v in values.items()}}


def test_deployment_validator_rejects_placeholder_secrets(production, secret_validator, deployment_secret):
    secret_validator(secret_document(deployment_secret))
    deployment_secret["POSTGRES_PASSWORD"] = "change-me"
    with pytest.raises(ConfigurationError):
        secret_validator(secret_document(deployment_secret))


def test_local_secret_is_ignored_and_not_tracked():
    root = Path(__file__).parents[2]
    path = "backend/deploy/kubernetes/secret.yaml"
    tracked = subprocess.run(["git", "ls-files", "--", path], cwd=root, capture_output=True, text=True, check=True)
    assert not tracked.stdout.strip(), "Deployment Secret must not be tracked by Git"
    subprocess.run(["git", "check-ignore", "--no-index", "--quiet", path], cwd=root, check=True)


def test_complete_deployment_secret_matches_manifest_contract(production, secret_validator, deployment_secret):
    import yaml
    manifest_dir = Path(__file__).parents[1] / "deploy/kubernetes"
    required = set()
    for name in ("postgres.yaml", "backend.yaml", "frontend.yaml"):
        for document in yaml.safe_load_all((manifest_dir / name).read_text()):
            if document["kind"] != "Deployment":
                continue
            for container in document["spec"]["template"]["spec"]["containers"]:
                for variable in container.get("env", []):
                    reference = variable.get("valueFrom", {}).get("secretKeyRef")
                    if reference and not reference.get("optional", False):
                        required.add(reference["key"])
    assert set(deployment_secret) == required
    secret_validator(secret_document(deployment_secret))


@pytest.mark.parametrize("key", ["POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "KUBEPILOT_DATABASE_URL", "KUBEPILOT_AUTH_SECRET", "KUBEPILOT_ADMIN_PASSWORD", "KUBEPILOT_ENCRYPTION_KEY"])
@pytest.mark.parametrize("value", [None, "", " \t\n"])
def test_deployment_secret_rejects_missing_or_blank_keys(production, secret_validator, deployment_secret, key, value):
    if value is None:
        deployment_secret.pop(key)
    else:
        deployment_secret[key] = value
    with pytest.raises(ConfigurationError, match="incomplete"):
        secret_validator(secret_document(deployment_secret))


@pytest.mark.parametrize("key", ["POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"])
def test_deployment_secret_rejects_database_mismatches(production, secret_validator, deployment_secret, key):
    deployment_secret[key] = "different-field-value"
    with pytest.raises(ConfigurationError, match="must match"):
        secret_validator(secret_document(deployment_secret))


def test_deployment_secret_accepts_url_encoded_matching_fields(production, secret_validator, deployment_secret):
    from urllib.parse import quote
    deployment_secret.update(POSTGRES_USER="user@example", POSTGRES_PASSWORD="unique/password:@value", POSTGRES_DB="app data")
    deployment_secret["KUBEPILOT_DATABASE_URL"] = "postgresql+psycopg://{}:{}@db/{}".format(
        *(quote(deployment_secret[key], safe="") for key in ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"))
    )
    secret_validator(secret_document(deployment_secret))
