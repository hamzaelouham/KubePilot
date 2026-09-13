# Feature 19d: Helm release upgrades

**Branch:** `feature/helm-release-upgrades`
**Status:** verified

## Goal

Allow admins and operators to upgrade an installed Helm release discovered in
the selected cluster and namespace. Each upgrade explicitly selects one
KubePilot-managed global repository, chart name, and chart version. Before a
background job is queued, the backend resolves and validates that chart source.

Upgrades preserve the release's currently deployed Helm values by reusing the
existing values. 19d does not expose a custom values editor or accept a values
payload from the browser.

## Design reference, only for visual or replication work

Reuse the existing Manage resources Helm releases experience: release detail
dialog, shadcn/ui/Base UI Dialog, Select, Input, Button, Badge, confirmation,
background-job progress, and toast patterns. The upgrade flow should use the
same spacing, typography, borders, status colors, focus behavior, and error
hierarchy without changing the page layout.

## In scope

- Add an Upgrade action to the selected release's existing Helm management
  surface for admins/operators.
- Keep viewers read-only: they can continue to inspect releases/history but see
  no upgrade controls and receive a backend permission denial if they call the
  mutation endpoint.
- Load the global KubePilot-managed repository list independently of cluster
  and namespace selection, then require an explicit repository selection.
- Collect and validate a chart name and chart version for every upgrade.
- Require exact release-name confirmation before queuing the operation.
- Resolve the selected repository, chart, and version through a bounded backend
  Helm adapter operation before creating a job; do not infer a source from the
  live release's current chart or from Marketplace history.
- Queue the upgrade through the existing `InstallationJob` worker and status
  pipeline, recording a source snapshot on the job.
- Execute an allowlisted Helm upgrade that uses `--reuse-values`, waits for
  completion, applies the configured timeout, and uses the selected cluster's
  backend-only kubeconfig when required.
- Capture bounded command output and expose queued/running/succeeded/failed
  progress through the existing installation status/log surfaces.
- Add queued/succeeded/failed upgrade audit events with selected cluster,
  namespace, release, repository, chart, version, and operation identity.
- Reject a second pending upgrade/rollback/uninstall for the same
  cluster/namespace/release with the established conflict response.
- Handle loading, empty, unavailable, invalid, forbidden, conflict, source
  resolution failure, and unexpected-error states in the established UI/API
  patterns. Refresh release inventory after a successful upgrade.
- Ensure changing the selected cluster remounts the release workspace and
  cannot reuse an old upgrade target, repository selection, or job state.

## Out of scope

- Custom Helm values, values YAML editing, `--set` overrides, or values import.
- Installing, rolling back, uninstalling, or deleting releases.
- Revision picking or arbitrary rollback targets.
- Persisting a release-to-repository association or modifying the global
  repository configuration model from Feature 19c.
- Private repositories, repository credentials, secret handling, or exposing
  Kubernetes/Helm credentials to the browser.
- Upgrading a release without an explicit repository, chart, and version.
- Changes to Marketplace discovery/install behavior or unrelated Manage
  resources layout redesign.

## Build loop

Work on branch `feature/helm-release-upgrades`, implementing the steps below in
order. Keep each step reviewable, run its narrowest relevant check, and inspect
the diff for authorization, target scope, command safety, redaction, and stale
state. With `workflow.stepReview: "feature"`, continue through passing steps
and present one final review packet. Checkpoint commits are disabled. Do not
merge, push, deploy, or start a development server from this feature.

## Build steps

- [x] 1. **Backend upgrade contract and source resolution** — extend the Helm
  release schemas/API and adapter to accept an explicit repository ID, chart,
  version, and release confirmation; validate the selected cluster/release,
  repository ownership/global scope, safe chart/version inputs, and chart
  availability before queuing. Add upgrade audit event names and pending-action
  conflict handling.

  **Done when:** authenticated admin/operator requests can resolve a valid
  repository/chart/version and invalid, missing, unavailable, unauthorized, or
  stale targets return the established typed error responses without creating a
  job; viewer and concurrent-action requests are denied/conflicted.

- [x] 2. **Upgrade job and worker execution** — extend `InstallationJob` action
  serialization/status responses and worker dispatch for `upgrade`. Snapshot
  the selected repository name/URL, chart, and version on the job, run the
  allowlisted repo setup/update plus `helm upgrade ... --reuse-values` with
  bounded logs, timeout, kubeconfig cleanup, and success/failure audits.

  **Done when:** a queued upgrade transitions through the existing job states,
  preserves deployed values by using `--reuse-values`, records bounded output
  and error text, cleans temporary kubeconfig files, and emits the matching
  queued/succeeded/failed audit events; unknown or malformed jobs fail safely.

- [x] 3. **Manage resources upgrade UI and progress** — add the role-aware
  Upgrade action and dialog to the Helm releases view. Fetch global repositories,
  collect chart/version, show a review summary that states deployed values will
  be preserved, require exact-name confirmation, queue the request with the
  selected cluster/namespace, and reuse the existing progress/log polling and
  toast patterns. Refresh live releases after success.

  **Done when:** admins/operators can complete a reviewed upgrade request from
  a live release, viewers have no action control, repository/chart/version and
  release-target errors are announced in the dialog, pending work disables
  unsafe controls, progress is visible through completion/failure, and a
  cluster change cannot retain the previous target.

- [x] 4. **Focused regression coverage and final verification** — add backend
  API/adapter/worker tests and update frontend-compatible schemas/types for the
  upgrade action, then run the exact project Verify command.

  **Done when:** focused tests cover authorization, explicit source resolution,
  values preservation, command argument safety, conflict handling, job/audit
  lifecycle, and viewer behavior; `cd backend && .venv/bin/python3 -m pytest && cd k8s-ui && yarn verify` passes.

## Files / areas

- `backend/app/api/v1/helm_releases.py` and
  `backend/app/api/v1/helm_release_schemas.py` for the upgrade endpoint,
  request/response contract, source resolution, authorization, and conflicts.
- `backend/app/kubernetes/helm.py` for bounded chart-source resolution and
  validated Helm command integration.
- `backend/app/models/entities.py` only if compatible job metadata requires a
  schema extension; reuse existing repository/chart/url/version snapshot fields
  and avoid a release-association foreign key.
- `backend/app/jobs/worker.py` for upgrade dispatch, `--reuse-values`, bounded
  logs, kubeconfig handling, and audit lifecycle.
- `backend/app/core/audit.py` and existing permission definitions for upgrade
  audit events and the admin/operator release-management boundary.
- `backend/app/api/v1/marketplace_schemas.py` and related status/log routes for
  the shared `upgrade` action serialization.
- `backend/tests/test_helm_releases.py`, `backend/tests/test_worker.py`, and
  focused upgrade tests for backend behavior.
- `k8s-ui/components/helm-releases-view.tsx` and existing dialog/progress
  components for the upgrade experience.
- `k8s-ui/lib/helm-releases.ts`, `k8s-ui/lib/helm-repositories.ts`, and the
  existing Next.js proxy routes for typed same-origin requests.

## Data / contracts

- Upgrade request: explicit selected-cluster query scope, release namespace,
  release name/path, `repository_id` UUID, `chart_name` string, `version`
  string, and exact `confirm_name` string. The trusted actor comes from the
  FastAPI session dependency, never from the body.
- Repository lookup is global and reads the Feature 19c `HelmRepository`
  record. The selected cluster and namespace scope the release only; they do
  not filter repositories.
- Chart names must be bounded safe Helm chart segments; versions must be
  bounded non-empty strings without whitespace/control characters. The backend
  remains authoritative and passes only validated list arguments to Helm.
- Source resolution must verify the repository URL and requested chart/version
  before job creation. A failed resolution creates no upgrade job and does not
  report the operation as queued.
- Upgrade jobs use `action="upgrade"`, `package_id=None`, the selected
  repository name and URL snapshot, chart name/version, selected cluster,
  namespace, and release name. No persistent release-to-repository association
  is created.
- The worker runs repository setup/update and upgrade with `--reuse-values`,
  `--wait`, and the configured timeout. It never accepts a browser-provided
  command, arbitrary flag list, values YAML, or credentials.
- Upgrade status uses the existing `queued`, `running`, `succeeded`, `failed`,
  and `cancelled` lifecycle and existing job/log response shape, extended to
  serialize `action="upgrade"`.
- Audit events identify queued, succeeded, and failed upgrade operations and
  include operation ID and target/source metadata. No kubeconfig, token,
  password, or secret is written to job logs, API responses, or audit context.

## Testing

- Backend API tests for admin/operator success, viewer denial, authentication,
  explicit cluster/namespace/release validation, exact-name confirmation,
  repository lookup/global scope, chart/version source resolution, conflict
  handling, and no-job-on-resolution-failure behavior.
- Helm adapter/worker tests for safe argv construction, repository setup,
  `--reuse-values`, timeout/error/log bounds, status transitions, audit events,
  malformed jobs, and kubeconfig cleanup.
- Frontend build/type checks for the upgrade action, repository loading and
  empty/error states, form validation, progress handling, toasts, and role
  visibility. No browser test runner is configured.
- Final gate: `cd backend && .venv/bin/python3 -m pytest && cd k8s-ui && yarn verify`.

## Notes for the AI

- Preserve the existing Helm releases layout and use existing shadcn/ui/Base UI
  primitives and Tailwind tokens. Keep the upgrade dialog compact and readable.
- Reuse `Permission.MARKETPLACE_RELEASE` unless repository evidence shows a
  specific existing release-management permission should be extended; do not
  weaken viewer read-only behavior.
- Treat live Kubernetes/Helm state as authoritative for the release target.
  Repository configuration is application-global and must never be inferred
  from live release inventory or Marketplace installation history.
- Preserve deployed values explicitly with `--reuse-values`; do not add a
  values editor or silently reset values.
- Keep source resolution and all Helm execution in FastAPI/worker code. Use
  `shell=False`, bounded output, safe argument lists, configured timeouts, and
  backend-only kubeconfig files with cleanup.
- Catch expected API/Helm failures at their boundary and surface typed error
  states; unexpected failures must reach the app's unexpected-error path.
- After modifying code, run `graphify update .` as required by the repository
  instructions.
