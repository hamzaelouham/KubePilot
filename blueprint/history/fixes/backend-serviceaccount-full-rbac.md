# Grant backend ServiceAccount full RBAC for Helm installs

> **Type:** Fix
> **Status:** verified
> **Branch:** `fix/backend-serviceaccount-full-rbac`

## The problem

Marketplace Helm installs failed with a K8s RBAC `forbidden` error. For example,
installing cert-manager failed:

```
Error: INSTALLATION FAILED: unable to continue with install: could not get
information about the resource ServiceAccount "test-cert-manager-cainjector" in
namespace "kubepilot": serviceaccounts ... is forbidden: User
"system:serviceaccount:kubepilot:kubepilot-api" cannot get resource
"serviceaccounts" in API group "" ...
```

The backend's in-cluster worker (`backend/app/jobs/worker.py` →
`_process_claimed_job` → `_run_helm_install`) runs `helm install` as the
`kubepilot-api` ServiceAccount. For the in-cluster/primary target there is no
stored `kubeconfig_content`, so Helm uses the pod's ServiceAccount token. That
ServiceAccount was bound only to the read-only `kubepilot-api-discovery`
ClusterRole, which grants `get/list/watch` for discovery but **no** create/update
rights. Real charts (cert-manager is the reported case) create ServiceAccounts,
Secrets, ClusterRoles, CRDs, webhooks — so every such install was forbidden.

## The fix

The backend must be able to execute install actions against the primary
(in-cluster) cluster and managed clusters. Bind the `kubepilot-api`
ServiceAccount to the built-in `cluster-admin` ClusterRole so it has full
cluster-wide rights in the primary cluster. Managed clusters are unaffected —
they already use their own stored kubeconfig credentials via `--kubeconfig`
(`_run_helm_install`, worker.py:85-86).

Change confined to `backend/deploy/kubernetes/service-account.yaml`: a new
`kubepilot-api-admin` ClusterRoleBinding binds the `kubepilot-api` ServiceAccount
(namespace `kubepilot`) to the `cluster-admin` ClusterRole. The existing
`kubepilot-api-discovery` role and binding are unchanged. Additive RBAC only —
no application code changes.

## Build steps

**Step 1 — Add the cluster-admin binding for the backend ServiceAccount.**
- File: `backend/deploy/kubernetes/service-account.yaml`
- Add a `ClusterRoleBinding` (`kubepilot-api-admin`) with `roleRef`
  `ClusterRole`/`cluster-admin` and subject the `kubepilot-api` ServiceAccount in
  namespace `kubepilot`.
- Done when: the live ClusterRoleBinding is present, binds the SA to
  `cluster-admin`, and existing discovery binding/rules are unchanged; YAML is
  valid.
- **Status: done** — applied to the live Minikube cluster; `clusterrolebinding
  kubepilot-api-admin` created with `Role ClusterRole/cluster-admin` and
  `SERVICEACCOUNTS kubepilot/kubepilot-api`. `auth can-i create serviceaccounts`
  for the SA → `yes` (previously forbidden). Backend restarted with a clean
  rollout. `tests/test_rbac.py` passes (the discovery ClusterRole rules were not
  modified, only a separate binding added).

## Verify

- `cd backend && .venv/bin/python3 -m pytest` — **210 passed** (incl.
  `test_rbac.py`).
- `cd k8s-ui && yarn verify` — builds clean (no frontend change).
- YAML valid; `minikube kubectl -- get clusterrolebinding kubepilot-api-admin`
  shows the binding to `cluster-admin`.
- Live: re-run the previously failed Marketplace chart install (e.g. cert-manager)
  — it completes instead of ending with a `forbidden` error.

## Verification evidence

- `minikube kubectl -- apply -f .../service-account.yaml` →
  `clusterrolebinding.rbac.authorization.k8s.io/kubepilot-api-admin created`.
- `minikube kubectl -- get clusterrolebinding kubepilot-api-admin -o wide` →
  `kubepilot-api-admin  ClusterRole/cluster-admin ...  kubepilot/kubepilot-api`.
- `minikube kubectl -- auth can-i --as=system:serviceaccount:kubepilot:kubepilot-api create serviceaccounts --all-namespaces` → `yes`.
- Backend `pytest` → `210 passed`; `k8s-ui yarn verify` → clean.
- Ledgers `findings.md` / `review.md`: clean canonical stubs (no P0/P1).
