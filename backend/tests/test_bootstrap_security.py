import base64
import importlib.util
import json
import os
import shutil
import subprocess
import sys
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
def secret_module():
    path = Path(__file__).parents[2] / "scripts/validate-deployment-secret.py"
    spec = importlib.util.spec_from_file_location("secret_validator", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def secret_validator(secret_module):
    return secret_module.validate_secret


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


@pytest.mark.parametrize("host", ["db", "db:5432", "db:15432", "[::1]:5432"])
@pytest.mark.parametrize("database", ["app", "app data", "app%20data"])
def test_deployment_secret_accepts_url_encoded_matching_fields(production, secret_validator, deployment_secret, host, database):
    from urllib.parse import quote
    from sqlalchemy import create_engine
    deployment_secret.update(POSTGRES_USER="user@example", POSTGRES_PASSWORD="unique/password:@value", POSTGRES_DB=database)
    deployment_secret["KUBEPILOT_DATABASE_URL"] = "postgresql+psycopg://{}:{}@{}/{}".format(
        quote(deployment_secret["POSTGRES_USER"], safe=""),
        quote(deployment_secret["POSTGRES_PASSWORD"], safe=""), host, database)
    secret_validator(secret_document(deployment_secret))
    engine = create_engine(deployment_secret["KUBEPILOT_DATABASE_URL"])
    try:
        args, options = engine.dialect.create_connect_args(engine.url)
        assert not args
        assert options["user"] == deployment_secret["POSTGRES_USER"]
        assert options["password"] == deployment_secret["POSTGRES_PASSWORD"]
        assert options["dbname"] == deployment_secret["POSTGRES_DB"]
    finally:
        engine.dispose()


AMBIGUOUS_DATABASE_URLS = [
    ("postgresql+psycopg://user:unique-database-password@db/app%20data", "app data"),
    *[(f"postgresql+psycopg://user:unique-database-password@db/app?{query}", "app")
      for query in ("password=other-password", "dbname=other_db", "user=other_user", "host=other_db", "port=not-a-port", "sslmode=require")],
    ("postgresql+psycopg://user:unique-database-password@db/app#ignored", "app"),
    (" postgresql+psycopg://user:unique-database-password@db/app", "app"),
    ("POSTGRESQL+PSYCOPG://user:unique-database-password@db/app", "app"),
    ("postgresql+psycopg://user:unique-database-password@other@db/app", "app"),
]


@pytest.mark.parametrize("url,database", AMBIGUOUS_DATABASE_URLS)
def test_deployment_secret_rejects_runtime_url_mismatches(production, secret_validator, deployment_secret, url, database):
    deployment_secret.update(KUBEPILOT_DATABASE_URL=url, POSTGRES_DB=database)
    with pytest.raises(ConfigurationError) as error:
        secret_validator(secret_document(deployment_secret))
    assert url not in str(error.value)


INVALID_DATABASE_ENDPOINTS = [
    ("unsupported+driver", "db"), ("postgresql", "db"), ("postgresql+psycopg2", "db"),
    ("postgresql+psycopg", ""), ("postgresql+psycopg", "db:not-a-port"),
    ("postgresql+psycopg", "db:0"), ("postgresql+psycopg", "db:65536"),
    ("postgresql+psycopg", "db:-1"), ("postgresql+psycopg", "db:"),
]


@pytest.mark.parametrize("scheme,host", INVALID_DATABASE_ENDPOINTS)
def test_deployment_secret_rejects_unusable_database_urls(production, secret_validator, deployment_secret, scheme, host):
    deployment_secret["KUBEPILOT_DATABASE_URL"] = f"{scheme}://user:unique-database-password@{host}/app"
    with pytest.raises(ConfigurationError, match="Deployment database URL") as error:
        secret_validator(secret_document(deployment_secret))
    assert deployment_secret["KUBEPILOT_DATABASE_URL"] not in str(error.value)


@pytest.fixture
def local_secret_document(production, monkeypatch, deployment_secret):
    monkeypatch.delenv("KUBEPILOT_ENCRYPTION_KEY", raising=False)
    return {"apiVersion": "v1", "kind": "Secret", "metadata": {"name": "kubepilot-secret", "namespace": "kubepilot"}, "stringData": deployment_secret.copy()}


def test_local_secret_normalizes_data_and_stringdata(secret_module, local_secret_document, deployment_secret):
    local_secret_document["data"] = secret_document(deployment_secret)["data"]
    local_secret_document["data"]["POSTGRES_PASSWORD"] = "invalid-base64"
    prepared = secret_module.prepare_local_secret(local_secret_document)
    assert prepared["data"] == secret_document(deployment_secret)["data"]
    assert "stringData" not in prepared
    local_secret_document.pop("stringData")
    local_secret_document["data"] = secret_document(deployment_secret)["data"]
    assert secret_module.prepare_local_secret(local_secret_document)["data"] == prepared["data"]


@pytest.mark.parametrize("field,value", [("kind", "ConfigMap"), ("apiVersion", "v2"), ("type", "kubernetes.io/tls"), ("name", "another-secret"), ("namespace", "default"), ("metadata", None), ("data", []), ("stringData", None)])
def test_local_secret_rejects_wrong_identity_or_shape(secret_module, local_secret_document, field, value):
    if field in {"name", "namespace"}:
        local_secret_document["metadata"][field] = value
    else:
        local_secret_document[field] = value
    with pytest.raises(ConfigurationError):
        secret_module.prepare_local_secret(local_secret_document)


@pytest.mark.parametrize("key", ["KUBEPILOT_ENCRYPTION_KEY", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "KUBEPILOT_DATABASE_URL"])
def test_local_secret_preserves_existing_key_and_database(secret_module, local_secret_document, deployment_secret, key):
    existing = secret_document(deployment_secret)
    existing["metadata"] = {"name": "kubepilot-secret", "namespace": "kubepilot", "resourceVersion": "7"}
    existing["data"][key] = base64.b64encode(b"different-existing-value").decode()
    with pytest.raises(ConfigurationError, match="Coordinate"):
        secret_module.prepare_local_secret(local_secret_document, existing)


def test_matching_secret_preserves_version_extras_and_accepts_auth_change(secret_module, local_secret_document, deployment_secret):
    existing = secret_document(deployment_secret)
    existing["metadata"] = {"resourceVersion": "7", "annotations": {"kubectl.kubernetes.io/last-applied-configuration": "old-secret", "owner": "operator"}}
    existing["data"]["extra"] = base64.b64encode(b"preserved").decode()
    local_secret_document["stringData"]["KUBEPILOT_AUTH_SECRET"] = "different-random-auth-secret-1234567890"
    prepared = secret_module.prepare_local_secret(local_secret_document, existing)
    assert prepared["metadata"]["resourceVersion"] == "7"
    assert prepared["metadata"]["annotations"] == {"owner": "operator"}
    assert prepared["data"]["extra"] == existing["data"]["extra"]
    assert prepared["data"]["KUBEPILOT_AUTH_SECRET"] != existing["data"]["KUBEPILOT_AUTH_SECRET"]


def test_local_secret_rejects_requested_key_mismatch(secret_module, local_secret_document, monkeypatch):
    monkeypatch.setenv("KUBEPILOT_ENCRYPTION_KEY", Fernet.generate_key().decode())
    with pytest.raises(ConfigurationError, match="requested encryption key"):
        secret_module.prepare_local_secret(local_secret_document)


@pytest.fixture
def deploy_runner(tmp_path, monkeypatch, deployment_secret):
    root = Path(__file__).parents[2]
    monkeypatch.delenv("KUBEPILOT_ENCRYPTION_KEY", raising=False)
    for relative in ("deploy.sh", "scripts/validate-deployment-secret.py", "backend/app/core/config.py"):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / relative, target)
    manifest_dir = tmp_path / "backend/deploy/kubernetes"
    manifest_dir.mkdir(parents=True)
    for name in ("namespace", "service-account", "configmap", "postgres", "backend", "frontend"):
        (manifest_dir / (name + ".yaml")).touch()
    binary_dir = tmp_path / "bin"
    binary_dir.mkdir()
    # Only synthetic Secrets are used; this executable never reaches Minikube.
    fake = binary_dir / "minikube"
    fake.write_text("#!" + sys.executable + "\n" + '''import json, os, sys
from pathlib import Path
root = Path(os.environ["DEPLOY_TEST_ROOT"])
args = sys.argv[1:]
with (root / "calls.jsonl").open("a") as log:
    log.write(json.dumps(args) + "\\n")
if args[:2] != ["kubectl", "--"]:
    sys.exit(0)
args = args[2:]
state = root / "live.json"
if args[:2] == ["get", "secret"]:
    if (root / "fail-read").exists():
        print("synthetic-sensitive-api-error", file=sys.stderr)
        sys.exit(1)
    if state.exists():
        value = json.loads(state.read_text())
        print(value["data"]["KUBEPILOT_ENCRYPTION_KEY"] if any("jsonpath=" in x for x in args) else json.dumps(value))
    elif "--ignore-not-found" not in args:
        sys.exit(1)
elif args[:2] == ["get", "pvc"]:
    print(json.dumps({"items": [{}] if (root / "pvc-exists").exists() else []}))
elif args[0] in {"create", "replace"}:
    payload = json.load(sys.stdin)
    if (root / "fail-write").exists() or ((root / "concurrent-change").exists() and payload["metadata"].get("resourceVersion") != "8"):
        print("synthetic-sensitive-api-error", file=sys.stderr)
        sys.exit(1)
    payload["metadata"]["resourceVersion"] = "8"
    state.write_text(json.dumps(payload))
''')
    fake.chmod(0o755)

    def run(local=None, existing=None, pvc=False, fail_write=False, fail_read=False, concurrent_change=False):
        if local is not None:
            import yaml
            (manifest_dir / "secret.yaml").write_text(local if isinstance(local, str) else yaml.safe_dump(local))
        if existing is not None:
            (tmp_path / "live.json").write_text(json.dumps(existing))
        if pvc:
            (tmp_path / "pvc-exists").touch()
        if fail_write:
            (tmp_path / "fail-write").touch()
        if fail_read:
            (tmp_path / "fail-read").touch()
        if concurrent_change:
            (tmp_path / "concurrent-change").touch()
        result = subprocess.run(["bash", "deploy.sh", "--no-build"], cwd=tmp_path,
                                env={**os.environ, "PATH": str(binary_dir) + os.pathsep + os.environ["PATH"], "DEPLOY_TEST_ROOT": str(tmp_path)},
                                capture_output=True, text=True, timeout=20)
        calls = [json.loads(line) for line in (tmp_path / "calls.jsonl").read_text().splitlines()]
        for key in ("POSTGRES_PASSWORD", "KUBEPILOT_DATABASE_URL", "KUBEPILOT_AUTH_SECRET", "KUBEPILOT_ADMIN_PASSWORD", "KUBEPILOT_ENCRYPTION_KEY"):
            value = deployment_secret[key]
            assert value not in result.stdout + result.stderr + json.dumps(calls)
        return result, calls
    return run


@pytest.mark.parametrize("already_exists", [False, True])
def test_deploy_applies_local_secret_before_workloads(deploy_runner, local_secret_document, deployment_secret, already_exists):
    existing = secret_document(deployment_secret) if already_exists else None
    if existing is not None:
        existing["metadata"] = {"resourceVersion": "7"}
    result, calls = deploy_runner(local_secret_document, existing)
    assert result.returncode == 0, result.stderr
    operation = "replace" if already_exists else "create"
    write = next(i for i, call in enumerate(calls) if call[2:3] == [operation])
    postgres = next(i for i, call in enumerate(calls) if "backend/deploy/kubernetes/postgres.yaml" in call)
    assert write < postgres


def test_deploy_without_local_file_uses_external_secret(deploy_runner, deployment_secret):
    existing = secret_document(deployment_secret)
    result, calls = deploy_runner(existing=existing)
    assert result.returncode == 0, result.stderr
    assert not any(call[2:3] in (["create"], ["replace"]) for call in calls)


@pytest.mark.parametrize("scheme,host", INVALID_DATABASE_ENDPOINTS)
@pytest.mark.parametrize("source", ["new-local", "existing-local", "external"])
def test_deploy_rejects_unusable_database_url_before_writes(deploy_runner, local_secret_document, deployment_secret, scheme, host, source):
    deployment_secret["KUBEPILOT_DATABASE_URL"] = f"{scheme}://user:unique-database-password@{host}/app"
    local_secret_document["stringData"].update(deployment_secret)
    existing = secret_document(deployment_secret) if source != "new-local" else None
    if existing is not None:
        existing["metadata"] = {"resourceVersion": "7"}
    result, calls = deploy_runner(None if source == "external" else local_secret_document, existing)
    assert result.returncode != 0
    assert "Deployment Secret is missing or unsafe" in result.stderr
    assert not any(call[2:3] in (["create"], ["replace"]) for call in calls)
    for workload in ("postgres", "backend", "frontend"):
        assert not any(f"backend/deploy/kubernetes/{workload}.yaml" in call for call in calls)


@pytest.mark.parametrize("url,database", AMBIGUOUS_DATABASE_URLS)
@pytest.mark.parametrize("source", ["new-local", "existing-local", "external"])
def test_deploy_rejects_runtime_url_mismatch_before_writes(deploy_runner, local_secret_document, deployment_secret, url, database, source):
    deployment_secret.update(KUBEPILOT_DATABASE_URL=url, POSTGRES_DB=database)
    local_secret_document["stringData"].update(deployment_secret)
    existing = secret_document(deployment_secret) if source != "new-local" else None
    if existing is not None:
        existing["metadata"] = {"resourceVersion": "7"}
    result, calls = deploy_runner(None if source == "external" else local_secret_document, existing)
    assert result.returncode != 0
    assert "Deployment Secret is missing or unsafe" in result.stderr
    assert not any(call[2:3] in (["create"], ["replace"]) for call in calls)
    for workload in ("postgres", "backend", "frontend"):
        assert not any(f"backend/deploy/kubernetes/{workload}.yaml" in call for call in calls)


def test_deploy_without_any_secret_stops_before_workloads(deploy_runner):
    result, calls = deploy_runner()
    assert result.returncode != 0
    assert not any("backend/deploy/kubernetes/postgres.yaml" in call for call in calls)


@pytest.mark.parametrize("failure", ["missing-key", "wrong-name", "wrong-namespace", "changed-key", "changed-database", "storage-without-secret", "api-read-error", "api-write-error", "concurrent-change", "malformed-yaml", "non-string-value"])
def test_deploy_rejects_unsafe_local_secret_before_workloads(deploy_runner, local_secret_document, deployment_secret, failure):
    existing = secret_document(deployment_secret)
    existing["metadata"] = {"resourceVersion": "7"}
    if failure == "missing-key":
        local_secret_document["stringData"].pop("POSTGRES_USER")
    elif failure == "wrong-name":
        local_secret_document["metadata"]["name"] = "other-secret"
    elif failure == "wrong-namespace":
        local_secret_document["metadata"]["namespace"] = "default"
    elif failure == "changed-key":
        local_secret_document["stringData"]["KUBEPILOT_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
    elif failure == "changed-database":
        existing["data"]["POSTGRES_PASSWORD"] = base64.b64encode(b"previous-database-password").decode()
    elif failure == "malformed-yaml":
        local_secret_document = 'stringData:\n  KUBEPILOT_AUTH_SECRET: "synthetic-sensitive-api-error\n'
    elif failure == "non-string-value":
        local_secret_document["stringData"]["POSTGRES_PASSWORD"] = 1234
    result, calls = deploy_runner(local_secret_document, None if failure == "storage-without-secret" else existing,
                                 pvc=failure == "storage-without-secret", fail_write=failure == "api-write-error",
                                 fail_read=failure == "api-read-error", concurrent_change=failure == "concurrent-change")
    assert result.returncode != 0
    assert "synthetic-sensitive-api-error" not in result.stderr
    assert not any("backend/deploy/kubernetes/postgres.yaml" in call for call in calls)
    if failure not in {"api-write-error", "concurrent-change"}:
        assert not any(call[2:3] in (["create"], ["replace"]) for call in calls)
