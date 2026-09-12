# Feature 19b — Installed Helm release management

**Feature:** 19b — Installed Helm release management

**Status:** verified

**Branch:** `feature/installed-helm-release-management`

## Goal

Extend **Manage resources** with a Helm releases tab that reads the selected
cluster's live Helm inventory across all namespaces, shows release status and
revision history, and lets admins/operators queue confirmed rollback or
uninstall actions for any installed release, including releases not installed
through KubePilot.

## In scope

- Add live Helm release discovery for the explicitly selected active registered
  cluster using the backend Helm binary and `helm list --all-namespaces`.
- Show release name, namespace, status, current revision, chart, app version,
  update time, and a safe description when Helm provides them.
- Show a selected release's `helm history` entries, including revision, update
  time, status, chart, app version, and description.
- Queue rollback to the previous revision and uninstall through the existing
  `InstallationJob`, worker, progress/status, audit, and Background jobs
  pipeline. No Marketplace installation record is required.
- Add the Helm releases tab, loading/empty/denied/error states, release detail
  and history dialog, confirmation flow, refresh behavior, and responsive
  shadcn/ui/Tailwind presentation within the existing Manage resources shell.
- Preserve viewer read access and hide mutation controls from viewers while
  keeping backend permission checks authoritative.

## Out of scope

- Helm repository configuration, chart source association, upgrades, values
  editing, or chart installation; these belong to 19c or Marketplace.
- A revision picker or arbitrary rollback target; rollback always requests the
  previous Helm revision, matching the existing Marketplace release action.
- Managing releases from the application database as an inventory source;
  Kubernetes/Helm remains authoritative.
- Scale, restart, delete-and-recreate, force deletion, finalizer removal, or
  changes to Kubernetes resource types delivered in 19a.
- New background queue technology, browser-test infrastructure, or a separate
  audit-log UI.

## Build loop

Use the existing Next.js 16, TypeScript, Tailwind, shadcn/ui/Base UI, FastAPI,
SQLAlchemy, Kubernetes/Helm, and Alembic conventions. `workflow.stepReview` is
`feature` and checkpoint commits are disabled, so implementation may continue
through the small steps and stop with one feature-level review packet. Do not
commit, merge, or push from `/implement`; `/complete` owns the work commit.

## Build steps

- [x] **Define live Helm contracts and external action-job persistence.** Add
  typed backend schemas and a Helm service/adapter for safe list/history JSON
  commands, explicit active-cluster resolution, request-local kubeconfig
  handling, bounded/sanitized errors, and stable release/history responses.
  Extend `InstallationJob` so rollback/uninstall jobs created from live releases
  do not require Marketplace package/chart metadata, while existing Marketplace
  rows and API responses remain compatible. Add migrations and focused backend
  tests. **Done when:** authenticated release/list and history contracts are
  defined, malformed or unsafe Helm output cannot escape as raw errors, external
  action jobs can be persisted without a Marketplace source row, and focused
  backend tests pass.

- [x] **Add authorized release discovery and job-driven actions.** Implement
  FastAPI list/history/action routes under the cluster Helm API, requiring an
  explicit active registered cluster and `resources:read` for reads plus the
  existing admin/operator release permission for mutations. Validate
  DNS-compatible release/namespace path values and exact confirmation names;
  reject missing releases, inactive clusters, pending actions, and stale
  targets before queueing. Reuse the existing worker's safe rollback/uninstall
  commands, status polling, bounded logs, and audit intent/result events, with
  distinct Helm-release audit context. Add same-origin Next.js proxies. **Done
  when:** viewers can read live releases/history but cannot queue actions,
  admins/operators can queue only confirmed previous-revision rollback or
  uninstall actions for a live target, action jobs appear in Background jobs,
  and backend/API tests cover auth, scope, conflicts, and worker outcomes.

- [x] **Build the Manage resources Helm releases tab.** Add a tab to the
  existing `ManageResourcesView` that lists all releases in the selected
  cluster, keeps the Kubernetes resource namespace behavior intact, and clears
  release rows, history, and pending dialogs on cluster changes. Add searchable
  release inventory, status badges, detail/history dialog, refresh, empty,
  loading, denied, invalid-target, and unexpected-error states. Reuse the
  existing release progress dialog or a focused equivalent and route completed
  actions to the live inventory refresh. **Done when:** `/manage-resources`
  reaches the Helm releases tab without changing the shell layout; a release
  from any namespace opens its history; protected role behavior and exact-name
  confirmation are visible; and responsive UI/build checks pass.

## Files / areas

- `backend/app/api/v1/helm_releases.py` and
  `backend/app/api/v1/helm_release_schemas.py` for live Helm contracts and
  routes; `backend/app/main.py` for router registration.
- `backend/app/kubernetes/` and `backend/app/jobs/worker.py` for safe Helm
  command execution, cluster-local credentials, external action dispatch, and
  bounded output.
- `backend/app/models/entities.py` and
  `backend/alembic/versions/` for the compatible external action-job model.
- `backend/app/core/rbac.py` and `backend/app/core/audit.py` only for the
  existing release permission and new accurately named audit events.
- `backend/tests/test_helm_releases.py`, `backend/tests/test_worker.py`, and
  relevant Marketplace/resource tests for contracts and regressions.
- `k8s-ui/components/manage-resources-view.tsx`, a new focused Helm release
  component/dialog as needed, and existing `data-table`, `release-action-dialog`,
  `dashboard-shell`, and theme primitives.
- `k8s-ui/lib/resource-management.ts` or a focused Helm helper plus
  `k8s-ui/app/api/cluster/helm/` same-origin proxy routes.

## Data / contracts

The backend is the only component that invokes Helm. Every request carries one
explicit `cluster=<registered-name>` query value; the backend resolves that
name to an active `ClusterConnection` before building the command and uses only
that record's request-local kubeconfig or in-cluster configuration. The browser
never receives kubeconfig, endpoint credentials, or arbitrary command arguments.

Use these stable response shapes:

- `GET /api/v1/cluster/helm/releases?cluster=<name>` requires
  `resources:read` and returns `{items: HelmReleaseSummary[]}`.
- `GET /api/v1/cluster/helm/releases/{release}/history?cluster=<name>&namespace=<ns>`
  requires `resources:read` and returns
  `{release_name, namespace, revisions: HelmReleaseRevision[]}`.
- `POST /api/v1/cluster/helm/releases/{release}/rollback` and `/uninstall`
  require `marketplace:release` and accept exactly
  `{confirm_name: string}` plus the explicit cluster and namespace query
  values. They return the existing `{job_id: UUID-string, status: "queued"}`
  shape without waiting for Helm.

`HelmReleaseSummary` contains `name`, `namespace`, `status`, `revision`,
`chart`, `app_version`, `updated`, and `description` as nullable safe display
values where Helm omits them. `HelmReleaseRevision` contains `revision`,
`updated`, `status`, `chart`, `app_version`, and `description`; numeric revision
values remain integers and Helm-provided timestamps remain normalized strings.
Unknown fields from Helm are ignored; malformed JSON is a sanitized backend
error.

For an action created from live inventory, `InstallationJob` keeps required
target fields (`cluster_id`, `namespace`, `release_name`, `action`, `status`,
timestamps, error, and bounded log output) and permits Marketplace-only
package/chart metadata to be null. Existing Marketplace install rows continue
to populate all current metadata. The queue records the live chart/version
when available and the current revision as informational metadata; rollback
still targets the previous revision through the existing worker command.

Use existing error envelope `{code, message}`: authentication/permission
errors retain current 401/403 behavior; unknown/inactive cluster is
`cluster_not_found`; invalid route/query/confirmation input is a 422 typed
validation error; missing live release is `release_not_found`; an already
queued/running action is `release_action_conflict`; sanitized Helm failures are
`helm_unavailable` or `helm_error`. Preserve `operation_outcome_unknown` when
the queue or action result cannot be established. Render all names, Helm
descriptions, errors, and logs as escaped text.

Audit the actor, resolved cluster UUID/name, namespace, release, action, and a
server-generated operation identifier. Persist the queued intent before the
worker is allowed to mutate Helm; record success, failure, or unknown result
without raw command output, credentials, or request-controlled identity.

## Testing

Run the repository's declared backend pytest suite and frontend `yarn verify`;
the root Verify line has a known sibling-directory typo, so use its corrected
equivalent from the repository root:

```sh
cd backend && .venv/bin/python3 -m pytest && cd ../k8s-ui && yarn verify
```

Add focused backend coverage for:

- Helm list/history parsing, empty inventory, malformed/unknown output,
  nonzero/timeout/missing-binary behavior, bounded error/log redaction, fixed
  argument ordering, per-cluster kubeconfig isolation, and no shell expansion.
- Signed-cookie admin/operator/viewer behavior, restricted/deactivated users,
  explicit cluster resolution, inactive/unknown cluster, namespace/release
  validation, missing live target, pending-action conflict, exact confirmation,
  and direct API permission enforcement.
- External rollback/uninstall jobs without Marketplace source rows, migration
  compatibility with existing jobs, worker queued/running/succeeded/failed
  transitions, previous-revision rollback, uninstall, audit events, and
  operation-outcome handling.
- Existing Marketplace installation/release actions, resource management,
  cluster routing, authentication, and audit regressions.

The frontend has no configured browser test runner. Do not add one for 19b;
manual evidence must use an explicitly selected disposable cluster and release
when a running environment is available.

## Notes for the AI

- Keep live release inventory separate from `InstallationJob` history; an
  external release must remain visible even when it has no KubePilot job.
- The Manage resources Helm tab is cluster-wide across namespaces. The existing
  shell namespace selector remains relevant to the Kubernetes resources tab but
  must not hide releases from other namespaces; show namespace in every release
  row and action target.
- Reuse the existing `MARKETPLACE_RELEASE` permission for rollback/uninstall so
  role behavior stays compatible; do not grant viewers mutation access.
- Use the existing worker/job status and Background jobs log/progress pipeline;
  do not add Celery/RQ or synchronous Helm mutations to the browser.
- 19c owns repository storage, chart-source association, upgrade values, and
  chart upgrades. Do not add placeholders for those flows.
