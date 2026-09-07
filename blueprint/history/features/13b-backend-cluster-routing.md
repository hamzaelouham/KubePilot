# Current Feature

**Status:** verified (complete)
**Type:** Feature
**Branch:** feature/multi-cluster-cluster-routing

## Goal

Feature 13b — **Backend cluster routing.** Make the existing single-cluster
`/api/v1/cluster/*` routes cluster-aware: each route accepts an optional
`?cluster=<name>` query param, resolves that name to the corresponding
`ClusterConnection` row, builds a Kubernetes client for that cluster (in-cluster
for the seeded default, kubeconfig-from-store for registered clusters), and
serves namespaces/resources/details/metrics from the selected cluster. Unknown
names return 404; a resolved cluster whose kubeconfig fails to load returns 503.
With no `?cluster` param, the default in-cluster cluster is used (backward
compatible with the current single-cluster behavior).

## In scope

- **Cluster resolution in `get_cluster_client`.** Replace the current
  `get_cluster_client(settings)` dependency in `app/core/dependencies.py` with a
  cluster-aware version. It keeps the same function name and module path (so the
  47 existing `app.dependency_overrides[get_cluster_client]` test overrides keep
  working) but reads the `cluster` query param from `request`, resolves it to a
  `ClusterConnection` row by name, and builds the client. New signature:
  `get_cluster_client(request, database, settings)`.
  - No `?cluster` param → resolve to the default cluster whose `name ==
    settings.cluster_name` (the seeded `primary`); use in-cluster loading.
  - `?cluster=<name>` matching a row with `kubeconfig_content is None` →
    in-cluster loading (the default cluster).
  - `?cluster=<name>` matching a row with non-null `kubeconfig_content` →
    load kubeconfig-from-content.
  - `?cluster=<name>` matching **no** row → raise `HTTPException(404)` with
    `code="cluster_not_found"`.
  - A row that resolves but whose kubeconfig fails to load/parse/connect →
    raise `ClusterUnavailableError` (→ 503 `cluster_unavailable`).
- **`create_cluster_client` kubeconfig support.** Extend
  `create_cluster_client(settings, loader=...)` in `app/kubernetes/client.py` to
  support two modes:
  - Default in-cluster: current behavior via `config.load_incluster_config()`.
  - Kubeconfig-from-content: accept an optional `kubeconfig_content` argument;
    when provided, call `config.load_kube_config_from_dict(yaml.safe_load(...))`
    instead of the in-cluster loader before building the API clients.
  - Both modes build the same `ClusterClient(name, core, apps, batch, rbac,
    storage, metrics_api)`.
- **Create API clients after config load.** The `client.CoreV1Api()` etc. must be
  constructed **after** the config loader runs (both modes), as they are today.
- **Wire all `/api/v1/cluster/*` routes.** The 9 routes that use
  `Depends(get_cluster_client)` (status, namespaces, resources, detail, yaml,
  logs, events, metrics/nodes, metrics/namespaces, metrics/summary, metrics/storage)
  continue to use `Depends(get_cluster_client)`; no route code changes needed
  because the dependency itself becomes cluster-aware. Confirm each route's
  `_validate_detail_scope` / scope logic still applies against the resolved
  cluster name.
- **`_validate_detail_scope` alignment.** The detail routes validate
  `cluster == settings.cluster_name`. Update this to compare against the
  resolved client's cluster name (the row's `name`), so a registered cluster's
  detail requests validate correctly. Read the `cluster` query param name via
  the same mechanism as `get_cluster_client`.
- **Unit tests.** Add `backend/tests/test_cluster_routing.py` covering:
  1. No `?cluster` param → default in-cluster cluster is used (client built with
     `settings.cluster_name`).
  2. `?cluster=<missing>` → 404 `cluster_not_found`.
  3. `?cluster=<default>` with `kubeconfig_content=None` → in-cluster path.
  4. `?cluster=<registered>` with valid `kubeconfig_content` → client built
     from stored kubeconfig, endpooint endpoint matches.
  5. Invalid/unloadable kubeconfig content on a registered cluster → 503
     `cluster_unavailable`.
  6. `create_cluster_client` with `kubeconfig_content` loads from dict.
  7. Existing detail-scope validation still rejects namespace-less
     non-node resources (regression guard).

## Out of scope

- **Frontend cluster selector (13c).** No frontend changes; the frontend already
  sends `?cluster=` on detail routes and will send it on others in 13c.
- **Admin cluster management page (13d).** No UI.
- **Cluster health checks or status polling.** The `status` field is not
  actively monitored.
- **Per-user cluster permissions.** All authenticated users with
  `CLUSTERS_READ`/`RESOURCES_READ` can access any registered cluster.
- **Cluster deletion or disabling.** Future.
- **Metrics via Prometheus per cluster.** Only the existing Metrics API path is
  made cluster-aware.

## Build loop

- Create branch `feature/multi-cluster-cluster-routing` (exact `Branch` value).
- `workflow.stepReview: feature` — build all small steps, then one review packet.
- `workflow.checkpointCommits: disabled` — no per-step checkpoint commits.
- Backend Verify: `cd backend && PYTHONPATH=. python3 -m compileall -q app && PYTHONPATH=. python3 -m pytest`.
- Frontend Verify unchanged: `cd k8s-ui && yarn build` (no frontend changes).

## Build steps

- [x] 1. **Extend `create_cluster_client` for kubeconfig-from-content.** In
  `backend/app/kubernetes/client.py`, add an optional `kubeconfig_content: str |
  None = None` parameter to `create_cluster_client`. When provided, load config
  via `config.load_kube_config_from_dict(yaml.safe_load(kubeconfig_content))`;
  otherwise keep the default in-cluster loader. Build the API clients after the
  loader in both modes.
  **Done when:** `python3 -m compileall -q app` passes, and a unit test confirms
  `create_cluster_client` accepts `kubeconfig_content` (loading from dict) versus
  the default in-cluster path.

- [x] 2. **Add the cluster-resolution helper.** In `backend/app/core/dependencies.py`,
  add a `_resolve_cluster(request, database, settings) -> tuple[str, str | None]`
  helper that returns `(cluster_name, kubeconfig_content)`:
  - Read `cluster` from `request.query_params`; default to `settings.cluster_name`
    when absent.
  - Look up `ClusterConnection` by name; on missing → `HTTPException(404,
    cluster_not_found)`.
  - Return `(row.name, row.kubeconfig_content)`.
  **Done when:** `python3 -m compileall -q app` passes.

- [x] 3. **Make `get_cluster_client` cluster-aware.** Rewrite
  `get_cluster_client` in `backend/app/core/dependencies.py` to:
  `def get_cluster_client(request, database, settings) -> ClusterClient`.
  Resolve the cluster via the helper, call `create_cluster_client(settings,
  kubeconfig_content=...)`, and return the client. Wrap unloadable config errors
  as `ClusterUnavailableError`. Keep the same function name/module so existing
  `dependency_overrides[get_cluster_client]` overrides continue to intercept.
  **Done when:** `python3 -m compileall -q app` passes, and the 47 existing
  kubernetes tests still pass (their overrides must remain effective).

- [x] 4. **Update `_validate_detail_scope` for resolved cluster names.** In
  `backend/app/api/v1/routes.py`, change `_validate_detail_scope(resource_type,
  cluster, settings, namespace)` to validate the provided `cluster` name against
  the resolved client's `cluster_name` (passed in) instead of
  `settings.cluster_name`. Pass the resolved client name where called.
  **Done when:** `python3 -m compileall -q app` passes, and the existing
  resource-detail tests still pass.

- [x] 5. **Add cluster routing unit tests.** Create
  `backend/tests/test_cluster_routing.py` covering the 7 scenarios in In scope,
  using a fake DB with a seeded default row and a registered row, overriding
  `create_cluster_client` where needed to observe the selected cluster name /
  kubeconfig path.
  **Done when:** all new tests pass.

- [x] 6. **Run full verification.** Run
  `cd backend && PYTHONPATH=. python3 -m compileall -q app && PYTHONPATH=. python3 -m pytest`
  and `cd k8s-ui && yarn build`.
  **Done when:** compileall passes, all pytest tests pass, frontend build clean.

## Files / areas

- `backend/app/core/dependencies.py` — cluster-aware `get_cluster_client` + resolution helper.
- `backend/app/kubernetes/client.py` — `create_cluster_client` kubeconfig-from-content.
- `backend/app/api/v1/routes.py` — `_validate_detail_scope` cluster-name alignment.
- `backend/tests/test_cluster_routing.py` (new) — routing unit tests.
- `backend/tests/test_kubernetes.py` — existing tests must remain green (override pattern preserved).

## Data / contracts

- **`?cluster` query param** on every `/api/v1/cluster/*` route carries the
  cluster **name** (not id). This matches current frontend behavior
  (`?cluster=KUBEPILOT_CLUSTER_NAME` on detail routes).
- Default when `?cluster` is absent: the cluster whose `name ==
  settings.cluster_name` (the seeded `primary`, `kubeconfig_content=None` →
  in-cluster).
- **`ClusterConnection.kubeconfig_content`** (from 13a): when non-null, the raw
  kubeconfig YAML is loaded via `config.load_kube_config_from_dict`.
- Error codes:
  - 404 `cluster_not_found` — `?cluster=<name>` has no matching row.
  - 503 `cluster_unavailable` — a resolved cluster's kubeconfig fails to
    load/parse/connect.
  - Existing 403/422/502/500 handlers unchanged.
- **`create_cluster_client(settings[, kubeconfig_content])`** — new optional
  parameter; behavior otherwise unchanged for the in-cluster default.

## Testing

- **Backend (`logicTests: when-configured`):** `cd backend && PYTHONPATH=. python3 -m compileall -q app` and `PYTHONPATH=. python3 -m pytest`.
- **Frontend:** `cd k8s-ui && yarn build` (no changes, must still pass).
- **Manual (none in this sub-feature).** The frontend already sends `?cluster=`
  on detail routes; cluster-aware responses are exercised by the unit tests.

## Notes for the AI

- **Preserve the `get_cluster_client` function identity.** The 47 existing tests
  do `app.dependency_overrides[get_cluster_client] = lambda: ...`. The override
  replaces the dependency entirely, so changing the real function's signature is
  fine — but do not rename or relocate the function. FastAPI resolves overrides
  by function object identity, so the module path and function name must stay
  `app.core.dependencies.get_cluster_client`.
- Do not modify any route's `Depends(get_cluster_client)` reference — the
  dependency becoming cluster-aware is the change; routes stay as they are.
- `request.query_params.get("cluster")` returns the raw string; default to
  `settings.cluster_name` when absent or empty. A `?cluster=` present but with a
  name that has a row must not be rejected.
- For kubeconfig-from-content, use `from kubernetes import config` and call
  `config.load_kube_config_from_dict(yaml.safe_load(content))`. `yaml` is already
  imported in `client.py`.
- The detail routes currently pass `cluster: str` (the query name) as a separate
  FastAPI param. `_validate_detail_scope` compares it against `settings.cluster_name`.
  Change only the comparison target to the resolved client's `cluster_name`; do not
  change the routing or URL shape.
- Do not start a dev server. Tests use the in-memory/sqlite DB and dependency
  overrides.

## Open questions

- None. All material choices (cluster identified by name in `?cluster=`, in-cluster
  for the seeded default, kubeconfig-from-content for registered clusters, 404 for
  unknown / 503 for unloadable, backward-compatible default) are reversible internal
  decisions consistent with existing frontend behavior and the 13a data model.