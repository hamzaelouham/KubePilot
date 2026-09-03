from pathlib import Path

import yaml


MANIFEST = Path(__file__).parents[1] / "deploy" / "kubernetes" / "service-account.yaml"


def test_rbac_manifest_is_read_only_for_discovery() -> None:
    documents = list(yaml.safe_load_all(MANIFEST.read_text()))
    role = next(document for document in documents if document["kind"] == "ClusterRole")
    verbs = {verb for rule in role["rules"] for verb in rule["verbs"]}
    resources = {resource for rule in role["rules"] for resource in rule["resources"]}

    assert verbs == {"get", "list", "watch"}
    assert resources == {
        "namespaces",
        "pods",
        "services",
        "nodes",
        "endpoints",
        "replicationcontrollers",
        "persistentvolumes",
        "deployments",
        "replicasets",
        "daemonsets",
        "statefulsets",
        "jobs",
        "cronjobs",
        "clusterroles",
        "storageclasses",
    }
