# Grant pod-logs and events RBAC (forbidden event tab / pod logs)

> **Type:** Fix
> **Status:** verified
> **Branch:** `fix/kubernetes-rbac-pod-logs-events`

## The problem

Opening the **Events** tab on a resource or the **Logs** tab on a pod shows
"Kubernetes access is forbidden" (the backend's `ClusterForbiddenError` message:
"Kubernetes RBAC denied the requested operation"). Root cause is RBAC, not code.

`backend/app/kubernetes/client.py` calls two Kubernetes Python API methods that
the `kubepilot-api` ServiceAccount's ClusterRole does not grant:

- **Pod logs** — `read_namespaced_pod_log` (client.py:184) requires the
  `pods/log` subresource.
- **Events** — `list_namespaced_event` (client.py:198) requires the `events`
  resource under API group `""` (core).

`backend/deploy/kubernetes/service-account.yaml` granted `pods` with
`get/list/watch` only — which does **not** imply `pods/log` — and had no
`events` rule at all. The K8s API therefore returned 403, surfaced as
"Kubernetes access is forbidden".

## The fix

Add the missing rules to the `kubepilot-api-discovery` ClusterRole in
`backend/deploy/kubernetes/service-account.yaml`:

- `resources: ["pods/log"]`, `verbs: ["get"]` under the core group, and
- `resources: ["events"]` with `get/list/watch` under the core group.

No existing rule changed and no permission reduced; the role stays read-only
(get/list/watch) and scoped to what the app reads.

## Build steps

**Step 1 — Add RBAC rules for pod logs and events.**
- File: `backend/deploy/kubernetes/service-account.yaml`
- Add `pods/log` (get) and `events` (get/list/watch) to the core-group rule.
- Done when: the applied ClusterRole includes `pods/log` get and `events`
  get/list/watch; existing rules unchanged.
- **Status: done** — applied to the live Minikube cluster
  (`minikube kubectl -- apply -f deploy/kubernetes/service-account.yaml`);
  live ClusterRole confirms `events` get/list/watch and `pods/log` get; backend
  restarted with a clean rollout. The RBAC manifest test
  (`tests/test_rbac.py::test_rbac_manifest_is_read_only_for_discovery`) was
  updated to include the two new read-only resources while still enforcing the
  read-only discovery guarantee.

## Verify

- `cd backend && PYTHONPATH=. .venv/bin/python3 -m pytest` — **210 passed**
  (including the updated `test_rbac.py`).
- `cd k8s-ui && yarn verify` — builds clean.
- `cd backend && python3 -m compileall -q app` — OK (no backend code changed).
- Live (Minikube deploy): open a pod's **Logs** tab and any resource's **Events**
  tab — they load real data instead of "Kubernetes access is forbidden".

## Verification evidence

- `minikube kubectl -- get clusterrole kubepilot-api-discovery` → rules include
  `[""] ["events"] ["get","list","watch"]` and `[""] ["pods/log"] ["get"]`.
- Backend `pytest` → `210 passed, 2 warnings`.
- `k8s-ui yarn verify` (`next build`) → clean.
- Ledgers `findings.md` / `review.md`: clean canonical stubs (no P0/P1).
