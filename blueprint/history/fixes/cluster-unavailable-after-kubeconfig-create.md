# Cluster created from kubeconfig reports "unavailable"

> **Type:** Fix
> **Status:** verified
> **Branch:** `fix/cluster-unavailable-after-kubeconfig-create`

## The problem

Registering a new cluster by pasting a kubeconfig file succeeds, but the cluster
then reports `503 Kubernetes cluster is unavailable` on every status/resource
call, so it can never be used.

Reproduced against the live environment (backend pod running on Minikube,
`kubectl config view --context kind-kind --raw`):

- The backend pod on Minikube cannot reach a kubeconfig API server bound to the
  host loopback. From inside the pod, `https://127.0.0.1:40393` (kind) and
  `https://127.0.0.1:32771` (minikube) are both **UNREACHABLE**. A kind kubeconfig
  pasted into the create form points at exactly that loopback URL, so the first
  request after creation fails with `ClusterUnavailableError` → HTTP 503.
- `POST /api/v1/clusters` (`backend/app/api/v1/routes.py:541`) only does
  structural YAML checks via `_parse_kubeconfig` (routes.py:485), then commits
  the row as `status="active"` (routes.py:585-593) with **no connectivity check**.
  The failure surfaces only later, in a generic form, with no actionable reason.
- `_parse_kubeconfig` stores the server of `clusters[0]` as the cluster
  `endpoint` (routes.py:505-518), ignoring the kubeconfig `current-context`. On
  this machine the real `~/.kube/config` lists `minikube` first but has
  `current-context: kind-kind` (`kubectl config view` sorts clusters, hiding the
  file order). Proven: registering the full config stored endpoint
  `https://127.0.0.1:32771` (minikube) while the client actually connects to
  kind (`https://127.0.0.1:40393`).
- A kubeconfig with a missing `current-context`, or whose context references a
  missing cluster/user, also passes creation silently and fails only at request
  time (`load_kube_config_from_dict` raises `ConfigException`, caught at
  `backend/app/kubernetes/client.py:332` → generic `ClusterUnavailableError`).

## The fix

Make cluster registration honest and diagnosable:

1. **Resolve the endpoint from the active context.** `_parse_kubeconfig` picks
   the server of the `current-context`'s cluster (not `clusters[0]`), so the
   stored `endpoint` is the cluster actually used. Missing `current-context` or
   an unresolvable context/cluster is a `422 invalid_kubeconfig` at creation,
   not a surprise at request time.
2. **Probe connectivity at creation.** After structural validation, build the
   client with the pasted content through the same code path the resources use
   (`create_cluster_client` + a lightweight namespaces call) and only commit a
   `status="active"` row when it connects. On failure, return a clear error
   (e.g. `502`/`422`) quoting the underlying cause — host unreachable, TLS,
   credentials, or the "API server bound to localhost but the backend runs
   inside Minikube/pod" case — and do not create the row.
3. **Surface the cause in runtime errors.** Include the underlying reason
   (connection refused / timeout / TLS / 403) in `ClusterUnavailableError`'s
   message instead of the flat "cluster is unavailable", without changing the
   HTTP status mapping.

Keep single-cluster and the existing behaved kubeconfigs working. Do not change
how active/inactive status routing works. Existing create tests
(`tests/test_cluster_management.py`) use a bogus non-routable server
(`https://10.0.0.1:6443`) with matching `clusters[0]` and `current-context`, so
the endpoint assertion stays valid; the new probe must be injectable/mockable so
those tests keep passing without a live cluster.

## Build steps

- **Step 1 — active-context endpoint resolution.** Update `_parse_kubeconfig`
  to read `current-context` and resolve its cluster's `server`; reject missing/
  broken `current-context` with `422 invalid_kubeconfig`.
  Done when: registering the real multi-cluster `~/.kube/config` stores the
  kind (active-context) server, and new tests cover multi-cluster + missing
  `current-context`. ✅
- **Step 2 — creation-time connectivity probe.** Wire a probe into
  `cluster_create` after parse, before commit; return a clear error on failure.
  Done when: posting the loopback kind kubeconfig is rejected with a message
  that names the reachability problem, and existing create tests pass with the
  probe overridden. ✅
- **Step 3 — runtime error detail.** Add the underlying reason to the
  `ClusterUnavailableError` message raised by `create_cluster_client`.
  Done when: a `503` body identifies host/TLS/credential cause. ✅
- **Step 4 — test + review pass.** `pytest` + the `Verify` command pass; manual
  kind-cluster reproduction shows the clear error. ✅

## Runtime note (live-validated)

The kind endpoint is reachable from the backend pod only after attaching the
kind node to Minikube's Docker bridge and rewriting the kubeconfig `server` to
the resulting `192.168.49.x` address. See
`docs/connecting-sibling-kind-cluster.md` for the exact recipe, evidence table,
and the `insecure-skip-tls-verify` trade-off (client-cert auth/RBAC unaffected).
Validated live: the backend pod connects to kind via the rewritten kubeconfig
and lists namespaces; a host-run backend on the current code registers it with
`status=active`, and `/cluster/namespaces`, `/cluster/resources/pods`,
`/cluster/resources/nodes` return real kind data.

## Verify

- `cd backend && .venv/bin/python3 -m pytest`
- Root project `Verify` command: `cd backend && .venv/bin/python3 -m pytest && cd k8s-ui && yarn verify`.
- Manual, running app: paste `kubectl config view --context kind-kind --raw`
  into **Settings → Clusters → Register cluster**. Expect a clear rejection
  naming the unreachable server (backend pod cannot reach host-loopback), not a
  silent "active" cluster that later shows `503 Kubernetes cluster is
  unavailable`.
- Backend on the host instead of the pod: same paste succeeds; the cluster list
  shows the kind server (`https://127.0.0.1:40393`) as `endpoint`, and status
  returns `connected`.