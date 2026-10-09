from pathlib import Path

import yaml


MANIFEST = Path(__file__).parents[1] / "deploy" / "kubernetes" / "service-account.yaml"


def test_rbac_manifest_is_read_only_for_discovery() -> None:
    documents = list(yaml.safe_load_all(MANIFEST.read_text()))
    role = next(document for document in documents if document["kind"] == "ClusterRole" and document["metadata"]["name"] == "kubepilot-api-discovery")
    verbs = {verb for rule in role["rules"] for verb in rule["verbs"]}
    resources = {resource for rule in role["rules"] for resource in rule["resources"]}

    assert verbs == {"get", "list", "watch"}
    assert resources == {
        "namespaces",
        "pods",
        "pods/log",
        "services",
        "nodes",
        "endpoints",
        "replicationcontrollers",
        "persistentvolumes",
        "persistentvolumeclaims",
        "events",
        "deployments",
        "replicasets",
        "daemonsets",
        "statefulsets",
        "jobs",
        "cronjobs",
        "clusterroles",
        "storageclasses",
    }
    metrics_rule = next(rule for rule in role["rules"] if rule["apiGroups"] == ["metrics.k8s.io"])
    assert set(metrics_rule["resources"]) == {"nodes", "pods"}


def test_all_rbac_roles_and_bindings_have_explicit_permissions() -> None:
    documents = list(yaml.safe_load_all(MANIFEST.read_text()))
    assert len(documents) == 5
    assert documents[0] == {
        "apiVersion": "v1", "kind": "ServiceAccount",
        "metadata": {"name": "kubepilot-api", "namespace": "kubepilot"},
    }
    expected = {
        "kubepilot-api-discovery": {
            "": {"namespaces", "pods", "services", "nodes", "endpoints",
                 "replicationcontrollers", "persistentvolumes", "persistentvolumeclaims", "events", "pods/log"},
            "metrics.k8s.io": {"nodes", "pods"},
            "apps": {"deployments", "replicasets", "daemonsets", "statefulsets"},
            "batch": {"jobs", "cronjobs"},
            "rbac.authorization.k8s.io": {"clusterroles"},
            "storage.k8s.io": {"storageclasses"},
        },
        "kubepilot-api-operations": {
            "": {"pods", "services", "namespaces", "configmaps", "secrets", "serviceaccounts",
                 "persistentvolumeclaims", "replicationcontrollers"},
            "apps": {"deployments", "replicasets", "daemonsets", "statefulsets"},
            "batch": {"jobs", "cronjobs"},
            "networking.k8s.io": {"ingresses", "networkpolicies"},
            "autoscaling": {"horizontalpodautoscalers"},
            "policy": {"poddisruptionbudgets"},
        },
    }
    roles = [d for d in documents if d["kind"] == "ClusterRole"]
    assert {r["metadata"]["name"] for r in roles} == set(expected)
    permissions = set()
    for role in roles:
        name = role["metadata"]["name"]
        assert set(role) == {"apiVersion", "kind", "metadata", "rules"}
        actual = set()
        for rule in role["rules"]:
            assert set(rule) == {"apiGroups", "resources", "verbs"}
            actual.update((g, r, v) for g in rule["apiGroups"] for r in rule["resources"] for v in rule["verbs"])
        wanted = set()
        for group, resources in expected[name].items():
            for resource in resources:
                verbs = {"get", "list", "watch"}
                if name == "kubepilot-api-operations":
                    verbs |= {"create", "update", "patch", "delete"}
                elif resource == "pods/log":
                    verbs = {"get"}
                wanted.update((group, resource, verb) for verb in verbs)
        assert actual == wanted
        permissions |= actual
    bindings = [d for d in documents if d["kind"] == "ClusterRoleBinding"]
    assert {b["metadata"]["name"] for b in bindings} == set(expected)
    for binding in bindings:
        assert binding["roleRef"] == {
            "apiGroup": "rbac.authorization.k8s.io", "kind": "ClusterRole",
            "name": binding["metadata"]["name"],
        }
        assert binding["subjects"] == [{"kind": "ServiceAccount", "name": "kubepilot-api", "namespace": "kubepilot"}]
    for forbidden in [
        ("rbac.authorization.k8s.io", "clusterrolebindings", "create"),
        ("apiextensions.k8s.io", "customresourcedefinitions", "create"),
        ("admissionregistration.k8s.io", "validatingwebhookconfigurations", "create"),
        ("", "nodes", "delete"), ("", "pods/exec", "create"),
        ("", "pods/attach", "create"), ("", "serviceaccounts/token", "create"),
    ]:
        assert forbidden not in permissions
