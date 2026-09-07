# Current Feature

**Status:** verified
**Type:** Feature
**Branch:** feature/frontend-cluster-selector

## Goal

Feature 13c — **Frontend cluster selector.** Give the dashboard header a working
cluster dropdown, persist the user's selection to `localStorage`, and pass the
selected cluster on every `/api/cluster/*` backend call so the already-shipped
13b routing actually selects a cluster. With one cluster the selector still
works, defaults to that cluster, and all dashboard data keeps flowing exactly as
it does today.

## In scope

- **Cluster list source.** A new `k8s-ui/app/api/clusters/route.ts` proxy that
  forwards `GET /api/v1/clusters` (with the session cookie) to the backend,
  returning the `ClusterListResponse` items passthrough. Uses the existing
  `backendUrl` / `forwardedCookie` / `backendUnavailable` pattern from
  `app/api/users/route.ts`.
- **Selection state hook.** `k8s-ui/lib/use-cluster-selection.ts` (client)
  replacing `lib/use-cluster-status.ts`:
  - Loads the cluster list from `/api/clusters`.
  - Initial cluster resolution, first non-empty wins: `initialCluster` prop
    (from the URL `?cluster=` param) → `localStorage` key `kubepilot.cluster`
    → the first listed cluster once the list loads → `""` (nothing selected).
  - `selectCluster(name)` sets state and writes `kubepilot.cluster` to
    `localStorage` (guarded for client-only access).
  - When the list loads and the current selection is not in it (stale URL or
    localStorage for a deleted cluster), reset to the first listed cluster.
  - Returns `{ cluster, clusters, selectCluster }`.
- **Selector control + context.** `DashboardShell` gains `clusters` and
  `onSelectCluster` props and provides a `ClusterProvider` React context so any
  descendant view can read the active `cluster`. Its header `<select>` is
  populated from `clusters` (`value=activeCluster`, `onChange=onSelectCluster`);
  the existing native `<select>` styling is kept for consistency with the
  namespace selector. When `activeCluster` is empty the current "Cluster
  unavailable" branch stays.
- **Wire the three top-level views** (`Dashboard`, `ResourceDetailView`,
  `UserSettingsView`) to `useClusterSelection` instead of `useClusterStatus`,
  passing `activeCluster` + `clusters` + `onSelectCluster` into their
  `DashboardShell`. Delete the obsolete `lib/use-cluster-status.ts`.
- **Proxies forward `cluster`.** Each `/api/cluster/*` proxy route
  (`status`, `namespaces`, `resources`, `metrics`, `details/[resourceType]`)
  forwards an incoming `cluster` query param to the backend target when the
  client request carries one. When absent, behavior is unchanged (backend uses
  its default). The details proxy stops hardcoding
  `KUBEPILOT_CLUSTER_NAME` and instead forwards the incoming `cluster` param,
  falling back to the env default when absent.
- **Thread cluster into every cluster fetch.** Add a small client helper
  (`withCluster(path, cluster)`) that appends `?cluster=<name>` to a cluster
  API path (handling existing query strings), and use it at every
  `/api/cluster/*` fetch site:
  - `dashboard-shell.tsx` namespaces fetch (line ~100)
  - `overview-view.tsx` (resources deployments/pods, metrics summary)
  - `cluster-view.tsx` (namespaces, resources nodes/storage-classes/
    persistent-volumes, metrics nodes/storage)
  - `core-resource-view.tsx` (resources, metrics nodes/namespaces/storage)
  - `namespaces-view.tsx` (namespaces)
  - `resource-detail-view.tsx` (metrics nodes/namespaces/storage and the four
    details fetch sites)
  - `use-cluster-selection.ts` status fallback if retained
  - Each fetch effect must include the active `cluster` in its dependency
    array so switching clusters refetches the view.
- **Cluster name is the routing key.** The build plan says "cluster ID", but
  the shipped 13b backend resolves `?cluster=<name>` by cluster *name* (the URL
  `cluster` param already carries names, e.g. the detail page's
  `?cluster=KUBEPILOT_CLUSTER_NAME`). 13c therefore passes cluster names, not
  UUID ids, everywhere.

## Out of scope

- **Admin cluster management page (13d)** — register/activate/deactivate,
  `/settings/clusters`.
- **Cluster status display or health polling** in the selector (only names are
  listed; the backend `status` field is not interpreted).
- **Per-user cluster permissions** — any user with `CLUSTERS_READ` sees and can
  select every cluster (matches backend 13a/13b).
- **Cluster-aware notifications, user menu, `+` header button** — untouched.
- **Backend changes** — 13b already routes by cluster; backend is untouched by
  13c.
- **The settings/password page** — does not render `DashboardShell`; no selector
  needed there.

## Build loop

- Create branch `feature/frontend-cluster-selector`.
- `workflow.stepReview: feature` — build all small steps, then one review packet.
- `workflow.checkpointCommits: disabled` — no per-step checkpoint commits.
- Frontend Verify: `cd k8s-ui && yarn build`.
- Backend Verify (unchanged by 13c; must stay green):
  `cd backend && PYTHONPATH=. python3 -m compileall -q app && PYTHONPATH=. python3 -m pytest`.
- Do not start a dev server; do not add a test runner (frontend has none).

## Build steps

- [x] 1. **Add the `/api/clusters` list proxy.** Create
  `k8s-ui/app/api/clusters/route.ts` exposing `GET` that fetches
  `${backendUrl()}/api/v1/clusters` with `forwardedCookie(request)` and returns
  the JSON passthrough, mapping failures to `backendUnavailable(...)` — mirroring
  `app/api/users/route.ts`.
  **Done when:** `yarn build` passes and a unit-testable fetch surface exists
  (frontend has no runner; the route is reachable via `/api/clusters` and
  requires the session cookie like `/api/users`).

- [x] 2. **Add the selection hook.** Create
  `k8s-ui/lib/use-cluster-selection.ts` (`"use client"`) implementing the In
  scope resolution rules with `localStorage` key `kubepilot.cluster`, the
  stale-selection reset, and the `{ cluster, clusters, selectCluster }` return.
  Use `AbortController` cleanup on unmount like the existing hooks.
  **Done when:** `yarn build` passes; logic is exercised by the handoff review
  (no frontend runner exists).

- [x] 3. **Replace `useClusterStatus` with the selection hook in the three
  top-level views.** Update `components/dashboard.tsx`,
  `components/resource-detail-view.tsx` (its `initialCluster` prop flows from
  the URL `?cluster=`), and `components/user-settings-view.tsx` to call
  `useClusterSelection(...)` and pass `activeCluster`, `clusters`, and
  `onSelectCluster` into `DashboardShell`. Remove `lib/use-cluster-status.ts`
  and delete its import lines.
  **Done when:** `yarn build` passes; no `use-cluster-status` references remain.

- [x] 4. **Make the header selector interactive via context.** In
  `components/dashboard-shell.tsx`, add `clusters: string[]` and
  `onSelectCluster: (name: string) => void` props plus a `ClusterProvider`
  (`k8s-ui/lib/cluster-context.tsx`) exposing `activeCluster` to descendants;
  render the header `<select>` from `clusters` with `value={activeCluster}` and
  `onChange` calling `onSelectCluster`. Keep the empty-cluster "Cluster
  unavailable" fallback and existing styling.
  **Done when:** `yarn build` passes; the selector (in the running app) lists
  each cluster and switching updates the local state.

- [x] 5. **Forward `cluster` in the five proxy routes.** Update
  `k8s-ui/app/api/cluster/{status,namespaces,resources,metrics}/route.ts` and
  `k8s-ui/app/api/cluster/details/[resourceType]/route.ts` so each sets the
  backend target's `cluster` query param from the incoming request's `cluster`
  param when present; the details route falls back to
  `KUBEPILOT_CLUSTER_NAME` when absent.
  **Done when:** `yarn build` passes; the details proxy no longer ignores an
  incoming cluster param.

- [x] 6. **Thread cluster into every `/api/cluster/*` fetch.** Add
  `withCluster(path, cluster)` to `k8s-ui/lib/` and apply it at every fetch
  site listed in In scope `dashboard-shell.tsx`, `overview-view.tsx`,
  `cluster-view.tsx`, `core-resource-view.tsx`, `namespaces-view.tsx`, and
  `resource-detail-view.tsx`, adding the cluster value to each effect's
  dependency array so switching clusters refetches data.
  **Done when:** `yarn build` passes; `grep -rn "api/cluster" components/` shows
  no fetch that omits `withCluster`.

- [x] 7. **Run full verification.** Run
  `cd backend && PYTHONPATH=. python3 -m compileall -q app && PYTHONPATH=. python3 -m pytest`
  and `cd k8s-ui && yarn build`.
  **Done when:** compileall + all backend pytest pass, frontend build clean.

## Files / areas

- `k8s-ui/app/api/clusters/route.ts` (new) — cluster list proxy.
- `k8s-ui/lib/use-cluster-selection.ts` (new) — selection + localStorage;
  `lib/use-cluster-status.ts` (deleted).
- `k8s-ui/lib/cluster-context.tsx` (new) — `ClusterProvider` / `useCluster`.
- `k8s-ui/lib/` — `withCluster` helper (new, e.g. `lib/cluster-query.ts`).
- `k8s-ui/components/dashboard-shell.tsx` — selector control + provider +
  namespaces fetch uses `withCluster`.
- `k8s-ui/components/dashboard.tsx`, `components/resource-detail-view.tsx`,
  `components/user-settings-view.tsx` — migrate to `useClusterSelection`.
- `k8s-ui/components/overview-view.tsx`, `cluster-view.tsx`,
  `core-resource-view.tsx`, `namespaces-view.tsx` — fetch sites add cluster.
- `k8s-ui/app/api/cluster/{status,namespaces,resources,metrics}/route.ts` and
  `k8s-ui/app/api/cluster/details/[resourceType]/route.ts` — forward `cluster`.

## Data / contracts

- **Selection persistence.** `localStorage["kubepilot.cluster"]` holds the
  cluster *name*. Written on every selection change; read on first load.
- **Cluster naming.** The `cluster` query param and the selector option values
  carry cluster `name`s, matching the 13b backend routing contract. The backend
  `ClusterSummary.id` (UUID) is not sent.
- **`/api/clusters` proxy response.** Passthrough of the backend
  `ClusterListResponse` (`{ "items": [{ "id", "name", "endpoint", "status",
  "created_at" }] }`); the client extracts `name`.
- **Error behavior.**
  - Backend down or list empty → no clusters, selection stays `""`, header shows
    "Cluster unavailable", the select is empty/disabled, and cluster fetches
    omit the param (backend default). No crash.
  - Stale URL/localStorage name not in the list → reset to the first listed
    cluster.
  - Unknown cluster name passed to a proxy → forwarded to backend → 404
    `cluster_not_found` surfaces as it does today (no client-side special-casing).
- **Unauthenticated access** to `/api/clusters` → backend 401 `authentication_required`
  passthrough via cookie, same as `/api/users`.

## Testing

- **Backend:** `cd backend && PYTHONPATH=. python3 -m compileall -q app && PYTHONPATH=. python3 -m pytest` — unchanged by 13c, must stay green.
- **Frontend:** `cd k8s-ui && yarn build` (`logicTests` is `when-configured`; no
  frontend runner exists, so build + manual review is the check).
- **Manual:** start backend + `yarn dev`, log in, use the header Cluster
  dropdown. Verify the option list matches registered clusters, switching
  changes the page data, and the choice survives a reload (localStorage).
  Single-cluster default behavior is unchanged.

## Notes for the AI

- **Do not start a dev server.** All checks are build/runtime-independent except
  the manual path above, which the user runs.
- **Keep the native header `<select>`** styling and empty-state fallback; do not
  swap to the Base UI `Select` component in this feature unless it is already
  used for the cluster selector.
- **`ResourceDetailView` owns its own selection** (page-level component that
  renders its own `DashboardShell`); it must pass the selection into the shell
  and use the same selection for its own details/metrics fetches — it cannot
  consume the shell's context from outside.
- The URL `?cluster=` param is the single inbound source on all three pages
  (dashboard and detail already read it; settings does not). Keep it read-only
  as `initialCluster`; do not write back to the URL except where
  `dashboard.tsx` already does.
- **Do not change** the sidebar `onNavigate`, notification popover, user menu, or
  the header `+` button.
- Backend files are untouched by this feature.

## Open questions

- None. `localStorage` key (`kubepilot.cluster`) and name-based routing are
  recorded as internal, reversible contracts consistent with shipped 13b
  behavior.