# Current Feature

**Status:** verified
**Type:** Feature
**Branch:** feature/admin-cluster-management-page

## Goal

Feature 13d — **Admin cluster management page.** Add `/settings/clusters`: a
table of registered clusters, a form to register a new cluster, and an
activate/deactivate toggle. Per user decisions:

- **Authorization follows the shipped RBAC matrix**, not the build plan's
  "admin-only" wording: listing is `clusters:read` (all roles), register and
  toggle are `clusters:create` / `clusters:update` (operator + admin). The
  frontend hides manage actions for viewers; the backend still enforces 403.
- **Deactivate means hide from selector + routing.** An `inactive` cluster is
  excluded from the 13c header selector list, stale selections reset to the
  first active cluster, and named cluster API requests return the existing
  `cluster_not_found` error until reactivated.

## In scope

- **Backend toggle endpoint.** `PATCH /api/v1/clusters/{cluster_id}` accepting
  `{ "status": "active" | "inactive" }`, gated by
  `Permission.CLUSTERS_UPDATE` (operator + admin). Reuses the existing
  `ClusterConnection.status` column — no schema change, no migration. Unknown
  id → 404 `cluster_not_found`. Invalid status value → 422. Successful toggle
  records a new audit event `cluster.status_change` (added to `AuditEvent`) with
  the actor id and cluster resource id, mirroring `CLUSTER_CREATED`.
- **Routing rejects inactive clusters.** `get_cluster_client`
  (`backend/app/core/dependencies.py`) returns 404 `cluster_not_found` when the
  resolved `ClusterConnection.status` is `inactive`, so all cluster routes
  (`namespaces`, `resources`, `metrics`, `status`, `details`) refuse the cluster
  until it is reactivated. A missing row keeps its existing 404 behavior.
- **List unchanged.** `GET /api/v1/clusters` keeps returning clusters of every
  status (the management table and the selector both read it; the selector
  filters client-side).
- **Frontend proxies.** `app/api/clusters/route.ts` gains `POST` (register, JSON
  body `{ name, kubeconfig_content }`, mirroring `/api/users` POST). New
  `app/api/clusters/[id]/route.ts` with `PATCH` (toggle, mirroring
  `/api/users/[id]` PATCH).
- **Settings page + management UI.** New `app/settings/clusters/page.tsx`
  (server: `requireBackendUser()`, computes `canManage` from role operator/admin,
  no admin redirect) rendering `components/cluster-settings-view.tsx` →
  `components/clusters-management.tsx` (client, modeled on `users-management.tsx`):
  - Table columns: Name, Endpoint, Status (badge), Created, Actions.
  - Register: "create cluster" button opening a Dialog with a Name input and a
    kubeconfig textarea; POSTs JSON. Shown only when `canManage`.
  - Toggle: Deactivate / Reactivate button per row calling the PATCH proxy;
    shown only when `canManage`.
  - Loading, empty ("No clusters yet."), 401 → `/login`, 503 unavailable, and
    inline error states matching `users-management.tsx`.
  - Viewers (`canManage=false`) see the read-only table without create/toggle
    controls; the backend independently returns 403 for their write attempts.
- **Sidebar entry.** `dashboard-shell.tsx` adds a "Clusters" link in the
  Administration group (visible to all logged-in users, following the Users /
  Password grouping) and an `activeResource`/title entry for `clusters`.
- **Selector filter (13c integration).** `lib/use-cluster-selection.ts` keeps
  each listed cluster's `status` and lists only `status === "active"` clusters
  in the header selector. Its existing stale-selection reset already drops
  deactivated selections to the first active cluster. `localStorage` key and URL
  `?cluster=` handling are unchanged.

## Out of scope

- **Cluster delete / edit.** No `DELETE` endpoints, no kubeconfig editing after
  register. The build plan does not request them.
- **Backend multipart create path.** The register form posts JSON
  (`name` + `kubeconfig_content` textarea); the existing multipart upload test
  path stays as-is.
- **Changing the 13a/13b role matrix.** Operator keeps `clusters:create` and
  `clusters:update`; no new admin-only permission is introduced.
- **Live status/health of clusters**, selector status badges, or connection
  tests beyond the existing toggle semantics.
- **User, auth, notifications, user menu, `+` header button** — untouched.
- **The `/settings/password` page** — untouched.

## Build loop

- Create branch `feature/admin-cluster-management-page`.
- `workflow.stepReview: feature` — build all small steps, then one review packet.
- `workflow.checkpointCommits: disabled` — no per-step checkpoint commits.
- Backend: `cd backend && PYTHONPATH=. python3 -m compileall -q app && PYTHONPATH=. .venv/bin/python3 -m pytest`.
- Frontend: `cd k8s-ui && yarn build`.
- Do not start a dev server. Focused backend tests are added with logic steps
  (the backend pytest runner is configured; the frontend has none).

## Build steps

- [x] 1. **Add the backend toggle endpoint.** In `backend/app/api/v1/routes.py`
  add `PATCH /api/v1/clusters/{cluster_id}` (path `UUID`, gated by
  `require_permission(Permission.CLUSTERS_UPDATE)`) accepting
  `ClusterStatusUpdateRequest { status: "active" | "inactive" }`, updating
  `ClusterConnection.status`, returning `ClusterSummary`, and recording the new
  `AuditEvent.CLUSTER_STATUS_CHANGED = "cluster.status_change"` (add it in
  `backend/app/core/audit.py` alongside `CLUSTER_CREATED`). Unknown id → 404
  `cluster_not_found`; invalid status value → 422 `validation_error`.
  Add `ClusterStatusUpdateRequest` to `backend/app/api/v1/cluster_schemas.py`.
  **Done when:** focused pytest passes (activate/deactivate round-trip returns
  `ClusterSummary` and persists the row status; unknown id 404; viewer 403;
  invalid status 422; a `cluster.status_change` `AuditAction` row is recorded).

- [x] 2. **Reject inactive clusters at the routing boundary.** In
  `backend/app/core/dependencies.py`, `get_cluster_client`: after the name
  lookup, when `row.status` is not `"active"` and not the pre-13d default
  `"unknown"`, i.e. specifically when `row.status == "inactive"`, raise 404
  `cluster_not_found` (same code/message as a missing row).
  **Done when:** focused pytest passes — a cluster toggled to `inactive` makes
  `GET /api/v1/cluster/namespaces?cluster=<name>` return 404 `cluster_not_found`
  while `GET /api/v1/clusters` still lists it; reactivating restores 200. All
  existing routing tests (default `primary` = `active`) still pass.

- [x] 3. **Add the frontend proxy routes.** Add `POST` to
  `k8s-ui/app/api/clusters/route.ts` (JSON passthrough mirroring `/api/users`
  POST, 503 `backendUnavailable` on catch) and create
  `k8s-ui/app/api/clusters/[id]/route.ts` with `PATCH` (mirroring
  `/api/users/[id]` PATCH).
  **Done when:** `yarn build` passes and the routes are registered in the build
  output.

- [x] 4. **Build the `/settings/clusters` page.** Create
  `k8s-ui/app/settings/clusters/page.tsx` (server: `requireBackendUser()`,
  `canManage = user.role === "admin" || user.role === "operator"`).
  Create `components/cluster-settings-view.tsx` (renders `DashboardShell` with
  `activeResource="clusters"`, `useClusterSelection` for the header selector,
  and `ClustersManagement` as children). Create `components/clusters-management.tsx`
  on the `users-management.tsx` pattern: fetch `/api/clusters`, render the
  table (Name / Endpoint / Status / Created / Actions), the "create cluster"
  dialog (Name + kubeconfig textarea → `POST /api/clusters`), the per-row
  Deactivate/Reactivate toggle → `PATCH /api/clusters/{id}` with
  `{ "status": "inactive" | "active" }`, `canManage`-gating of both actions, and
  the loading / empty / 401 / 503 / error states. In `dashboard-shell.tsx` add
  the Administration "Clusters" link (all logged-in users) and a
  `resourceTitles` entry for `clusters`.
  **Done when:** `yarn build` passes; the nav renders the Clusters link and the
  page compiles.

- [x] 5. **Filter the header selector to active clusters.** In
  `k8s-ui/lib/use-cluster-selection.ts`, read `status` from each
  `/api/clusters` item and list only `status === "active"` names in the hook's
  cluster list/selection resolution. Keep the `localStorage` key, resolution
  order, and stale-selection reset unchanged.
  **Done when:** `yarn build` passes; `grep -rn "items\|status" lib/use-cluster-selection.ts`
  confirms the filter; single-cluster and stored-selection behavior are
  unchanged.

- [x] 6. **Run full verification.**
  `cd backend && PYTHONPATH=. python3 -m compileall -q app && PYTHONPATH=. .venv/bin/python3 -m pytest`
  and `cd k8s-ui && yarn build`.
  **Done when:** compileall + all backend pytest pass, frontend build clean.

## Files / areas

- `backend/app/api/v1/routes.py` — `PATCH /clusters/{cluster_id}`.
- `backend/app/api/v1/cluster_schemas.py` — `ClusterStatusUpdateRequest`.
- `backend/app/core/audit.py` — `CLUSTER_STATUS_CHANGED`.
- `backend/app/core/dependencies.py` — inactive routing rejection.
- `backend/tests/test_cluster_management.py`,
  `backend/tests/test_cluster_routing.py` — new tests.
- `k8s-ui/app/api/clusters/route.ts` — add `POST`.
- `k8s-ui/app/api/clusters/[id]/route.ts` — new `PATCH`.
- `k8s-ui/app/settings/clusters/page.tsx` — new server page.
- `k8s-ui/components/cluster-settings-view.tsx`,
  `k8s-ui/components/clusters-management.tsx` — new.
- `k8s-ui/components/dashboard-shell.tsx` — Administration "Clusters" link +
  `resourceTitles["clusters"]`.
- `k8s-ui/lib/use-cluster-selection.ts` — active-only selector filter.

## Data / contracts

- **Toggle request/response.** `PATCH /api/v1/clusters/{cluster_id}` body
  `{ "status": "active" | "inactive" }` (any other value → 422
  `{ code: "validation_error" }`). Response is the updated `ClusterSummary`
  (`{ id, name, endpoint, status, created_at }`). Errors: 404
  `cluster_not_found` (unknown id), 401 `authentication_required`, 403
  `insufficient_permissions`. Requires `clusters:update`.
- **Status values.** `ClusterConnection.status` is reused: `"active"` and
  `"inactive"` are toggleable; the pre-13d default `"unknown"` is preserved and
  not treated as inactive by routing. No new column, no migration.
- **Inactive routing.** Any `/api/v1/cluster/*` request whose resolved
  `?cluster=` name is `inactive` returns 404 `cluster_not_found`, identical to a
  missing row. The `/api/v1/clusters` list is not filtered.
- **Selector source.** `/api/clusters` proxy passthrough lists all statuses;
  `use-cluster-selection.ts` filters to `status === "active"`. Stale
  `localStorage`/URL selections naming an inactive cluster reset to the first
  active cluster (existing 13c reset path).
- **Audit.** `AuditEvent.CLUSTER_STATUS_CHANGED = "cluster.status_change"`
  recorded with actor id, `resource_type="cluster_connection"`,
  `resource_id=<cluster uuid>`, on every status toggle.
- **Register form.** `POST /api/clusters` sends JSON
  `{ "name": string, "kubeconfig_content": string }`; the backend validates the
  kubeconfig (existing `_parse_kubeconfig` error contract: 422
  `invalid_kubeconfig`, 409 `duplicate_cluster_name`), and the frontend surfaces
  the backend `message` via the existing `extractError` pattern.
- **Error behavior (frontend).** 401 → redirect `/login`; 503/network → "The
  cluster management service is currently unavailable."; other non-OK → backend
  `message` or generic fallback. Unexpected failures reach the generic error
  state; no cluster data is fabricated client-side.

## Testing

- **Backend (pytest, focused new tests):**
  - `test_cluster_management.py`: toggle active→inactive→active returns updated
    `ClusterSummary` and persists; 404 unknown id; 403 viewer; 422 invalid
    status (`"paused"`); audit `cluster.status_change` row with actor id;
    `GET /clusters` still lists the inactive cluster.
  - `test_cluster_routing.py`: after toggling a named cluster inactive,
    `GET /api/v1/cluster/namespaces?cluster=<name>` → 404 `cluster_not_found`;
    after reactivating → 200. Existing default-`primary` routing tests stay green.
- **Frontend:** `cd k8s-ui && yarn build` (no runner configured).
- **Manual:** start backend + `yarn dev`; log in as admin: open the
  Administration → Clusters link; confirm the seeded `primary` row, register a
  cluster (paste a kubeconfig), toggle it inactive, confirm the header selector
  drops it and its data views show the error until reactivated; log in as
  operator (can register/toggle) and as viewer (sees the table with no
  create/toggle controls).

## Notes for the AI

- **Do not start a dev server.** All checks are build/test independent except the
  manual path above, which the user runs.
- **Model the management UI and error/loading states on `users-management.tsx`** —
  badge variants, `Dialog`/`AlertDialog` usage, `extractError`, 401/503 handling,
  and the row action layout.
- The register form uses the **JSON create path** (name + kubeconfig textarea),
  not multipart.
- **13c integration is a narrow edit:** only the active-status filter in
  `use-cluster-selection.ts`; do not rewrite the hook's resolution order,
  `localStorage` key, or stale-reset.
- **Authorization is role-permission-based, not page-level admin-only.** The page
  is reachable by any logged-in user; only the write affordances are gated in the
  UI, and the backend enforces permissions regardless.
- Do not add `DELETE`, kubeconfig editing, or cluster health polling.
- Do not change user/auth flows, the password page, notifications, the user menu,
  or the header `+` button.

## Open questions

- None. The "admin-only" wording in the build plan was resolved by the user's
  decision to follow the shipped RBAC matrix (operator + admin may write, all
  roles may read), and deactivate semantics to hide from both the selector and
  routing.