# Current Feature

> **Generated file.** Holds the one feature, fix, or rollback being built right now. Run
> `/feature <number-or-name>` to spec a build-plan feature, or `/fix "<bug>"` for
> an ad-hoc fix. Use `/rollback <completed-feature>` to plan a safe reversal.
> Build one thing at a time; `/complete` archives it under
> `blueprint/history/` and resets this file.

## Feature 18j — Installation history

**Type:** Feature
**Status:** verified
**Branch:** feature/installation-history

### Goal

Show a **table of recent Marketplace installations** (package, cluster,
namespace, status badge, date) on the `/marketplace` page, with basic status
filtering. Build-plan 18j; it reads jobs already stored by 18g-18i, so there is
nothing new to persist.

### In scope

- Backend `GET /api/v1/marketplace/installations` list endpoint: returns all
  installation jobs ordered `created_at DESC` (tie-break `id DESC`), each item
  shaped like the existing single-status response (reuse
  `MarketplaceInstallationStatus`), plus `total`.
- Optional `status` query filter restricted to the closed set
  `queued|running|succeeded|failed|cancelled`; anything else → 422
  `invalid_status_filter`.
- Optional `limit` (1-200, default 100) via `Query(ge=1, le=200)`.
- Frontend proxy `GET /api/marketplace/installations` (Next.js route handler in
  `k8s-ui/app/api/marketplace/installations/route.ts`, sibling to the existing
  `[job_id]` route) forwarding the backend cookie, `cache: "no-store"`.
- New `MarketplaceHistory` component under the package browser on `/marketplace`
  (rendered from `MarketplaceView`): shadcn `DataTable` with columns Package,
  Cluster, Namespace, Status badge, Date; a status `Select` filter
  (All + the five statuses) applied client-side to the fetched items; a Refresh
  button; loading, error (with retry), and empty states.
- Focused backend tests in `backend/tests/test_marketplace.py` reusing the
  existing `_seed_installation`, `admin_cookie`, and client fixtures.
- Run the declared `Verify` (backend `pytest` + `k8s-ui yarn verify`).

### Out of scope

- No release management / upgrade / rollback / uninstall (build-plan 18j
  explicitly defers these).
- No reopen/review of a job's live progress from history (18i dialog remains the
  only live progress surface).
- No server-side pagination for the history endpoint (the client `DataTable`
  paginates the fetched slice; `limit` caps the slice).
- RBAC hardening and install-permission checks stay in 18k.
- Cluster-scoping/per-cluster history filters stay out until Multi-cluster (13).

### Build loop

- `workflow.stepReview: feature` — implement each step, continue through passing
  steps, present one review packet at the end.
- `workflow.checkpointCommits: disabled` — no per-step commits inside
  `/implement`; the final `/complete` work commit is the only commit.

### Build steps

**Step 1 — Backend history list endpoint.**
- File: `backend/app/api/v1/marketplace.py`, `backend/app/api/v1/marketplace_schemas.py`
- Add `GET /marketplace/installations` (response model
  `MarketplaceInstallationListResponse` with `items:
  list[MarketplaceInstallationStatus]` and `total: int`, `extra="forbid"`). Auth:
  `Depends(get_current_actor)` like the other marketplace endpoints (18k
  hardens this later). Use `select(InstallationJob)` ordered by
  `InstallationJob.created_at.desc(), InstallationJob.id.desc()`, optional
  `status` where-filter validated against the closed set (422 code
  `invalid_status_filter`), optional `limit: int = 100` via
  `Query(ge=1, le=200)`; `total` = count of the same filtered set. Reuse
  `MarketplaceInstallationStatus` field-for-field for each item (no new item
  schema).
- Add focused tests reusing `_seed_installation`: unauthenticated → 401;
  empty DB → `{items: [], total: 0}`; multiple jobs ordered most-recent-first;
  `?status=succeeded` returns only matching; `?status=invalid` → 422
  `invalid_status_filter`; `?limit=0` / `?limit=201` → 422.
- Done when: `cd backend && .venv/bin/python3 -m pytest tests/test_marketplace.py`
  passes with the new tests, and the endpoint returns the closed status contract.
- [x] Done: list endpoint + schema + 6 focused tests; `tests/test_marketplace.py` — **47 passed**.

**Step 2 — Frontend proxy route.**
- File: `k8s-ui/app/api/marketplace/installations/route.ts` (new)
- `GET` handler mirroring `[job_id]/route.ts` exactly (forwarded cookie,
  `cache: "no-store"`, `proxyResponse`, `backendUnavailable` fallback) targeting
  `/api/v1/marketplace/installations`.
- Done when: route builds under `k8s-ui` (`yarn verify`), and it resolves as a
  list sibling to the existing `[job_id]` route.
- [x] Done: `route.ts` proxy mirroring `[job_id]/route.ts` (cookie, `no-store`,
  `proxyResponse`/`backendUnavailable`); builds under `yarn verify`.

**Step 3 — History UI.**
- Files: `k8s-ui/components/marketplace-history.tsx` (new),
  `k8s-ui/components/marketplace-view.tsx` (render it below
  `<MarketplaceBrowser />`)
- `MarketplaceHistory` is a client component that fetches the proxy on mount
  (reuse the `useState` + `useRef(AbortController)` + effect pattern from
  `workloads-view.tsx`, `cache: "no-store"`, abort on unmount/refetch). States:
  loading (muted "Loading installation history…" like workloads-view), error
  (`role="alert"` red banner with Retry), ready.
- `DataTable` columns: Package (`package_name`), Cluster, Namespace, Status
  (Badge, tone-mapped pill via className like `healthTone`:
  queued→`bg-slate-200 text-slate-600`, running→`bg-cyan-100 text-cyan-700`,
  succeeded→`bg-green-100 text-green-700`, failed→`bg-red-100 text-red-700`,
  cancelled→`bg-amber-100 text-amber-700`), Date
  (`new Date(created_at).toLocaleString()`). Placeholder "No installations yet."
- Status `Select` above the table ("All statuses" + the five statuses) filtering
  `items` client-side before passing to `DataTable` (matches "basic status
  filtering only if easy"); `aria-label="Filter installations by status"`.
  Refresh button styled like `workloads-view`'s Refresh.
- `MarketplaceView` renders `<section className="mt-10"><MarketplaceHistory /></section>`
  after `<MarketplaceBrowser />`.
- Done when: `yarn verify` passes and the section renders with the 5-column
  table, working filter, refresh, and the three non-ready states.
- [x] Done: `MarketplaceHistory` client component + `MarketplaceView` renders it
  in `<section className="mt-10">`; loading/error-with-Retry/empty states;
  status `Select` filter (client-side); Refresh button; builds under `yarn verify`.

**Step 4 — Full Verify.**
- Run the declared Verify: `cd backend && .venv/bin/python3 -m pytest` and
  `cd k8s-ui && yarn verify`; also `cd k8s-ui && yarn lint` (must stay at 0
  errors, pre-existing warnings allowed).
- Done when: backend suite **210 + new tests** passes and the frontend build and
  lint pass.
- [x] Done: verify passed — backend **216 passed**; frontend **yarn verify build
  passed**; **yarn lint 0 errors/19 pre-existing warnings**.

### Files / areas

- `backend/app/api/v1/marketplace.py` — new list endpoint (existing router).
- `backend/app/api/v1/marketplace_schemas.py` — new list response schema (reuse
  `MarketplaceInstallationStatus` as the item shape).
- `backend/tests/test_marketplace.py` — focused list tests (reuse
  `_seed_installation`).
- `k8s-ui/app/api/marketplace/installations/route.ts` — list proxy (sibling to
  `[job_id]/route.ts`).
- `k8s-ui/components/marketplace-history.tsx` — new history table component.
- `k8s-ui/components/marketplace-view.tsx` — render history below the browser.
- Model `InstallationJob` (entities.py) is read-only; no migration.

### Data / contracts

- `GET /api/v1/marketplace/installations` → `{ items: MarketplaceInstallationStatus[], total: int }`.
- Item fields (unchanged contract from 18h): `job_id`, `package_name`, `cluster`,
  `namespace`, `release_name`, `status` (closed set), `error_message`,
  `created_at`, `started_at`, `completed_at`.
- Errors: 401 unauthenticated; 422 `{"code":"invalid_status_filter"}` for a
  bad status; 422 pydantic bounds for `limit` out of 1-200. No audit event for a
  read-only GET (matches existing GETs).
- Read-only, no new stored fields, no cache layer (explicit `no-store`).

### Testing

- Backend: `pytest` focused tests in `test_marketplace.py` (auth, empty,
  ordering, status filter positive + invalid, limit bounds).
- Frontend: no test runner (per AGENTS.md); verified via `yarn verify` (build),
  `yarn lint`, and the manual browser path under `Verify`.

### Notes for the AI

- Preserve the unrelated uncommitted edit in `k8s-ui/components/dashboard-shell.tsx`
  (working tree, not part of this spec) — do not stage or modify it.
- Do not touch `k8s-ui/components/install-dialog.tsx` or the `marketplace-cache.ts`
  cache; the history list is live ops data and must stay uncached.
- Reuse the `Spinner`/empty/error idioms already used by `marketplace-browser.tsx`
  and `workloads-view.tsx`; do not introduce new deps.
- React-hooks lint rule blocks synchronous `setState` in effects — keep fetch
  state updates in async/then callbacks (mirror `workloads-view.tsx`).
- `cluster` on the job is the `ClusterConnection.name` (relationship already
  loaded by the status endpoint via `job.cluster`).

### Open questions

- None blocking. Placement decision (history section on the same `/marketplace`
  page, below the package browser) is repository-native and reversible; filter
  is client-side per "only if easy".