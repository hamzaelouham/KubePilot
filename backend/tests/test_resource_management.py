import json
from contextlib import nullcontext
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
import yaml
from fastapi.testclient import TestClient
from kubernetes import client as kube_client
from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.core.config import ConfigurationError, Settings
from app.kubernetes.resource_management import (
    RESOURCE_KINDS, ManagementClient, ResourceManagementError, ensure_unprotected,
    management_client, parse_manifest, resource_kind,
)
from app.core.dependencies import AuthenticatedActor, get_current_actor
from app.models.base import Base
from app.models.entities import AuditAction, ClusterConnection, UserAccount


def manifest_for(resource_type="pods", name="example", namespace=None):
    kind = RESOURCE_KINDS[resource_type]
    metadata = {"name": name}
    if namespace is not None:
        metadata["namespace"] = namespace
    return {"apiVersion": kind.api_version, "kind": kind.kind, "metadata": metadata}


@pytest.mark.parametrize("resource_type", RESOURCE_KINDS)
def test_manifest_mapping_preserves_spec_and_selects_namespace(resource_type):
    kind = resource_kind(resource_type)
    source = manifest_for(resource_type)
    source["spec"] = {"example": ["unchanged"]}
    parsed = parse_manifest(yaml.safe_dump(source), kind, "default" if kind.namespaced else None)
    assert parsed["spec"] == source["spec"]
    assert parsed["metadata"].get("namespace") == ("default" if kind.namespaced else None)


@pytest.mark.parametrize("content", [
    "", "[]", "null", "!!python/object/apply:os.system ['echo forbidden']",
    "a: &a [*a]", "a: 1\na: 2", "a: {x: 1, x: 2}",
    "a: 1\n---\nb: 2", "a: .nan", "a: 2026-09-11", "{[a]: b}", "{1: a}",
    "apiVersion: [", "kind: List\napiVersion: v1\nitems: []",
])
def test_invalid_yaml_is_rejected_without_echoing_content(content):
    with pytest.raises(ResourceManagementError) as caught:
        parse_manifest(content, resource_kind("pods"), "default")
    assert caught.value.status == 422
    assert "os.system" not in caught.value.message


@pytest.mark.parametrize("field", ["uid", "resourceVersion", "creationTimestamp", "deletionTimestamp", "managedFields", "generateName"])
def test_server_metadata_is_rejected(field):
    source = manifest_for()
    source["metadata"][field] = "sensitive-value"
    with pytest.raises(ResourceManagementError, match="server-managed"):
        parse_manifest(json.dumps(source), resource_kind("pods"), "default")


@pytest.mark.parametrize("change", [
    {"kind": "Service"}, {"apiVersion": "apps/v1"}, {"metadata": {}},
    {"metadata": {"name": "../escape"}}, {"status": {}},
    {"metadata": {"name": "pod", "namespace": "different"}},
])
def test_invalid_resource_identity(change):
    source = manifest_for() | change
    with pytest.raises(ResourceManagementError):
        parse_manifest(json.dumps(source), resource_kind("pods"), "default")


@pytest.mark.parametrize("resource_type,namespace", [("pods", None), ("pods", ""), ("namespaces", "default")])
def test_invalid_namespace_scope(resource_type, namespace):
    with pytest.raises(ResourceManagementError):
        parse_manifest(json.dumps(manifest_for(resource_type)), resource_kind(resource_type), namespace)


def test_namespace_cannot_embed_a_namespace():
    with pytest.raises(ResourceManagementError):
        parse_manifest(json.dumps(manifest_for("namespaces", namespace="default")), resource_kind("namespaces"), None)


@pytest.mark.parametrize("namespace", ["kube-system", "kube-public", "kube-node-lease", "hosting"])
@pytest.mark.parametrize("deleting", [False, True])
@pytest.mark.parametrize("resource_type", ["pods", "namespaces"])
def test_protected_scope_has_no_role_bypass(namespace, deleting, resource_type):
    kind = resource_kind(resource_type)
    with pytest.raises(ResourceManagementError) as caught:
        ensure_unprotected(kind, namespace if kind.namespaced else None, namespace, "hosting", deleting=deleting)
    assert caught.value.code == "namespace_protected"


def test_default_contents_allowed_but_namespace_delete_blocked():
    for deleting in (False, True):
        ensure_unprotected(resource_kind("pods"), "default", "pod", "kubepilot", deleting=deleting)
    ensure_unprotected(resource_kind("namespaces"), None, "default", "kubepilot", deleting=False)
    with pytest.raises(ResourceManagementError):
        ensure_unprotected(resource_kind("namespaces"), None, "default", "kubepilot", deleting=True)


@pytest.mark.parametrize("name", ["", "A", "a.b", "x" * 64, "../escape", "a "])
def test_invalid_host_namespace_configuration(name):
    with pytest.raises(ConfigurationError):
        Settings(auth_secret="x" * 32, database_url="sqlite://", host_namespace=name)


def test_unknown_resource_not_dispatched():
    with pytest.raises(ResourceManagementError) as caught:
        resource_kind("secrets")
    assert caught.value.code == "invalid_resource_type"


def live_resource(namespace="default", name="example", uid="resource-uid", deleting=None):
    return SimpleNamespace(
        metadata=SimpleNamespace(name=name, namespace=namespace, uid=uid, deletion_timestamp=deleting),
        status=SimpleNamespace(phase="Running"),
        spec=SimpleNamespace(replicas=1, secret="must-not-leak"),
    )


class FakeResources:
    def __init__(self):
        self.calls = []
        self.item = live_resource()
        self.error = None

    def resources(self, kind, namespace):
        self.calls.append(("list", kind.kind, namespace))
        return [live_resource(namespace=namespace if kind.namespaced else None)]

    def read(self, kind, namespace, name):
        self.calls.append(("read", kind.kind, namespace, name))
        if self.error:
            raise self.error
        return self.item

    def create(self, kind, namespace, manifest):
        self.calls.append(("create", kind.kind, namespace, manifest))
        if self.error:
            raise self.error
        return live_resource(namespace, manifest["metadata"]["name"], uid="created-uid")

    def delete(self, kind, namespace, name, uid):
        self.calls.append(("delete", kind.kind, namespace, name, uid))
        if self.error:
            raise self.error


@pytest.fixture()
def api(tmp_path, monkeypatch):
    from app.main import create_app

    monkeypatch.setenv("KUBEPILOT_AUTH_SECRET", "x" * 32)
    monkeypatch.setenv("KUBEPILOT_DATABASE_URL", f"sqlite:///{tmp_path / 'resources.db'}")
    monkeypatch.setenv("KUBEPILOT_WORKER_ENABLED", "false")
    monkeypatch.setenv("KUBEPILOT_HOST_NAMESPACE", "hosting")
    settings = Settings.from_env()
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as database:
        user = UserAccount(email="resource@example.test", password_hash="unused", role="admin")
        primary = ClusterConnection(name="primary", endpoint="in-cluster", kubeconfig_ref="in-cluster", status="active")
        staging = ClusterConnection(name="staging", endpoint="https://staging.test", kubeconfig_ref="staging", kubeconfig_content="stored-credentials", status="active")
        database.add_all([user, primary, staging])
        database.commit()
        actor = AuthenticatedActor(user.email, "admin", user_id=user.id)
    fake = FakeResources()
    state = SimpleNamespace(actor=actor, factory=factory, kubernetes=fake, targets=[], cluster_id=primary.id)

    def selected(cluster):
        state.targets.append((cluster.id, cluster.name, cluster.kubeconfig_content))
        return nullcontext(fake)

    monkeypatch.setattr("app.api.v1.resource_management.management_client", selected)
    app = create_app()
    app.dependency_overrides[get_current_actor] = lambda: state.actor
    with TestClient(app) as client:
        state.client = client
        yield state
    engine.dispose()


PREFIX = "/api/v1/cluster/manage-resources"


@pytest.mark.parametrize("role", ["admin", "operator", "viewer"])
@pytest.mark.parametrize("resource_type", RESOURCE_KINDS)
def test_inventory_roles_types_and_redaction(api, role, resource_type):
    api.actor = replace(api.actor, role=role)
    response = api.client.get(f"{PREFIX}/{resource_type}?cluster=staging")
    assert response.status_code == 200, response.text
    item = response.json()["items"][0]
    assert item["uid"] == "resource-uid"
    assert item["cluster"] == "staging"
    assert item["kind"] == resource_kind(resource_type).kind
    assert bool(item["delete_blocked_reason"]) == (role == "viewer")
    assert "must-not-leak" not in response.text
    assert "stored-credentials" not in response.text
    assert api.targets[0][1:] == ("staging", "stored-credentials")


@pytest.mark.parametrize("query,code", [
    ("", "invalid_resource_identity"), ("?cluster=", "invalid_resource_identity"),
    ("?cluster=primary&cluster=staging", "invalid_resource_identity"),
    ("?cluster=missing", "cluster_not_found"),
    ("?cluster=primary&namespace=one&namespace=two", "invalid_namespace_scope"),
])
def test_invalid_inventory_scope_never_constructs_client(api, query, code):
    response = api.client.get(f"{PREFIX}/pods{query}")
    assert response.status_code in (404, 422)
    assert response.json()["code"] == code
    assert api.targets == []


def test_inactive_cluster_cannot_be_used(api):
    with api.factory() as database:
        database.get(ClusterConnection, api.cluster_id).status = "inactive"
        database.commit()
    assert api.client.get(f"{PREFIX}/pods?cluster=primary").status_code == 404
    assert api.targets == []


def test_restricted_and_unauthenticated_inventory_denied_before_kubernetes(api):
    api.actor = replace(api.actor, restricted=True)
    assert api.client.get(f"{PREFIX}/pods?cluster=primary").json()["code"] == "password_change_required"
    api.client.app.dependency_overrides.pop(get_current_actor)
    assert api.client.get(f"{PREFIX}/pods?cluster=primary").status_code == 401
    assert api.targets == []


def test_namespaces_are_cluster_scoped(api):
    assert api.client.get(f"{PREFIX}/namespaces?cluster=primary&namespace=default").status_code == 422
    response = api.client.get(f"{PREFIX}/namespaces?cluster=primary")
    assert response.json()["items"][0]["namespace"] is None


@pytest.mark.parametrize("resource_type", RESOURCE_KINDS)
def test_installed_sdk_dispatch_validation_and_delete_preconditions(monkeypatch, resource_type):
    calls = []
    configuration = kube_client.Configuration()
    with kube_client.ApiClient(configuration=configuration) as raw:
        def call_api(*args, **kwargs):
            calls.append((args, kwargs))
            return SimpleNamespace(items=[], metadata=None)
        monkeypatch.setattr(raw, "call_api", call_api)
        adapter = ManagementClient(raw)
        kind = resource_kind(resource_type)
        namespace = "default" if kind.namespaced else None
        adapter.resources(kind, namespace)
        adapter.create(kind, namespace, manifest_for(resource_type))
        adapter.delete(kind, namespace, "example", "confirmed-uid")
    assert calls[0][0][1] == "GET"
    assert calls[1][0][1] == "POST"
    assert ("fieldValidation", "Strict") in calls[1][0][3]
    options = calls[2][1]["body"]
    assert options.preconditions.uid == "confirmed-uid"
    assert options.propagation_policy is None
    assert options.grace_period_seconds is None


def test_interleaved_cluster_configuration_is_isolated(monkeypatch):
    from app.kubernetes import resource_management as module
    def load(content, client_configuration, persist_config):
        assert persist_config is False
        client_configuration.host = content["host"]
        client_configuration.api_key["authorization"] = content["token"]
    monkeypatch.setattr(module.config, "load_kube_config_from_dict", load)
    primary = SimpleNamespace(kubeconfig_content="host: https://primary.test\ntoken: primary-token")
    staging = SimpleNamespace(kubeconfig_content="host: https://staging.test\ntoken: staging-token")
    original_default = kube_client.Configuration.get_default_copy().host
    with management_client(primary) as first:
        with management_client(staging) as second:
            a = first.apis["core"].api_client.configuration
            b = second.apis["apps"].api_client.configuration
            assert a.host == "https://primary.test" and b.host == "https://staging.test"
            assert a.api_key["authorization"] == "primary-token"
            assert b.api_key["authorization"] == "staging-token"
            assert a is not b and a.retries == b.retries == 0
            assert kube_client.Configuration.get_default_copy().host == original_default


def test_remote_missing_credentials_never_falls_back_to_host():
    with pytest.raises(ResourceManagementError) as caught:
        with management_client(SimpleNamespace(kubeconfig_content=None, endpoint="https://remote.test")):
            pytest.fail("must not construct a client")
    assert caught.value.code == "cluster_unavailable"


def create_request(api, resource_type="pods", name="example", namespace="default", **extra):
    params = {"cluster": "primary"}
    if resource_kind(resource_type).namespaced:
        params["namespace"] = namespace
    source = manifest_for(resource_type, name) | extra
    return api.client.post(f"{PREFIX}/{resource_type}", params=params, json={"yaml": yaml.safe_dump(source)})


def delete_request(api, resource_type="pods", name="example", namespace="default", uid="resource-uid", confirm="example"):
    params = {"cluster": "primary"}
    if resource_kind(resource_type).namespaced:
        params["namespace"] = namespace
    return api.client.request("DELETE", f"{PREFIX}/{resource_type}/{name}", params=params, json={"uid": uid, "confirm_name": confirm})


def audit_rows(api):
    with api.factory() as database:
        return database.scalars(select(AuditAction).order_by(AuditAction.created_at, AuditAction.id)).all()


@pytest.mark.parametrize("resource_type", RESOURCE_KINDS)
@pytest.mark.parametrize("role", ["admin", "operator"])
def test_create_resource_dispatch_and_audit(api, role, resource_type, monkeypatch):
    api.actor = replace(api.actor, role=role)
    operation_id = uuid4()
    monkeypatch.setattr("app.api.v1.resource_management.uuid4", lambda: operation_id)
    response = create_request(api, resource_type, spec={"sensitive": "do-not-record"})
    assert response.status_code == 201, response.text
    resource = response.json()["resource"]
    assert resource["cluster_id"] == str(api.cluster_id)
    assert resource["uid"] == "created-uid"
    assert resource["namespace"] == ("default" if resource_kind(resource_type).namespaced else None)
    rows = audit_rows(api)
    assert [row.action for row in rows] == ["resource.create_requested", "resource.create_result"]
    assert [row.result for row in rows] == ["requested", "success"]
    assert all(row.actor_id == api.actor.user_id for row in rows)
    assert all(json.loads(row.context)["operation_id"] == str(operation_id) for row in rows)
    assert json.loads(rows[1].context)["uid"] == "created-uid"
    assert "do-not-record" not in response.text + str([row.context for row in rows])


@pytest.mark.parametrize("resource_type", RESOURCE_KINDS)
@pytest.mark.parametrize("role", ["admin", "operator"])
def test_delete_resource_dispatch_and_acceptance(api, role, resource_type):
    api.actor = replace(api.actor, role=role)
    response = delete_request(api, resource_type)
    assert response.status_code == 202, response.text
    assert response.json()["status"] == "deletion_requested"
    assert response.json()["uid"] == "resource-uid"
    assert api.kubernetes.calls[-1] == (
        "delete", resource_kind(resource_type).kind,
        "default" if resource_kind(resource_type).namespaced else None,
        "example", "resource-uid",
    )
    assert [row.action for row in audit_rows(api)] == ["resource.delete_requested", "resource.delete_result"]


@pytest.mark.parametrize("action", ["create", "delete"])
def test_viewer_denied_before_constructing_mutation_client(api, action):
    api.actor = replace(api.actor, role="viewer")
    response = create_request(api) if action == "create" else delete_request(api)
    assert response.status_code == 403
    assert api.targets == [] and audit_rows(api) == []


@pytest.mark.parametrize("role", ["admin", "operator"])
@pytest.mark.parametrize("target", ["kube-system", "kube-public", "kube-node-lease", "hosting"])
@pytest.mark.parametrize("resource_type", ["pods", "namespaces"])
def test_api_protection_covers_both_roles_and_namespace_objects(api, role, target, resource_type):
    api.actor = replace(api.actor, role=role)
    name = target if resource_type == "namespaces" else "example"
    for response in (
        create_request(api, resource_type, name=name, namespace=target),
        delete_request(api, resource_type, name=name, namespace=target, confirm=name),
    ):
        assert response.status_code == 422
        assert response.json()["code"] == "namespace_protected"
    assert api.targets == [] and audit_rows(api) == []


def test_default_namespace_delete_protected_but_contents_manageable(api):
    response = delete_request(api, "namespaces", name="default", confirm="default")
    assert response.json()["code"] == "namespace_protected"
    assert create_request(api).status_code == 201
    assert delete_request(api).status_code == 202


@pytest.mark.parametrize("uid,confirm,code", [
    ("resource-uid", "wrong", "confirmation_required"),
    ("", "example", "validation_error"),
    (" ", "example", "invalid_resource_identity"),
    ("old-uid", "example", "resource_conflict"),
])
def test_invalid_confirmation_or_replaced_object_never_deleted(api, uid, confirm, code):
    response = delete_request(api, uid=uid, confirm=confirm)
    assert response.json()["code"] == code
    assert not any(call[0] == "delete" for call in api.kubernetes.calls)
    assert audit_rows(api) == []


def test_already_terminating_object_is_not_deleted_again(api):
    api.kubernetes.item = live_resource(deleting=datetime.now(timezone.utc))
    response = delete_request(api)
    assert response.status_code == 202
    assert [call[0] for call in api.kubernetes.calls] == ["read"]


def test_missing_target_requires_refresh(api):
    api.kubernetes.error = ResourceManagementError(404, "resource_not_found", "Refresh inventory")
    assert delete_request(api).json()["code"] == "resource_not_found"
    assert [call[0] for call in api.kubernetes.calls] == ["read"]


@pytest.mark.parametrize("status,code,outcome", [
    (409, "resource_conflict", "failure"),
    (422, "invalid_manifest", "failure"),
    (504, "operation_outcome_unknown", "unknown"),
])
def test_failed_or_uncertain_create_is_audited_and_never_retried(api, status, code, outcome):
    api.kubernetes.error = ResourceManagementError(status, code, "Safe error")
    response = create_request(api)
    assert response.status_code == status
    assert [call[0] for call in api.kubernetes.calls] == ["create"]
    rows = audit_rows(api)
    assert rows[1].result == outcome
    assert json.loads(rows[1].context)["error_code"] == code


def test_uid_race_after_preliminary_read_still_rejected(api, monkeypatch):
    def replaced(*args):
        raise ResourceManagementError(409, "resource_conflict", "Replaced")
    monkeypatch.setattr(api.kubernetes, "delete", replaced)
    response = delete_request(api)
    assert response.status_code == 409
    assert audit_rows(api)[1].result == "failure"


@pytest.mark.parametrize("action", ["create", "delete"])
def test_audit_intent_failure_prevents_mutation(api, action, monkeypatch, caplog):
    def unavailable(*args, **kwargs):
        raise SQLAlchemyError("private-db-error")
    monkeypatch.setattr("app.api.v1.resource_management.record_audit", unavailable)
    response = create_request(api) if action == "create" else delete_request(api)
    assert response.status_code == 503
    assert response.json()["code"] == "audit_unavailable"
    assert not any(call[0] in ("create", "delete") for call in api.kubernetes.calls)
    assert "private-db-error" not in response.text + caplog.text


@pytest.mark.parametrize("action", ["create", "delete"])
def test_audit_result_failure_preserves_observed_success_and_intent(api, action, monkeypatch, caplog):
    from app.api.v1 import resource_management as module
    original = module.record_audit
    def result_unavailable(database, event, *args, **kwargs):
        if event.endswith("_result"):
            raise SQLAlchemyError("private-db-error")
        return original(database, event, *args, **kwargs)
    monkeypatch.setattr(module, "record_audit", result_unavailable)
    response = create_request(api) if action == "create" else delete_request(api)
    assert response.status_code == (201 if action == "create" else 202)
    rows = audit_rows(api)
    assert len(rows) == 1 and rows[0].result == "requested"
    assert json.loads(rows[0].context)["operation_id"] in caplog.text
    assert "private-db-error" not in response.text + caplog.text


@pytest.mark.parametrize("status,code", [(403, "cluster_forbidden"), (409, "resource_conflict"), (422, "invalid_manifest"), (500, "operation_outcome_unknown")])
def test_upstream_errors_never_echo_manifest_or_credentials(status, code):
    from kubernetes.client.exceptions import ApiException
    from app.kubernetes.resource_management import _translate_error
    error = ApiException(status=status, reason="secret-reason")
    error.body = "secret-manifest-value"
    translated = _translate_error(error, "create")
    assert translated.code == code
    assert "secret" not in translated.message


def test_timeouts_and_connection_loss_have_unknown_mutation_outcome():
    from app.kubernetes.resource_management import _translate_error
    for error in (TimeoutError("secret"), OSError("secret")):
        assert _translate_error(error, "delete").code == "operation_outcome_unknown"
        assert _translate_error(error, "read").code == "cluster_unavailable"


@pytest.mark.parametrize("role", ["admin", "operator", "viewer"])
def test_real_cookie_roles_and_live_session_changes(api, role):
    from app.core.passwords import hash_password

    api.client.app.dependency_overrides.pop(get_current_actor)
    with api.factory() as database:
        user = database.get(UserAccount, api.actor.user_id)
        user.password_hash = hash_password("management-test-password-01")
        user.role = role
        user.must_change_password = False
        database.commit()
    login = api.client.post("/api/v1/auth/login", json={
        "email": api.actor.identifier, "password": "management-test-password-01",
    })
    assert login.status_code == 200, login.text
    api.client.cookies.set("kubepilot_session", login.json()["cookie"])
    assert api.client.get(f"{PREFIX}/pods?cluster=primary").status_code == 200
    assert create_request(api).status_code == (403 if role == "viewer" else 201)
    assert delete_request(api).status_code == (403 if role == "viewer" else 202)

    # A signed cookie does not freeze the role or authorize a deactivated user.
    with api.factory() as database:
        user = database.get(UserAccount, api.actor.user_id)
        user.role = "viewer"
        database.commit()
    api.targets.clear()
    assert create_request(api).status_code == 403
    assert delete_request(api).status_code == 403
    with api.factory() as database:
        database.get(UserAccount, api.actor.user_id).is_active = False
        database.commit()
    assert api.client.get(f"{PREFIX}/pods?cluster=primary").status_code == 401
    assert create_request(api).status_code == 401
    assert delete_request(api).status_code == 401
    assert api.targets == []


def test_real_restricted_cookie_cannot_manage_resources(api):
    from app.core.passwords import hash_password

    api.client.app.dependency_overrides.pop(get_current_actor)
    with api.factory() as database:
        user = database.get(UserAccount, api.actor.user_id)
        user.password_hash = hash_password("management-test-password-01")
        user.must_change_password = True
        database.commit()
    login = api.client.post("/api/v1/auth/login", json={
        "email": api.actor.identifier, "password": "management-test-password-01",
    })
    assert login.status_code == 200, login.text
    api.client.cookies.set("kubepilot_session", login.json()["cookie"])
    for response in (api.client.get(f"{PREFIX}/pods?cluster=primary"), create_request(api), delete_request(api)):
        assert response.status_code == 403
        assert response.json()["code"] == "password_change_required"
    assert api.targets == []


@pytest.mark.parametrize("method,body", [
    ("POST", {}), ("POST", {"yaml": 1}), ("POST", {"yaml": "sensitive", "endpoint": "https://untrusted"}),
    ("DELETE", {"confirm_name": "example"}), ("DELETE", {"uid": "resource-uid", "confirm_name": "example", "force": True}),
])
def test_malformed_request_envelopes_never_reach_kubernetes(api, method, body):
    suffix = "/example" if method == "DELETE" else ""
    response = api.client.request(method, f"{PREFIX}/pods{suffix}?cluster=primary&namespace=default", json=body)
    assert response.status_code == 422
    assert response.json() == {"code": "validation_error", "message": "Request validation failed"}
    assert api.targets == []


@pytest.mark.parametrize("method", ["POST", "DELETE"])
@pytest.mark.parametrize("query", [
    "namespace=default", "cluster=missing&namespace=default", "cluster=primary",
    "cluster=primary&cluster=staging&namespace=default", "cluster=primary&namespace=default&namespace=other",
])
def test_mutations_never_fall_back_from_ambiguous_or_missing_scope(api, method, query):
    suffix = "/example" if method == "DELETE" else ""
    body = {"yaml": yaml.safe_dump(manifest_for())} if method == "POST" else {"uid": "resource-uid", "confirm_name": "example"}
    response = api.client.request(method, f"{PREFIX}/pods{suffix}?{query}", json=body)
    assert response.status_code in (404, 422)
    assert api.targets == []


@pytest.mark.parametrize("resource_type", ["pods", "namespaces"])
def test_continuation_tokens_preserve_selected_scope(monkeypatch, resource_type):
    with kube_client.ApiClient(configuration=kube_client.Configuration()) as raw:
        adapter = ManagementClient(raw)
        calls = []
        def page(kind, method, operation, **kwargs):
            calls.append((method, kwargs.copy()))
            return SimpleNamespace(items=[len(calls)], metadata=SimpleNamespace(_continue="next" if len(calls) == 1 else None))
        monkeypatch.setattr(adapter, "_call", page)
        kind = resource_kind(resource_type)
        namespace = "selected" if kind.namespaced else None
        assert adapter.resources(kind, namespace) == [1, 2]
        assert calls[0][1] == ({"namespace": "selected"} if namespace else {})
        assert calls[1][1] == {**calls[0][1], "_continue": "next"}


def test_repeated_continuation_is_a_safe_error(monkeypatch):
    with kube_client.ApiClient(configuration=kube_client.Configuration()) as raw:
        adapter = ManagementClient(raw)
        monkeypatch.setattr(adapter, "_call", lambda *args, **kwargs: SimpleNamespace(items=[], metadata=SimpleNamespace(_continue="same")))
        with pytest.raises(ResourceManagementError, match="continuation"):
            adapter.resources(resource_kind("pods"), None)


def test_terminating_inventory_exposes_lifecycle_and_blocks_delete(api, monkeypatch):
    monkeypatch.setattr(api.kubernetes, "resources", lambda *args: [live_resource(deleting=datetime.now(timezone.utc))])
    item = api.client.get(f"{PREFIX}/pods?cluster=primary&namespace=default").json()["items"][0]
    assert item["status"] == "Terminating"
    assert item["deletion_timestamp"] is not None
    assert item["delete_blocked_reason"]


def test_unknown_delete_outcome_records_intent_and_never_retries(api, monkeypatch):
    calls = []
    def unknown(*args):
        calls.append(args)
        raise ResourceManagementError(504, "operation_outcome_unknown", "Refresh inventory")
    monkeypatch.setattr(api.kubernetes, "delete", unknown)
    assert delete_request(api).status_code == 504
    assert len(calls) == 1
    assert [row.result for row in audit_rows(api)] == ["requested", "unknown"]


def test_duplicate_create_is_not_an_update_or_retry(api, monkeypatch):
    calls = []
    def create(kind, namespace, manifest):
        calls.append(manifest)
        if len(calls) > 1:
            raise ResourceManagementError(409, "resource_conflict", "Already exists")
        return live_resource()
    monkeypatch.setattr(api.kubernetes, "create", create)
    assert create_request(api).status_code == 201
    assert create_request(api).status_code == 409
    assert len(calls) == 2
    assert [row.result for row in audit_rows(api)] == ["requested", "success", "requested", "failure"]
