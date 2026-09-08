# Current Feature

**Status:** verified
**Type:** Feature
**Scope:** 18f — KubePilot Marketplace installation API
**Branch:** `feature/installation-api`

## Goal

Add the Marketplace install API: a backend `POST /api/v1/marketplace/install`
(plus the matching Next.js proxy route) that validates the values the 18e dialog
collects, resolves and validates the package/version against Artifact Hub,
creates an `InstallationJob` row in state `queued`, records an audit action, and
returns `{job_id, status: "queued"}` without running Helm. It also wires the 18e
install dialog's Submit button to the new endpoint. Who-what authorized to
install becomes a role policy in 18k; the background Helm worker, status
endpoints, and progress/history UI stay in 18g-18j.

## In scope

1. **`InstallationJob` model + migration** (new) - in
   `backend/app/models/entities.py`, `__tablename__ = "installation_jobs"`, with
   the overview-pinned field set: `id` (PrimaryKey), `package_id` (String, not
   null), `package_name` (String, not null), `chart_name` (String, not null),
   `chart_repository` (String, not null), `chart_version` (String, not null),
   `cluster_id` (UUID FK -> `cluster_connections.id`, `ondelete="CASCADE"`, not
   null, indexed), `namespace` (String, not null), `release_name` (String, not
   null), `status` (String(32), not null, default/server_default for the model
   must be `"queued"` at insert time - the endpoint sets it explicitly),
   `error_message` (Text, nullable), `started_at` (DateTime(timezone=True),
   nullable), `completed_at` (nullable), `created_at` (CreatedAt). A
   `relationship` back to `ClusterConnection` (`back_populates="installations"`
   added on `ClusterConnection`). Register in `app/models/__init__.py`. New
   Alembic revision chained after the current head adding the
   `installation_jobs` table with an index on `cluster_id` and `status`.
2. **Install request/response schemas** (new) - in
   `backend/app/api/v1/marketplace_schemas.py`, both `extra="forbid"`:
   - `MarketplaceInstallRequest`: `package_id: str`, `package_name: str`,
     `version: str`, `repository_name: str`, `cluster: str`, `namespace: str`,
     `release_name: str`. Pydantic field constraints: `package_id`,
     `package_name`, `version`, `cluster` non-empty; `repository_name`,
     `namespace`, `release_name` match the DNS-1123 label pattern
     (`^[a-z0-9]([-a-z0-9]*[a-z0-9])?$`) with max length 63 (namespace/release
     name are k8s DNS-1123 labels; repository name is a package URL segment).
     Constraint violations surface as the app's generic 422
     `validation_error` (the existing `RequestValidationError` handler), the
     same code cluster routes use for shape failures.
   - `MarketplaceInstallResponse`: `job_id: UUID`, `status: Literal["queued"]`.
3. **Backend `POST /api/v1/marketplace/install`** (new) in
   `backend/app/api/v1/marketplace.py`, reusing the router already mounted at
   `/api/v1` in `main.py`, `status_code=201`, `response_model=MarketplaceInstallResponse`:
   - **Auth:** `Depends(get_current_actor)` (any authenticated user, matching
     the existing marketplace endpoints). `restricted` actors are NOT blocked
     here (that is the 18k RBAC audit); 401 when unauthenticated.
   - **Cluster resolve:** look up `ClusterConnection` by `body.cluster`
     (exact name). Missing or `status == "inactive"` -> 404 `cluster_not_found`
     ("Cluster was not found") - same semantics as `get_cluster_client`.
   - **Namespace check:** build a `ClusterClient` from `kubeconfig_content`
     (`create_cluster_client(settings, kubeconfig_content=row.kubeconfig_content,
     cluster_name=row.name)`) and list namespaces; if `body.namespace` is not
     among them -> 422 `namespace_not_found` ("Namespace was not found in
     cluster"). ClusterClient failures propagate to the app's existing handlers
     (403 `cluster_forbidden`, 503 `cluster_unavailable`, 502 `cluster_error`).
     kube-system is NOT special-cased here; that policy is 18k.
   - **Package/version resolve:** fetch the Artifact Hub package detail using
     `_read_package_segment(body.repository_name, "repository")` and the detail
     URL pattern already used by `get_package_versions`
     (`ARTIFACT_HUB_PACKAGE_URL`, `kind=helm`), via `_fetch_artifact_hub_search`.
     Upstream 404 -> 404 `marketplace_not_found`; transport error or non-200 ->
     502 `marketplace_upstream_error`; non-dict payload or missing
     `available_versions` list -> 502 `marketplace_upstream_error`. A
     != 200 semantic check: if `body.version` is not present as a `version`
     string of an entry in `available_versions` -> 422 `version_not_available`
     ("Version is not available for this package").
   - **Create:** insert `InstallationJob` with `status="queued"` and the stored
     fields: `package_id` / `package_name` from the request,
     `chart_name` = upstream detail `name`, `chart_repository` = upstream detail
     `repository.name` (the resolved Artifact Hub repo name), `chart_version` =
     `body.version`, `cluster_id` = resolved cluster id, `namespace`,
     `release_name`; `error_message`/`started_at`/`completed_at` null. Commit,
     then record audit `AuditEvent.MARKETPLACE_INSTALL_QUEUED` with
     `resource_type="installation_job"`, `resource_id=str(job.id)`,
     `result="success"`, and commit. Return
     `MarketplaceInstallResponse(job_id=job.id, status="queued")`.
4. **Next.js proxy route** (new) - `k8s-ui/app/api/marketplace/install/route.ts`
   HTTP `POST`, forwarding JSON body + incoming cookie to
   `/api/v1/marketplace/install` with `cache: "no-store"`, using the
   `@/lib/backend` helpers exactly like the existing
   `app/api/marketplace/packages/route.ts` proxy (`503 backend_unavailable` on
   transport failure). It is a standalone route; the packages route stays
   GET-only.
5. **Install dialog wiring** (`k8s-ui/components/install-dialog.tsx`) - the
   footer Install button becomes a real submit (still `type="button"`, no form
   element): while `posting`, the button is disabled with its current label; on
   201 it is replaced by a muted success line "Installation queued (job
   {job_id})"; the dialog stays open (progress follows in 18h/18i); on any
   non-201 it shows an inline `role="alert"` box with the backend `message`
   (from the proxy JSON error body) and re-enables Submit. All fetch/state
   transitions happen in event/async handlers only - no synchronous `setState`
   in effects. Payload:
   `{package_id, package_name, version, repository_name, cluster, namespace,
   release_name}` from the already-collected dialog state
   (`pkg.package_id`, `pkg.name`, `pkg.repository?.name`, version select,
   cluster select, namespace select, release input).

## Out of scope

- Background Helm execution, worker, and status transitions - 18g.
- Status API (`GET .../installations/{job_id}`) - 18h.
- Progress UI / polling / history - 18i-18j.
- Install-permission (role) policy, kube-system protection, backend re-audit of
  security on collected values, Helm command construction; Artifact Hub output
  treated as executable input - 18k.
- Release management (upgrade/rollback/uninstall), cancellation semantics - not
  in the Marketplace plan yet.
- Adding columns beyond the overview field set (for example a repo URL for
  `helm repo add`) - 18g resolves what its worker needs.

## Build loop

Follow `blueprint/config.json`: `stepReview: feature`, `checkpointCommits:
disabled` - one review packet after the small steps below, a single feature
commit at the end via `/complete`. Every step stays on branch
`feature/installation-api` (never master), ends green, and carries an observable
`Done when`. Backend steps run `cd backend && python3 -m compileall -q app`
and focused/full pytest (`.venv/bin/python3 -m pytest`); frontend steps run
`yarn lint` (0 errors; 19 baseline warnings) + `yarn build`. Stop on any P0/P1
finding; `/complete` archives and squash-merges only with the user's explicit
go-ahead.

## Build steps

- [x] 1. **`InstallationJob` model + Alembic migration.** Add the entity and
  `ClusterConnection.installations` relationship, export from
  `app/models/__init__.py`, and add a new Alembic revision (after the current
  head) creating `installation_jobs` with the exact columns/indexes above.
  `Done when`: `python3 -m compileall -q app` is clean, the current tests still
  pass (`183 passed`), and `cd backend && PYTHONPATH=. alembic upgrade head --sql`
  renders a `CREATE TABLE installation_jobs` statement.
- [x] 2. **Install schemas + POST endpoint.** Add `MarketplaceInstallRequest`
  and `MarketplaceInstallResponse` to `marketplace_schemas.py`, add
  `AuditEvent.MARKETPLACE_INSTALL_QUEUED = "marketplace.install_queued"`, and
  implement `create_installation` in `marketplace.py` with the full validation/
  resolve/create/audit flow in scope item 3. `Done when`: `python3 -m
  compileall -q app` is clean and the current test suite still passes without
  new focused tests yet (existing `183 passed`).
- [x] 3. **Focused tests for the endpoint.** In `backend/tests/test_marketplace.py`
  reuse the `api`/`upstream` fixtures and add: unauthenticated 401; malformed
  body and invalid DNS-1123 fields 422 `validation_error`; unknown and inactive
  cluster 404 `cluster_not_found`; upstream detail 404 -> 404
  `marketplace_not_found` and non-200/transport -> 502
  `marketplace_upstream_error`; valid package but requested version absent from
  `available_versions` -> 422 `version_not_available`; namespace missing from the
  (faked) cluster's namespace list -> 422 `namespace_not_found`; happy path
  201 with `{job_id, status:"queued"}` where the row is re-read from the DB
  (package/cluster/namespace/release/status fields match) and an
  `audit_actions` row exists. Add a fixture/fake `ClusterClient` (monkeypatch
  `app.api.v1.marketplace.create_cluster_client`) returning a fixed namespace
  list. `Done when`: `cd backend && .venv/bin/python3 -m pytest
  tests/test_marketplace.py` passes (existing + new).
- [x] 4. **Proxy route + dialog submit wiring.** Create
  `k8s-ui/app/api/marketplace/install/route.ts`; rework the
  `install-dialog.tsx` footer from the 18e no-op into the POST submit
  (pending state, success queued line, inline error alert; no synchronous
  setState in effects). `Done when`: `yarn lint` (0 errors, same 19 baseline
  warnings) and `yarn build` pass.
- [x] 5. **Verify.** Run the declared Verify once: `cd backend &&
  .venv/bin/python3 -m pytest` (183 + the new focused tests) and
  `cd k8s-ui && yarn verify`. `Done when`: both commands pass.

## Files / areas

- `backend/app/models/entities.py` - add `InstallationJob`; add
  `installations: Mapped[list["InstallationJob"]]` relationship on
  `ClusterConnection`.
- `backend/app/models/__init__.py` - export `InstallationJob`.
- `backend/alembic/versions/<new>.py` - create `installation_jobs`; chain after
  the current head (verify with `alembic heads` before writing).
- `backend/app/api/v1/marketplace_schemas.py` - `MarketplaceInstallRequest`,
  `MarketplaceInstallResponse`.
- `backend/app/api/v1/marketplace.py` - `create_installation` route + helpers
  (reuse `_read_package_segment`, `_fetch_artifact_hub_search`,
  `_upstream_error`, `ARTIFACT_HUB_PACKAGE_URL`); import `create_cluster_client`
  from `app.kubernetes.client` (module-level name the tests patch).
- `backend/app/core/audit.py` - `MARKETPLACE_INSTALL_QUEUED` event.
- `backend/tests/test_marketplace.py` - new focused tests + fake cluster client.
- `k8s-ui/app/api/marketplace/install/route.ts` - new Next POST proxy
  (`@/lib/backend` helpers, mirror the existing marketplace proxy).
- `k8s-ui/components/install-dialog.tsx` - real submit wiring + states.
- Reused unchanged: `app/core/dependencies.py` (`get_current_actor`,
  `get_database_session`, `get_settings`), `app.core.audit.record_audit`,
  `marketplace_schemas` existing types, `ui/dialog.tsx`, `ui/button.tsx`.

## Data / contracts

- New contract `POST /api/v1/marketplace/install`:
  - Request `{package_id, package_name, version, repository_name, cluster,
    namespace, release_name}` (strings; DNS-1123 for repository/namespace/
    release). No new id plumbing is added: `cluster` is the selector name the
    18e dialog collects and `cluster_id` is resolved server-side.
  - 201 `{job_id: UUID, status: "queued"}`; 401 `authentication_required`; 422
    `validation_error` (shape/format), 422 `namespace_not_found`, 422
    `version_not_available`; 404 `cluster_not_found`, 404
    `marketplace_not_found`; 502 `marketplace_upstream_error`, plus the cluster
    handlers' 403/503/502.
  - Idempotency: repeated identical installs create distinct jobs (no
    unique constraint) - intended; dedupe/cancel is a later worker concern.
- `InstallationJob` (`installation_jobs`) fields pinned above. The overview
  assigns the model to 18g, but 18f must return a real `job_id` in state
  `queued`, so 18f introduces the table with the overview field set and 18g
  implements the worker + transitions without new columns (any worker-only need
  is 18g's migration). `status` is stored as `"queued"` at create.
- `chart_name` and `chart_repository` are copied from the live Artifact Hub
  detail response (`name`, `repository.name`), not from request fields, so the
  client cannot set executable/chart identity. The repository URL needed later
  for `helm repo add` is NOT stored now; 18g resolves what it needs, and 18k
  governs trust of Artifact Hub output.
- Namespace membership is checked against the live cluster's namespace list at
  request time (same source as the shell) so a queued job targets a namespace
  that exists today; kube-system is not yet special-cased (18k).
- The dialog keeps sending nothing else; no version PIN changed (18e contract:
  version is a string from the versions endpoint). Release name obeys the same
  DNS-1123 rule as 18e.
- Audit: one `audit_actions` row per job (`marketplace.install_queued`,
  resource_type `installation_job`, resource_id `str(job.id)`, actor =
  authenticated user).

## Testing

- Backend: `cd backend && .venv/bin/python3 -m pytest` - existing 183 plus the
  new `test_marketplace.py` cases (Artifact Hub seam + fake cluster client, no
  live network/k8s); `cd backend && python3 -m compileall -q app`; migration
  renders via `cd backend && PYTHONPATH=. alembic upgrade head --sql`.
- Frontend: no test runner (opt-in per standards); `yarn lint` (0 errors, 19
  baseline warnings incl. the two `no-img-element`) + `yarn build`. The submit
  wiring is client logic verified by the manual try path below.
- Manual try path: start backend + `yarn dev`, open `/marketplace`, open the
  install dialog, pick version/cluster/namespace + a release name, Submit; expect
  no page reload, a queued line with a job UUID, and a new
  `installation_jobs`/`audit_actions` row; confirm an invalid release name keeps
  Submit disabled (a form that cannot reach the API), and a request to a
  namespace that no longer exists returns the inline alert. Confirm the dialog
  still closes via ESC/backdrop/close.

## Notes for the AI

- Reuse `_fetch_artifact_hub_search`; the existing tests patch
  `app.api.v1.marketplace._fetch_artifact_hub_search`, so call it through the
  module namespace. Import `create_cluster_client` in `marketplace.py` as a
  module-level name (`from app.kubernetes.client import create_cluster_client`)
  so the new fake can `monkeypatch.setattr("app.api.v1.marketplace.create_cluster_client", fake)`;
  the fake's `namespaces()` must return an iterable of `(name, status)` tuples
  matching `ClusterClient.namespaces()` used in `routes.py`.
- Do not rename or move the version/detail seams; 12 marketplace tests and the
  6 versions tests depend on them.
- The dialog form resets per package via `key={pkg.package_id}` (already in
  place); do not add a `<form onSubmit>` - keep the Button `type="button"` and do
  the fetch in an async click handler so we stay clear of the react-compiler
  setState-in-effect rule. `posting`/`error`/`jobId` are plain event-driven
  state.
- The 18e Submit was a deliberate no-op; this step is the first real caller of
  the install API. Keep the success state non-dismissive (close/ESC/backdrop
  only) since 18h/18i supply progress; never fake a "succeeded" status.
- `Alembic heads` may need `PYTHONPATH=.`; the project already documents
  `cd backend && PYTHONPATH=. alembic upgrade head --sql` as the migration SQL
  check.
- In the review handoff, call out the model-timing decision (18f owns the
  InstallationJob table so it can return `job_id`; 18g only adds the worker)
  and the auth scope (authenticated-user only; role/permission policy is 18k).

## Open questions

- **Install authorization policy (who may install per role):** the build plan
  puts install-permission checks in 18k, and the overview defers the policy to
  a Marketplace spec. 18f proceeds with the existing marketplace auth boundary
  (`get_current_actor`, any authenticated user) to avoid inventing a policy;
  the role-permission decision must be made in its 18k spec.
- **kube-system policy:** overview defers "protected unless explicitly allowed
  by policy" to 18k; 18f queues installs into any namespace that exists in the
  cluster. Non-blocking for 18f.