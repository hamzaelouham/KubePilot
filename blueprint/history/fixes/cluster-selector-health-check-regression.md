# Current Feature

> **Generated file.** Holds the one feature, fix, or rollback being built right now. Run
> `/feature <number-or-name>` to spec a build-plan feature, or `/fix "<bug>"` for
> an ad-hoc fix. Use `/rollback <completed-feature>` to plan a safe reversal.
> Build one thing at a time; `/complete` archives it under
> `blueprint/history/` and resets this file.

## Fix: cluster selector regression after health-check commit

**Type:** Fix
**Status:** verified
**Branch:** `fix/cluster-selector-health-check-regression`
**Fixes:** —
**Parent item:** —

### The problem

Commit `f7b485b` ("fix: refresh cluster connection health") introduced a live
Kubernetes API probe (`list_namespace(limit=1, _request_timeout=5)`) into
`GET /api/v1/clusters`, called synchronously for every registered active
cluster on every request (`routes.py:_connection_status`). The frontend
selector in `use-cluster-selection.ts` was updated to filter on
`connection_status === "connected"`.

Two regressions result:

1. **Empty selector on probe failure.** When any health probe returns
   `"unavailable"` or `"forbidden"` — network blip, slow API server, RBAC
   issue — that cluster is excluded from the header selector and every
   resource view. If all probes fail, the header shows "Cluster unavailable"
   and the dashboard is blank, with no user recourse.

2. **Latency on every list request.** `connection_status` is recomputed via
   live probes on each `GET /api/clusters` call. With two clusters and slow
   probes, this adds 600ms+ to every cluster-list request; the frontend's
   `useClusterSelection` fetch runs on every dashboard mount and the
   cluster-management page runs its own fetch, so the cost multiplies.

### The fix

Remove the synchronous per-cluster health probe from the list endpoint and
move it to an explicit, on-demand refresh the user or UI can trigger without
blocking the list response.

**Backend changes:**

- Remove `_connection_status()` and the per-cluster `health()` call from
  `GET /api/v1/clusters`. The list endpoint returns only the persisted
  `status` field (`active` / `inactive`), as it did before `f7b485b`. This
  restores the fast, pure-DB read.
- Add a new lightweight endpoint `GET /api/v1/clusters/{id}/health` (or
  extend the existing cluster-management backend) that returns the live
  `connection_status` for a single cluster without blocking the list.
- Preserve the existing `_connection_status()` helper and
  `ClusterClient.health()` method; they remain available for the dedicated
  health endpoint and any future per-cluster checks.

**Frontend changes:**

- Revert the `use-cluster-selection.ts` filter to only check
  `status === "active"`, removing the `connection_status === "connected"`
  requirement. The header selector once again lists all administratively
  active clusters.
- In `clusters-management.tsx`, fetch each cluster's live health status in
  the background (after the main list loads) via the new per-cluster health
  endpoint, and display the badge from the result without blocking the table.
  If the health endpoint is unreachable or slow, the badge defaults to a
  neutral "checking…" state instead of hiding the cluster.
- Keep the existing `statusBadge()` logic (connected / unavailable /
  forbidden / inactive) unchanged; only the data source changes from
  synchronous-list to on-demand.

**What the fix must not break:**

- Administratively inactive clusters must stay hidden from the selector
  (current behavior).
- The cluster-management page must still show live connection status badges.
- No new database tables, no new Alembic migrations, no new background
  workers.

### Build steps

- [x] **Step 1 — Backend: remove health probe from list endpoint, add
  per-cluster health endpoint**
  - Remove the `settings` dependency and `_connection_status()` call from
    `cluster_list` in `routes.py`. The response model reverts to only
    `id`, `name`, `endpoint`, `status`, `created_at` (drop
    `connection_status` from `ClusterSummary`; keep the field on the
    response model but set it to `"unknown"` for the list endpoint, or
    remove it entirely — whichever keeps the diff smallest).
  - Add `GET /api/v1/clusters/{cluster_id}/health` that loads the
    `ClusterConnection` row, calls `_connection_status()`, and returns
    `{ "connection_status": "connected" | "unavailable" | "forbidden" }`.
  - Gate the new endpoint behind `CLUSTERS_READ`.
  - **Done when:** `GET /api/v1/clusters` returns instantly without
    `connection_status` and `GET /api/v1/clusters/{id}/health` returns
    the live probe result for a single cluster.

- [x] **Step 2 — Frontend: revert selector filter, add on-demand health
  badges**
  - In `use-cluster-selection.ts`, remove `connection_status === "connected"`
    from the filter; restore `item.status === "active"` only.
  - In `clusters-management.tsx`, after the main cluster list loads, fire
    parallel `fetch("/api/v1/clusters/{id}/health")` calls for each cluster
    and update each row's badge from the response. Show a neutral
    "Checking…" badge while in-flight; fall back to "Unavailable" on error.
  - **Done when:** the header selector shows all active clusters regardless
    of probe state, and the cluster-management page shows live health
    badges loaded in the background without blocking the table render.

### Verify

- `GET /api/v1/clusters` returns in < 50ms with no `connection_status`
  field (or `"unknown"`).
- `GET /api/v1/clusters/{id}/health` returns `"connected"` for a reachable
  cluster.
- Header cluster selector lists all `status: "active"` clusters.
- Cluster-management page shows live "Connected" / "Unavailable" badges.
- Background badge fetch does not block the initial table render.
- `yarn build` passes; `python3 -m compileall -q app` passes.
