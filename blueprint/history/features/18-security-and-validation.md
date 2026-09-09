# Current Feature

> **Generated file.** Holds the one feature, fix, or rollback being built right now. Run
> `/feature <number-or-name>` to spec a build-plan feature, or `/fix "<bug>"` for
> an ad-hoc fix. Use `/rollback <completed-feature>` to plan a safe reversal.
> Build one thing at a time; `/complete` archives it under
> `blueprint/history/` and resets this file.

## Feature 18k — Security & validation

**Type:** Feature
**Status:** verified
**Branch:** feature/security-and-validation

### Goal

Close the Marketplace security gates called out in build-plan 18k: gate installs
behind the existing RBAC permission system, block installs into `kube-system`,
tighten validation so Artifact Hub metadata is never trusted as executable
input, and harden the background Helm worker. Read surfaces (catalog, versions,
status, history) stay auth-only so viewers can still operate the UI.

### In scope

- **Install permission.** New `Permission.MARKETPLACE_INSTALL =
  "marketplace:install"` in `app/core/rbac.py`, granted to `operator` and
  `admin` (viewer is denied). `POST /api/v1/marketplace/install` switches from
  `get_current_actor` to `require_permission(Permission.MARKETPLACE_INSTALL)`,
  which also rejects restricted (password-change-forced) sessions.
- **kube-system protection.** Reject `namespace == "kube-system"` on install
  with 422 `namespace_protected` (checked before the namespace-existence check,
  so it holds even where `kube-system` exists). No allow-policy exists; the plan
  default "not allowed" applies.
- **Metadata trust hardening.** In `_fetch_package_detail`, `chart_name` and
  `chart_repository` must match the existing DNS-1123
  `PACKAGE_SEGMENT_PATTERN`, and `chart_repository_url` must parse with an
  `http`/`https` scheme; otherwise 502 `invalid_package_source`. Verify the
  Artifact Hub `package_id` equals the request's `package_id` (422
  `package_mismatch`) before creating the job. Existing checks kept: version must
  be in upstream `available_versions`, cluster must be active, namespace and
  release name already DNS-1123 in `MarketplaceInstallRequest`.
- **Worker defense-in-depth.** `_process_claimed_job` re-validates
  `chart_name`, `chart_repository`, `namespace`, `release_name` (DNS-1123) and
  `chart_repository_url` (http/https) before running any Helm command, and marks
  the job failed with a clear message instead of executing (protects pre-18k
  rows). Helm runs stay list-argv with `subprocess.run` (no shell), which already
  defeats shell injection — unchanged, now enforced by the guard.
- **Frontend 403 surfacing.** The install dialog must present the backend 403
  `message` ("Insufficient permissions for the required role") instead of a
  generic failure. No new viewer-gating UI in 18k (that lands with 18l).
- Focused backend tests for every gate above, reusing
  `_seed_installation`/`admin_cookie`/`upstream`/`cluster_client` fixtures and
  the user-seeding patterns from `tests/test_users.py` for non-admin roles.
- Run the declared `Verify` (backend `pytest` + `k8s-ui yarn verify`).

### Out of scope

- No UI role-gating / hiding Install buttons for viewers (18l).
- No resource-level install authorization beyond role (no per-cluster or
  per-namespace ACLs; 13 defines per-cluster scoping).
- No idempotency keys / duplicate-install detection; each request creates one
  queued job (existing behavior, keep).
- No allowed-namespace policy knobs or configurable protected-namespace list;
  `kube-system` is the single protected namespace per the plan text.
- No pinning of the ServiceAccount / cluster RBAC bindings (overview open item).
- No cancel/upgrade/rollback/uninstall (deferred with 18l-era plans).

### Build loop

- `workflow.stepReview: feature` — implement each step, continue through passing
  steps, present one review packet at the end.
- `workflow.checkpointCommits: disabled` — no per-step commits inside
  `/implement`; the final `/complete` work commit is the only commit.

### Build steps

**Step 1 — RBAC install-permission gate.**
- Files: `backend/app/core/rbac.py`, `backend/app/api/v1/marketplace.py`
- Add `Permission.MARKETPLACE_INSTALL = "marketplace:install"` (the
  `ALL_PERMISSIONS` loop picks it up automatically) and grant it to
  `Role.OPERATOR` in `ROLE_PERMISSIONS` (admin already gets all).
  `create_installation` uses `actor: Annotated[AuthenticatedActor,
  Depends(require_permission(Permission.MARKETPLACE_INSTALL))]`.
- Tests in `tests/test_marketplace.py` (seed a viewer and a restricted-operator
  account via the `tests/test_users.py` user/session pattern): viewer install →
  403 `insufficient_permissions` and no job created; restricted operator →
  403 `password_change_required`; operator install happy path; admin install
  happy path unchanged (201, job queued).
- Done when:
  `cd backend && .venv/bin/python3 -m pytest tests/test_marketplace.py` passes
  with the new tests, and a viewer/restricted actor gets 403 before any cluster
  or upstream work.
- [x] Done: `MARKETPLACE_INSTALL` permission + operator grant; install gated by
  `require_permission`; viewer/restricted-operator denied (403), operator
  allowed — 28 install-focused tests pass (and the operator row of the
  `test_rbac_permissions` matrix now includes `marketplace:install`).

**Step 2 — kube-system protection and metadata trust.**
- Files: `backend/app/api/v1/marketplace.py`
- Helper `_ensure_namespace_allowed(namespace)` → 422
  `{"code":"namespace_protected",...}` when `namespace == "kube-system"`, called
  in `create_installation` between cluster resolution and
  `_ensure_namespace_exists`.
- `_fetch_package_detail` returns also `package_id`; validate `chart_name` and
  `chart_repository` against `PACKAGE_SEGMENT_PATTERN` and
  `chart_repository_url` scheme in `("http", "https")` → else 502
  `invalid_package_source`. `create_installation` compares upstream
  `package_id` to `request.package_id` → mismatch 422 `package_mismatch`.
- Tests: update `test_install_namespace_not_found_rejected` to a missing
  non-system namespace (e.g. `analytics`); add `kube-system` to the fake
  cluster's namespace list and assert a `kube-system` install → 422
  `namespace_protected`; upstream payload with invalid `name`/repo `url`
  (e.g. `file:///etc`, or `Bad_Chart`) → 502 `invalid_package_source`;
  `UPSTREAM_INSTALL_DETAIL` with a different `package_id` than `INSTALL_BODY` →
  422 `package_mismatch`.
- Done when: the marketplace test file passes (auth/403/404/422/502 ordering
  intact) and `namespace_protected` returns before `namespace_not_found` for a
  present `kube-system`.
- [x] Done: `_ensure_namespace_allowed` (422 `namespace_protected` before
  existence check); chart name/repo DNS-1123 + repo URL http(s) enforced
  (502 `invalid_package_source`); request `package_id` vs upstream matched
  (422 `package_mismatch`); tests updated/added — 38 install/package tests pass.

**Step 3 — Worker claim-time guard.**
- File: `backend/app/jobs/worker.py`
- `_process_claimed_job` validates `job.chart_name`, `job.chart_repository`,
  `job.namespace`, `job.release_name` against the DNS-1123 pattern and
  `job.chart_repository_url` against the http(s) scheme before
  `_run_helm_install`; on failure mark the job failed with a "refusing to run
  helm: invalid job fields" style message and skip execution. Keep the existing
  empty-`chart_repository_url` failure path and list-argv execution.
- Tests in `tests/test_worker.py` (seed one malformed job, e.g.
  `release_name="Bad Name"`, monkeypatch `_run_helm_install` to raise if
  called): the job ends `failed`, `_run_helm_install` is not called, and the
  error message names the invalid field.
- Done when:
  `cd backend && .venv/bin/python3 -m pytest tests/test_worker.py` passes with
  the new tests, and a malformed job fails without executing Helm.
- [x] Done: claim-time DNS-1123 + http(s) guard in `_process_claimed_job`;
  malformed jobs fail with `refusing to run helm: invalid job field ...` and
  never invoke Helm — 14 worker tests pass.

**Step 4 — Frontend 403 surfacing and full Verify.**
- File: `k8s-ui/components/install-dialog.tsx`
- Confirm the install submit error path renders the backend detail `message`
  when present (403 "Insufficient permissions for the required role"); add a
  fallback label only if the path cannot reach it. No role-based hiding.
- Run the declared Verify: `cd backend && .venv/bin/python3 -m pytest` and
  `cd k8s-ui && yarn verify`; also `cd k8s-ui && yarn lint` (must stay at 0
  errors, pre-existing warnings allowed).
- Done when: backend suite **216 + new tests** passes, frontend build and lint
  pass, and the dialog path for a 403 shows the permission message.
- [x] Done: submit path already surfaces the backend detail `message` in the
  `role="alert"` banner (`install-dialog.tsx` submit → `body.message` → error
  banner), so a 403 `insufficient_permissions` shows the message with no code
  change; full Verify + lint pass.

### Files / areas

- `backend/app/core/rbac.py` — new `MARKETPLACE_INSTALL` permission + operator grant.
- `backend/app/api/v1/marketplace.py` — permission gate, namespace protection,
  metadata trust validation, package_id match.
- `backend/app/jobs/worker.py` — claim-time field guard before Helm execution.
- `backend/tests/test_marketplace.py`, `backend/tests/test_worker.py` — focused
  security tests.
- `k8s-ui/components/install-dialog.tsx` — surface 403 detail message.
- No schema or migration changes; `InstallationJob` fields unchanged.

### Data / contracts

- New error codes:
  - 403 `insufficient_permissions` (existing `require_permission` contract).
  - 403 `password_change_required` (existing restricted-session contract).
  - 422 `namespace_protected` — `namespace == "kube-system"`.
  - 422 `package_mismatch` — request `package_id` ≠ Artifact Hub `package_id`.
  - 502 `invalid_package_source` — upstream chart name/repository/URL fails the
    trust patterns.
- Install order: 401/403 (auth/permission) → 404 `cluster_not_found` → 422
  `namespace_protected` → 422 `namespace_not_found` → 502 upstream/untrusted
  source → 422 `version_not_available`/`package_mismatch` → 201 queued.
- Read endpoints (`/marketplace/packages`, `/versions`, `/installations`,
  `/installations/{id}`) stay auth-only (viewer-readable) — unchanged.

### Testing

- Backend: role/restricted tests (Step 1), protection + metadata tests
  (Step 2), worker guard tests (Step 3); runners configured (pytest).
- Frontend: no test runner (per AGENTS.md); verified via `yarn verify` (build),
  `yarn lint`, and manual 403 confirmation path (login as a viewer and attempt
  an install from the dialog).

### Notes for the AI

- Preserve the unrelated uncommitted edit in
  `k8s-ui/components/dashboard-shell.tsx` (working tree, not part of this spec)
  — do not stage or modify it.
- Viewer login tests need a non-admin `UserAccount` + session: mirror the
  seeding in `tests/test_users.py` (password hashes + `login()` helper reuse in
  `tests/test_marketplace.py`).
- `ROLE_PERMISSIONS` grants `operator` the marketplace install right; do not add
  it to a stored field — it is code-only.
- Keep Helm execution list-argv (`subprocess.run` without `shell=True`); the
  guard is offense-if-a-bad-row-exists, not a shell-escape layer.
- The fake `cluster_client` namespaces list is mutable; extend it rather than
  adding `kube-system` to every happy-path fixture.

### Open questions

- **Who may install per role?** Default: `operator` and `admin` (viewer denied),
  matching the existing mutation grants (`RESOURCES_CREATE/UPDATE/DELETE`).
  Confirm this is correct for 18k before implementation starts. Alternative:
  installs require `admin` only. This changes Step 1's grant and the viewer/operator tests.