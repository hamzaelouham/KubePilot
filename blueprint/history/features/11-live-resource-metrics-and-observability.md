# Current Feature

**Status:** verified (complete)
**Type:** Feature
**Branch:** feature/live-resource-metrics-and-observability

## Goal

Feature 11 — **Live resource metrics and observability**. Today the dashboard
shows live resource summaries (status + health) but no CPU, memory, storage, or
resource-utilization figures. This feature adds real-time utilization data for
nodes and workloads by integrating the Kubernetes Metrics API (and node/PV
capacity data), then renders it **in-place within the existing Overview and
Workloads dashboard views and the existing resource detail page — no new
pages or routes are created**. Metrics appear as charts, utilization indicators,
and per-resource values on those existing surfaces, auto-refreshed via the
existing `usePolling` hook. This covers build-plan sub-items 11a (Node
metrics), 11b (Workload metrics), 11c (Storage metrics), 11d (Metrics API
integration), and 11e (Metrics UI), completed on one feature branch per the
user's explicit scope and placement decision.

## In scope

- **Metrics API integration (11d).** Backend reads the Kubernetes Metrics API
  (`metrics.k8s.io/v1beta1`) for live node and pod CPU/memory usage via the
  existing `kubernetes` client (`CustomObjectsApi`). Gracefully report a clear
  `unavailable` state when the cluster has no metrics provider (for example no
  metrics-server) instead of failing.
- **Node metrics (11a).** Per node: live CPU and memory utilization (percent and
  raw), allocatable capacity, and storage figures derived from node capacity /
  allocatable values.
- **Workload metrics (11b).** Per pod and per workload kind: CPU and memory
  usage, with namespace-level utilization summaries.
- **Storage metrics (11c).** PersistentVolume and PersistentVolumeClaim
  capacity; utilization where a supported source exists.
- **Metrics UI (11e).** Charts, utilization indicators, and per-resource
  metrics rendered **in-place inside the existing Overview and Workloads
  dashboard views and the existing resource detail page**. No new pages, tabs,
  or top-level routes are added; the metrics enrich existing surfaces.
  Auto-refresh via the existing `usePolling` hook.

## Out of scope

- **RBAC / multi-user access control** (item 12) and **multi-cluster** (item 13)
  and **AI Copilot** (item 14). Keep later features out.
- **Prometheus as a required dependency.** 11d integrates the cluster-native
  Metrics API only; Prometheus remains a later, opt-in enhancement (the
  build-plan lists it "where needed"). No new runtime dependency is added in
  this feature unless a charting library is chosen (see Open questions).
- **Per-deep filesystem usage via the kubelet** `/stats/summary` endpoint. That
  requires direct per-node access not exposed through the Python client's
  managed APIs and carries node-specific RBAC; it is out of scope. Storage
  utilization is limited to data available from node capacity/allocatable and
  PV/PVC objects, reported as `unknown` when no source exists.
- **Persisting metrics history** in PostgreSQL. Metrics remain live,
  polled-on-demand data; no schema migration and no historical retention in this
  feature.
- **New dashboard pages or routes.** Metrics render in-place inside the existing
  Overview and Workloads views and the existing resource detail page; no new
  pages are created.
- Any change to the existing `status` / `health` / `name` / `namespace` /
  `kind` / `cluster` fields or the `extra="forbid"` schemas of existing
  endpoints.

## Build loop

- Create branch `feature/live-resource-metrics-and-observability` (exact
  `Branch` value).
- `workflow.stepReview: feature` → build all small steps, then one review packet.
- `workflow.checkpointCommits: disabled` → no per-step checkpoint commits.
- Do not run the full Verify after every step; run it once after all steps pass.
- Use the installed `verify`-equivalent: backend `cd backend && .venv/bin/python
  -m pytest` plus `python3 -m compileall -q app`; frontend `cd k8s-ui && yarn
  build`. There is no project `test` command; backend pytest is the declared
  runner for logic-bearing work.

## Build steps

- [ ] 1. **Backend: add a Metrics API provider to `ClusterClient`.**
  Add a `CustomObjectsApi` to the cluster client and a
  `metrics()` / node/pod metrics reader that calls
  `metrics.k8s.io/v1beta1` (`list_cluster_custom_object` for nodes and pods).
  Introduce a dedicated `ClusterMetricsError` subclass of `ClusterClientError`
  (reusing `classify_kubernetes_error`) so the API can distinguish
  "metrics unavailable" from a real failure. Do not change existing
  resource/health responses.
  **Done when:** the client can fetch node and pod metrics and surfaces a
  specific, catchable error when the cluster has no metrics provider; the
  existing 50 backend tests still pass.

- [ ] 2. **Backend: expose a metrics endpoint with `extra="forbid"` schemas.**
  Add Pydantic response models (e.g. `NodeMetricItem`, `WorkloadMetricItem`,
  `NamespaceMetricSummary`, `MetricsResponse`) in `discovery_schemas.py` (or a
  new `metrics_schemas.py`), each with `extra="forbid"` and explicit units
  (cpu in millicores with `user`/`limit`/`usage`, memory in bytes or Mi with the
  unit named in the field). Add `GET /api/v1/cluster/metrics/nodes`,
  `.../metrics/namespaces/{namespace}` (pods/workloads), and a metrics summary
  route, all behind the existing `get_current_actor` dependency, mirroring the
  pattern in `routes.py`. Return `available: bool` + `reason` (`"unavailable"`)
  when the provider is missing, rather than a 500.
  **Done when:** the routes return the typed models, reject unknown fields via
  `extra="forbid"`, and return a 200 `available:false` shape when metrics are
  unavailable; backend tests cover the success and unavailable branches.

- [ ] 3. **Frontend: BFF metrics proxy routes.**
  Add `k8s-ui/app/api/cluster/metrics/...` route handlers mirroring the existing
  `resources/route.ts` proxy: validate the metrics "type" against a small set,
  forward the backend cookie, pass through the backend response, and return a
  503/`backend_unavailable` on fetch failure. Do not re-derive metrics
  client-side.
  **Done when:** `yarn build` passes and the proxy forwards to the backend
  metrics endpoints with cookie auth.

- [ ] 4. **Node metrics (11a): data + minimal UI in `CoreResourceView`.**
  In the `nodes` view, render per-node CPU and memory utilization, allocatable
  capacity, and storage figures from the new metrics payload. Handle the
  metrics-unavailable case with a clear inline notice (not an error page).
  **Done when:** the nodes table/list shows utilization and capacity with units,
  shows an explicit "metrics unavailable" notice when the cluster has no
  provider, and `yarn build` passes.

- [ ] 5. **Workload metrics (11b): pods and workloads + namespace summaries.**
  Add per-pod and per-workload CPU/memory usage columns (or a metrics section)
  in the pods and workload views, with a namespace-level utilization summary
  shown in `OverviewView` and the namespace selector. Handle empty and
  unavailable metrics states.
  **Done when:** pods/workloads show CPU/memory usage with units, the namespace
  summary displays correctly, empty and unavailable states render, and `yarn
  build` passes.

- [ ] 6. **Storage metrics (11c): PV/PVC capacity and utilization.**
  Surface PersistentVolume and PersistentVolumeClaim capacity from the objects;
  show utilization where a supported source exists and `unknown` otherwise (the
  cluster-native Metrics API does not provide filesystem usage). Add the
  `persistent-volume-claims` resource type to the backend resource registry and
  the frontend `columns` map / BFF `resourceTypes` if it is not already present.
  **Done when:** PV/PVC capacity renders with units, utilization shows the
  supported value or a clear "not available", and `yarn build` passes.

- [ ] 7. **Metrics UI (11e): charts and utilization indicators, in place.**
  Inside the existing Overview and Workloads dashboard views and the existing
  resource detail page (no new pages), add a lightweight chart/indicator for
  the live metrics (a small sparkline/bar for recent polled values),
  utilization indicators (color-coded via `status-tone.ts` or a new tone map),
  and per-resource metric rows. Wire auto-refresh to the existing `usePolling`
  hook. Prefer a minimal, dependency-light chart implementation unless a
  library is explicitly approved. Do not add new tabs, routes, or pages.
  **Done when:** metrics render with charts/indicators **on the existing
  Overview and Workloads views and the detail page**, auto-refresh updates them
  via `usePolling`, empty/unavailable states are handled, no new page/route is
  added, and `yarn build` passes.

## Files / areas

- `backend/app/kubernetes/client.py` — add `CustomObjectsApi` + `metrics()`
  reader and `ClusterMetricsError`; keep existing resource/health logic intact.
- `backend/app/kubernetes/__init__.py` — export any new error type.
- `backend/app/api/v1/discovery_schemas.py` or new
  `backend/app/api/v1/metrics_schemas.py` — `extra="forbid"` metric response
  models with explicit units.
- `backend/app/api/v1/routes.py` — `/cluster/metrics/...` endpoints behind
  `get_current_actor`, mirroring existing route patterns.
- `backend/tests/test_kubernetes.py` (+ optionally a new metrics test module) —
  focused tests for the metrics reader success, unavailable, and unit-shaping
  branches using the existing fake/object fixture style.
- `k8s-ui/app/api/cluster/metrics/.../route.ts` (new) — BFF proxy mirroring
  `resources/route.ts`.
- `k8s-ui/components/core-resource-view.tsx` — node/workload/PV metrics
  rendering + unavailable/empty states.
- `k8s-ui/components/overview-view.tsx` — namespace utilization summary.
- `k8s-ui/components/resource-detail-view.tsx` — per-resource metrics on detail.
- `k8s-ui/lib/status-tone.ts` or a new `k8s-ui/lib/metrics.ts` — unit formatting
  and utilization tone mapping (shared helper per the `lib/` convention).

No DB migration, no new required environment variables. The Metrics API is
cluster-native; metrics-server presence is a cluster/environment matter, not a
code config value.

## Data / contracts

New additive endpoints under `/api/v1/cluster/metrics/...`, each response with
`extra="forbid"`:

- `{available: boolean}` plus per-metric fields, with `available:false` and a
  `reason: "unavailable"` when no metrics provider is reachable.
- CPU units are **millicores** (e.g. `250m`); memory units are **bytes** with the
  field named to state units. Values are non-negative numbers or null when the
  cluster provides no value.
- Node metrics expose cpu/memory `usage` and the node's `allocatable`/
  `capacity` for cpu, memory, and storage(ephemeral-storage) where present.
- Workload metrics expose pod cpu/memory `usage` and workload/namespace summary
  aggregates.
- Storage metrics expose PV/PVC `capacity`; `utilization` is null/`unknown`
  when the standard client APIs do not provide it.

The existing `/cluster/resources/...` response and `ResourceItem` schema are
unchanged; metrics are a separate endpoint family, not fields bolted onto the
resource summary.

## Testing

- **Backend (`logicTests: when-configured`):** pytest is configured (use
  `backend/.venv/bin/python -m pytest`). Add focused unit tests for the metrics
  reader using existing fake/object fixture style: node/pod metrics parse,
  unavailable-provider branch surfaces `available:false` (or a
  `ClusterMetricsError`), unit shaping (millicore / bytes) is exact, and the
  `extra="forbid"` schemas reject unknown fields. Run
  `python3 -m compileall -q app`. Do not add brittle tests for UI.
- **Frontend (`uiEvidence: when-available`):** no test runner is configured.
  Proof is the build (`cd k8s-ui && yarn build`) plus manual browser
  verification against the running app: view nodes/pods/workloads/PV/PVC,
  confirm utilization + capacity render, confirm the metrics-unavailable notice
  shows when metrics-server is absent, confirm auto-refresh updates values.

## Notes for the AI

- Backend owns all metrics semantics (it holds the cluster client). The frontend
  only renders returned values and units; do not re-derive utilization in the
  browser.
- Preserve `extra="forbid"` on every new response model and state units in field
  names so no later work reinterprets a value.
- Reuse the existing `usePolling` hook and `lib/` shared-helper convention;
  follow the current `"use client"` + `fetch` + `AbortController` pattern in the
  views.
- Keep failures flowing to the existing `error`/`role="alert"` render paths, but
  surface "metrics unavailable" as an informational notice distinct from a hard
  resource load error.
- The Metrics API returns 404/403/503 when metrics-server (or a compatible
  provider) is not installed. Route that to the graceful `available:false`
  state, and do not treat it as a cluster outage.
- Do not add Prometheus or a charting dependency unless the user approves it
  (see Open questions). Prefer a minimal, hand-rolled lightweight indicator.

## Open questions

- **Charting approach (11e).** Whether to render the small charts with a
  dependency-light hand-rolled SVG/sparkline (default, repository-native, no new
  runtime dep) or add a charting library. The default is the hand-rolled
  approach; a library is a reversible presentation choice, so it does not block,
  but should be confirmed during review if changes.
- **Live series / time ranges (11e).** Metrics render live and in-place within
  the existing Overview/Workloads views; there is no page or time-range control
  for stored history in this feature (historical retention is out of scope). Any
  "recent" indication is limited to the current poll cycle rather than implying
  a persisted series. Confirm this stays in place during review.
- **Storage utilization source (11c).** The cluster-native Metrics API does not
  expose filesystem/PV utilization. The spec reports capacity and marks
  utilization `unknown` when no supported source exists. If the user requires
  actual utilization, that is a follow-up (likely kubelet or a metrics
  provider), not part of this feature.

The implementation can begin against the above defaults without further
product decisions; the defaults are recorded and reversible.
