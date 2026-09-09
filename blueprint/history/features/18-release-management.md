# Current Feature

**Feature 18m - Release management (backend)**

**Branch:** `feature/release-management-backend`

> **Status:** verified - all build steps checked; Verify green (backend 245 passed, `yarn verify` build+lint+typecheck clean).

## Goal

After a Marketplace install completes (job status `succeeded`), an admin or operator can roll a release back to its previous revision or uninstall (delete) it. Both run through the existing job-driven Helm pipeline: a queued `InstallationJob` claimed by the background worker, with status and audit surfaced through the existing install status/history API. Viewers and restricted sessions are denied.

## In scope

- Backend only. No UI changes (that is 18n).
- Extend `InstallationJob` with `action` (`install` | `rollback` | `uninstall`, default `install`) and nullable `revision` via one backward-compatible Alembic migration (`down_revision: d1e2f3a4b5c6`).
- Worker dispatch by `action`:
  - `install` - unchanged existing path (repo add/update + `helm install`, full field guard).
  - `rollback` - `helm rollback <release> --namespace <ns> --wait --timeout <helm_install_timeout_seconds>s`; previous revision (Helm default, no revision argument).
  - `uninstall` - `helm uninstall <release> --namespace <ns>`; no `--wait` (helm returns once deletion is enqueued).
- Two new endpoints, gated by a new `marketplace:release` permission (operator + admin):
  - `POST /api/v1/marketplace/installations/{job_id}/rollback`
  - `POST /api/v1/marketplace/installations/{job_id}/uninstall`
  - Both create a new queued `InstallationJob` whose target (`cluster_id`, `namespace`, `release_name`) is copied from the referenced source job - never from client text.
- Audit events for queued/succeeded/failed rollback and uninstall.
- Status response gains an `action` field so the 18n UI can tell job kinds apart.

## Out of scope

- Revision picker / `helm history`; upgrades; releases the app did not install (nothing outside a known `InstallationJob` row); frontend changes; 18l polish, 18n UI.

## Build loop

- Branch: `feature/release-management-backend`. Per `blueprint/config.json`: `checkpointCommits` disabled (no checkpoint commits), `stepReview: feature` (one review checkpoint after all implementation steps; `/complete` creates the final feature commit).
- Quality gates (`regular`): audit, independent review, check, try guide are all `manual` - run only when explicitly requested. Logic tests per existing test command; no browser tests in this project.

## Build steps

- [x] 1. **Model + migration** - add `action` (String(32), non-null, default + server both `"install"`) and `revision` (nullable Integer) to `InstallationJob` in `backend/app/models/entities.py;`; new Alembic revision `d1e2f3a4b5c6_...` adding both columns (server_default keeps existing rows `install`).
   - Done when: `cd backend && PYTHONPATH=. alembic upgrade head --sql` shows the new columns only, and `cd backend && python3 -m compileall -q app` is clean.
- [x] 2. **Permission + audit** - add `Permission.MARKETPLACE_RELEASE = "marketplace:release"` to `backend/app/core/rbac.py` and to the `Role.OPERATOR` set (admin keeps `ALL_PERMISSIONS`); update the operator matrix in `tests/test_rbac_permissions.py`. Add `MARKETPLACE_ROLLBACK_QUEUED/SUCCEEDED/FAILED` and `MARKETPLACE_UNINSTALL_QUEUED/SUCCEEDED/FAILED` to `AuditEvent` in `backend/app/core/audit.py`.
   - Done when: the rbac permissions test asserts operator `marketplace:release`, viewer denied; audit events compile.
- [x] 3. **API endpoints** - reuse `MarketplaceInstallResponse` for both new routes. Add `action: Literal["install","rollback","uninstall"] = "install"` to `MarketplaceInstallationStatus` in `backend/app/api/v1/marketplace_schemas.py`. In `backend/app/api/v1/marketplace.py` add the two POST routes with `require_permission(Permission.MARKETPLACE_RELEASE)`, resolving the source job, then:
   - source missing -> 404 `installation_not_found`
   - cluster inactive -> 404 `cluster_not_found`
   - source `action != install` -> 422 `invalid_source_job`
   - source `status != succeeded` -> 422 `install_not_completed`
   - existing queued/running `InstallationJob` with same `cluster_id` + `namespace` + `release_name` -> 409 `release_action_conflict`
   - else create the job (copy `cluster_id`, `namespace`, `release_name`, and display fields `package_name`, `chart_name`, `chart_repository`, `chart_version`; `chart_repository_url` null), commit, record the QUEUED audit with `actor_id`, return 201 `{job_id, status: "queued"}`.
   - Done when: backend tests cover viewer/restricted 403, 404, both 422s, 409, and 201+audit.
- [x] 4. **Worker dispatch** - in `backend/app/jobs/worker.py` extract a shared single-command runner (timeout / OSError / error-cap trimming from `_run_helm_install`), add `_run_helm_rollback` and `_run_helm_uninstall` (list-argv as above, `--kubeconfig` when `cluster.kubeconfig_content` set, same temp-file 0600 + cleanup), guard non-install jobs with a DNS-1123 check on `namespace` + `release_name` only, branch `_process_claimed_job` by `action` (unknown action fails the job), and parameterize `_fail_job` audit events by action.
   - Done when: worker tests record rollback success/failure and uninstall success/failure with the exact helm argv, invalid namespace fails without helm, and install path is unchanged.
- [x] 5. **Full Verify** - `cd backend && .venv/bin/python3 -m pytest` and `cd k8s-ui && yarn verify`.
   - Done when: both pass (baseline entering this feature: backend 230 passed, `yarn verify` build+lint+typecheck clean).

## Files / areas

- `backend/app/models/entities.py` (`InstallationJob`)
- `backend/alembic/versions/<new>_add_installation_job_action.py` (new, `down_revision: d1e2f3a4b5c6`)
- `backend/app/core/rbac.py`, `backend/app/core/audit.py`
- `backend/app/api/v1/marketplace.py`, `backend/app/api/v1/marketplace_schemas.py`
- `backend/app/jobs/worker.py`
- `backend/tests/test_marketplace.py`, `backend/tests/test_worker.py`, `backend/tests/test_rbac_permissions.py`

## Data / contracts

- `InstallationJob`: `action` String(32) default/server-default `"install"`; `revision` Integer nullable. Rollback uses previous revision - the column is reserved for a future revision target and is unused by this feature.
- Job statuses unchanged (`queued/running/succeeded/failed/cancelled`); `requeue_running_jobs` keeps working generically for any action.
- Rules of operation:
  - Trusted actor for mutations: authenticated session with `marketplace:release`; restricted sessions 403 `password_change_required` (from `require_permission`).
  - Target lineage always from the stored source job; never from request text. Kubernetes access stays in the backend; kubeconfig temp file 0600 and unlinked in `finally`.
  - Mutations are never run the moment the worker is a simple poller: obtain claim via `claim_next_job` (atomic update), so one release action executes at a time per job row.
  - 409 idempotency guard prevents double-queued destructive jobs on the same release.
  - Rollback/uninstall jobs copy display fields so the status/history shape stays uniform; `chart_repository_url` is intentionally null for non-install jobs (install path still requires it).
  - Error messages trimmed to 4096 chars via existing `_trim`.

## Testing

- `backend/tests/test_marketplace.py` - permission denials (viewer, restricted session), 404 unknown/inactive, 422 non-install source + not-succeeded source, 409 conflict, 201 queued with copied fields + `action` in the created row + queued audit event.
- `backend/tests/test_worker.py` - rollback/uninstall happy path (argv asserted), failure path + failed audit, invalid namespace/release guard without touching helm, unknown-action job fails, kubeconfig temp file written/unlinked.
- `backend/tests/test_rbac_permissions.py` - `marketplace:release` in the operator matrix, absent for viewer.
- Backend-only feature: no frontend tests are affected; existing status schema adds a defaulted `action` field.

## Notes for the AI

- Baseline entering the feature: backend `230 passed`; `yarn verify` clean; branch `feature/release-management-backend` from `master` at `26324f8`.
- The `action` flag will drive 18n UI rows; keep names stable (`install` | `rollback` | `uninstall`).
- Install path must remain byte-for-byte behavior-equivalent; existing worker tests guard this.
- Do not start the dev server; verification is the pytest + `yarn verify` gate above.

## Open questions

- Should rollback/uninstall also be offered for a **failed** install (partial resources left behind)?
  Default taken in this spec: `succeeded` only, per the plan wording ("once an install completes"). Cleanup of failed partial installs would be a follow-up. Flag in the review handoff.