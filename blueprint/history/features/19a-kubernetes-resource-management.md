# Feature 19a - Kubernetes resource management

Archive of build-plan sub-feature 19a. **Status:** verified, completed and ready for merge.


**Feature:** 19a — Kubernetes resource management
**Branch:** feature/kubernetes-resource-management
**Status:** verified
**Branch:** feature/kubernetes-resource-management Live UI/cluster evidence remains unobserved.

## Goal

Give admins and operators a "Manage resources" sidebar section where they can list, create through YAML, and delete supported Kubernetes resources in the selected registered cluster. Viewers can inspect the same inventory but cannot mutate it. FastAPI owns authorization, target resolution, validation, Kubernetes calls, and audit recording.

## In scope

- `/manage-resources`, using the existing dashboard shell and cluster/namespace controls, with an active Kubernetes resources tab.
- Eight resource types drawn from the current workload/resource UI: Pods, Deployments, Namespaces, Services, StatefulSets, DaemonSets, Jobs, and CronJobs. This uses the narrower scope proposed during planning; the optional ConfigMap/Secret/Ingress/PVC expansion was not selected.
- Live inventory, type selection, namespace filtering, existing DataTable filtering/pagination, refresh, creation from one YAML resource, and confirmation before individual deletion.
- Existing admin/operator `resources:create` and `resources:delete` permissions; viewer access through `resources:read`. No new role, grant, or per-user cluster assignment model.
- User-confirmed protection for both admins and operators: block creation/deletion in `kube-system`, `kube-public`, `kube-node-lease`, and KubePilot's hosting namespace; block creation/deletion of those Namespace objects themselves; also block deletion of the `default` Namespace. Ordinary supported resources in `default` remain manageable. Protected inventory remains readable.
- Explicit cluster targets, namespace validation, per-operation Kubernetes client configuration, UID-based deletion preconditions, sanitized errors, and durable audit intent/results.
- Loading, empty, invalid, denied, unreachable, conflict, unknown-outcome, and deletion-in-progress states. Changing cluster/type/namespace invalidates pending confirmation and stale data.

## Out of scope

- Helm release discovery, history, rollback/uninstall, repositories, and upgrades: 19b/19c. Do not add nonfunctional Helm controls or placeholder actions in this item.
- ConfigMaps, Secrets, Ingresses, PVCs, PVs, Nodes, RBAC objects, ServiceAccounts, custom resources, and every type outside the explicit management allowlist. Existing read-only dashboard views remain available.
- Editing/applying/replacing existing objects, scale/restart, multi-document or `List` manifests, bulk deletion, arbitrary kubectl execution, force deletion, finalizer removal, or custom deletion propagation controls.
- Visual YAML builders, sample application/image presets, manifest storage, a new job system, audit-log UI, new test runners, or changes to existing Marketplace behavior.
- Commits, merge, push, deployment, or live mutations of an unspecified cluster as part of writing this spec.

## Build loop

- Follow `workflow.stepReview: feature`: implement and verify the small steps, then present one review packet for the complete item.
- `workflow.checkpointCommits: disabled`: no checkpoint commits. `/complete` handles the final feature commit after the required review/gates.
- Regular audit, independent review, check, and try-guide gates are all `manual`; invoke them only when requested.
- Preserve the approved, currently uncommitted changes to `blueprint/project-plan.md`, `blueprint/build-plan.md`, and `blueprint/context/project-overview.md`. They belong to this planning conversation; do not discard or silently commit them.

## Build steps

1. [x] **Define management schemas, resource dispatch, and namespace policy.** Add narrow management schemas and a backend adapter using the mapping below. Implement safe single-object YAML parsing, identity/scope checks, and one protection helper shared by every mutation. Add hosting-namespace configuration and populate it from the backend Pod's namespace in the deployment manifest. Confirm the installed Kubernetes client supports the selected list/create/delete arguments before wiring them.

   **Done when:** focused pytest cases cover all eight mappings, invalid/unsupported YAML, namespace mismatches, every protected name for both mutating roles, allowed resources in `default`, and invalid hosting-namespace configuration. The existing app still starts and its read APIs retain their response contracts.

2. [x] **Expose live management inventory with explicit cluster identity.** Register a separate management router in `app/main.py`. Resolve an active `ClusterConnection` before constructing request-local Kubernetes clients; list the selected type with UIDs and deletion timestamps. Reuse existing status/health interpretation where applicable without making changes to the old resource/namespace response shapes a prerequisite.

   **Done when:** API tests show admin/operator/viewer reads, rejected unauthenticated/restricted requests, correct namespaced/cluster-scoped responses, no fallback for absent/unknown/inactive cluster targets, and independent credentials under interleaved requests to two registered clusters. List responses contain no raw manifests or credentials.

3. [x] **Implement authorized YAML creation and auditing.** Add the create endpoint with the validation, audit, and response contract below. Use Kubernetes create operations with strict server field validation; preserve the submitted resource spec rather than injecting deployment/image defaults. Do not use apply/patch or retry a mutation automatically.

   **Done when:** API/client tests create each supported kind through the correct client and namespace, reject viewers/protected or mismatched targets before mutation, return a conflict for existing names, sanitize Kubernetes validation errors, and record audit intent plus observed outcome. Audit-intent persistence failure prevents the Kubernetes create call.

4. [x] **Implement confirmed, UID-constrained deletion.** Add deletion with exact target-name confirmation and Kubernetes UID preconditions. Preserve Kubernetes grace periods, finalizers, and normal garbage-collection behavior. Report acceptance separately from completed removal.

   **Done when:** tests prove that wrong confirmation, missing UID, viewer access, protected targets, and a replaced object cannot cause deletion; allowed Namespace/workload deletion uses the expected scope and precondition; missing/already-terminating resources have the defined behavior; and audit/error handling covers success, rejection, and uncertain transport outcomes.

5. [x] **Build the Manage resources page and same-origin bridge.** Add the protected server page, management view/table, YAML create dialog, delete AlertDialog, and narrow Next.js proxy routes. Add the sidebar link/title, preserve selected-cluster navigation, and keep namespace changes within this page. Reuse the existing components, theme tokens, authentication helpers, and backend error conventions.

   **Done when:** the production build includes `/manage-resources` and its API routes; the page renders the Kubernetes resources tab and supported type selector; admin/operator controls call only the new proxies; viewers have no mutation controls; namespace/object deletion clearly explains its impact; invalid/error states remain actionable; cluster/scope changes clear stale inventory and confirmation. Verify the running UI when available and report separately which behavior was observed versus inspected.

6. [x] **Verify the complete flow and review.** Finish focused regression coverage for target switching, permission/protection enforcement, request-local client identity, API response redaction, duplicate submission, deletion lifecycle, and audit failure paths. Run the combined backend/frontend gate and inspect the complete diff.

   **Done when:** backend pytest and frontend `yarn verify` pass, `git diff --check` is clean, existing discovery/auth/Marketplace tests remain green, and the review packet states the changed behavior, checks, and any unavailable live/browser evidence. Leave build-plan checkboxes pending until `/complete`.

## Files / areas

Existing integration points:

- `backend/app/core/dependencies.py`: authenticated actor and registered-cluster resolution patterns. Existing read requests permit default-cluster fallback; new management requests must not inherit it.
- `backend/app/core/rbac.py`: reuse `RESOURCES_READ`, `RESOURCES_CREATE`, and `RESOURCES_DELETE` without expanding role grants.
- `backend/app/core/audit.py`, `backend/app/models/entities.py`: extend event names and use existing `AuditAction` storage; no resource inventory table/migration is needed.
- `backend/app/core/config.py`, `backend/deploy/kubernetes/backend.yaml`: hosting namespace setting and downward-API environment wiring.
- `backend/app/kubernetes/client.py`: existing typed clients, list dispatch, and status helpers. Its factory currently uses global default configuration; new management clients must use explicit, isolated `Configuration`/`ApiClient` objects.
- `backend/app/main.py`: register the router and preserve the public `{code, message}` error envelope.
- `backend/tests/test_kubernetes.py`, `test_cluster_routing.py`, `test_rbac_permissions.py`, and `test_end_to_end_rbac.py`: patterns and regression coverage for clients, selected clusters, roles, and real authentication.
- `k8s-ui/components/dashboard-shell.tsx`, `lib/use-cluster-selection.ts`, `lib/cluster-context.tsx`, `lib/cluster-query.ts`: selection, navigation, and namespace refresh. Keep any shared edits focused on management reachability and stale-scope prevention.
- `k8s-ui/lib/auth.ts`, `lib/backend.ts`, `lib/api-error.ts`: protected page, cookie forwarding, and proxy/error helpers.
- `k8s-ui/components/data-table.tsx` and existing `ui/dialog.tsx`, `ui/alert-dialog.tsx`, `ui/button.tsx`, `ui/select.tsx`, `ui/input.tsx`: reuse native UI patterns. No visual redesign or new component system.

Planned additions:

- `backend/app/api/v1/resource_management.py` and `resource_management_schemas.py`.
- `backend/app/kubernetes/resource_management.py` for the allowlisted adapter, validation, and mutation error translation.
- `backend/tests/test_resource_management.py` for behavior and authorization tests; use focused additional client tests if separation improves readability.
- `k8s-ui/app/manage-resources/page.tsx` and `components/manage-resources-view.tsx`.
- `k8s-ui/components/create-resource-dialog.tsx`, `delete-resource-dialog.tsx`, and shared management response types in `lib/resource-management.ts`.
- `k8s-ui/app/api/cluster/manage-resources/[resourceType]/route.ts` for GET/POST and `[resourceType]/[name]/route.ts` for DELETE.

## Data / contracts

### Resource mapping and live identity

Use a fixed backend mapping; neither YAML nor a URL may select arbitrary API methods or endpoints.

| URL resource type | apiVersion | kind | Scope / client |
| --- | --- | --- | --- |
| `pods` | `v1` | `Pod` | Namespaced / CoreV1Api |
| `services` | `v1` | `Service` | Namespaced / CoreV1Api |
| `namespaces` | `v1` | `Namespace` | Cluster / CoreV1Api |
| `deployments` | `apps/v1` | `Deployment` | Namespaced / AppsV1Api |
| `stateful-sets` | `apps/v1` | `StatefulSet` | Namespaced / AppsV1Api |
| `daemon-sets` | `apps/v1` | `DaemonSet` | Namespaced / AppsV1Api |
| `jobs` | `batch/v1` | `Job` | Namespaced / BatchV1Api |
| `cron-jobs` | `batch/v1` | `CronJob` | Namespaced / BatchV1Api |

An object is identified by the resolved cluster UUID, resource type, namespace (null for Namespace), name, and Kubernetes UID. Names alone are insufficient after an object is replaced. [Kubernetes object identity](https://kubernetes.io/docs/concepts/overview/working-with-objects/names/).

`ManagedResource` contains `cluster` (registered name string), `cluster_id` (UUID string), `resource_type` (the allowlist), `api_version`, `kind`, `name`, `namespace` (string/null), `uid` (opaque nonempty Kubernetes UID string), `status` (display string), `health` (existing healthy/warning/error/unknown vocabulary), `deletion_timestamp` (RFC 3339 string/null), and `delete_blocked_reason` (safe string/null computed for the actor/target). These are live response fields, not new database columns. Never return raw specs, annotations, environment values, or Kubernetes credential/configuration data in this inventory.

### Endpoints and authorization

Backend prefix: `/api/v1/cluster/manage-resources`. Browser prefix: `/api/cluster/manage-resources`.

- `GET /{resource_type}?cluster=<registered-name>&namespace=<namespace>` requires `resources:read`; returns `200 {items: ManagedResource[]}`. For namespaced kinds, omit namespace to list across namespaces. For Namespace, namespace must be absent. Return all fetched rows; use the existing DataTable's client pagination and follow Kubernetes continuation tokens if a list call returns them.
- `POST /{resource_type}?cluster=<registered-name>&namespace=<namespace>` requires `resources:create`; JSON body is exactly `{yaml: string}`; returns `201 {status: "created", resource: ManagedResource}` after Kubernetes accepts creation. Namespace creation omits the namespace query parameter; every other kind requires it.
- `DELETE /{resource_type}/{name}?cluster=<registered-name>&namespace=<namespace>` requires `resources:delete`; JSON body is exactly `{uid: string, confirm_name: string}`. `confirm_name` must exactly equal the path name. Returns `202 {status: "deletion_requested", cluster: string, cluster_id: UUID-string, resource_type: string, namespace: string|null, name: string, uid: string}` after Kubernetes accepts the request. Namespace deletion omits the namespace query parameter.

Every endpoint requires a nonempty explicit cluster parameter and resolves it against active database records before constructing a client. Follow existing name-based `cluster` routing; do not mistake it for the database UUID. Reject missing/blank/ambiguous identity parameters. Never accept an endpoint, kubeconfig, role, actor ID, or impersonation setting from the request. Management uses the current global role model across registered clusters; there is no existing tenant or per-user cluster grant to reinterpret.

Authenticate and check the required permission before any Kubernetes work. Restricted/password-change sessions are denied with existing behavior. Construct an isolated Kubernetes configuration from the resolved record (or in-cluster credentials for the configured local connection), and use that same explicit client for the whole operation. Do not change process-global Kubernetes defaults or share mutable authentication state between requests. Verify interleaving with tests rather than relying on single-thread execution.

Next.js proxies forward only the operation's validated route/query fields, JSON body, and signed cookie to a fixed backend path, using `no-store`. Preserve status and the backend response shape; use the existing `503 backend_unavailable` fallback. Never construct a destination from a user-supplied host. The server page calls `requireUsableBackendUser`, following the Marketplace page pattern; do not rely solely on the current proxy matcher, which does not cover this new page.

### YAML creation

- Accept one nonempty YAML document representing one mapping. JSON-form YAML is acceptable. Reject multiple documents, YAML `List` objects, custom tags, duplicate mapping keys, recursive/alias structures, and non-JSON-compatible parsed values. Use PyYAML's safe-loading machinery with explicit validation; never execute YAML constructors or shell commands.
- Require string `apiVersion`, `kind`, and explicit `metadata.name`; require metadata to be a mapping. Match kind/version to the URL type exactly. `generateName` is outside this first create flow so retries always refer to one named target.
- For namespaced kinds, the query namespace is required. If `metadata.namespace` is absent, use that selected namespace; if present, it must match exactly. Namespace resources must not carry `metadata.namespace`. Never create a namespace implicitly as a side effect of creating another resource.
- Reject server-managed identity/lifecycle input (`metadata.uid`, `resourceVersion`, `creationTimestamp`, `deletionTimestamp`, `managedFields`) and top-level `status` instead of silently treating an exported object as an update. Preserve ordinary spec/label/annotation fields and allow Kubernetes admission to validate kind-specific constraints.
- Validate identities as Kubernetes names/path segments, preserving kind-specific rules; do not impose Helm release-name rules on Kubernetes objects. Kubernetes remains authoritative for the resource schema, admission, quotas, and field validation. Use strict server field validation so misspelled/unknown fields are not silently dropped.
- Use create only. Kubernetes name uniqueness is the atomic duplicate boundary: an existing object produces `409 resource_conflict`, never an update or a second generated name. Disable repeated UI submission and do not automatically retry writes after network errors. A timeout can leave an unknown outcome; instruct the user to refresh inventory before deciding to resubmit.
- Raw YAML stays in the open dialog and request memory only. Do not persist it in localStorage, application tables, audit context, or logs; redact upstream errors even for non-Secret kinds because pod specs may contain credentials.

### Protection and deletion

The protection is a server-enforced rule with no admin bypass in 19a. Protect `kube-system`, `kube-public`, `kube-node-lease`, and the configured hosting namespace name across selected clusters, including the corresponding Namespace objects. Also prohibit deleting Namespace `default`; this does not prohibit normal creates/deletes inside `default`.

Add `KUBEPILOT_HOST_NAMESPACE` / `Settings.host_namespace`. The checked deployment runs in `kubepilot`, so use that existing namespace as the non-Pod development fallback. In the backend deployment, populate the setting through `fieldRef: metadata.namespace` so a renamed deployment namespace is protected. Validate the setting as a nonempty namespace name; never derive the protected set from YAML, browser state, or user role. Read visibility is unaffected. Existing Kubernetes RBAC/admission still applies; these target checks are not a replacement for cluster admission policies.

Before deletion, show the fixed cluster, namespace, kind, and name; require the user to type the exact name. Explain that Namespace deletion removes its contents, workload deletion may clean up dependents, and a controller may recreate a deleted Pod. Cancellation performs no request. Changing scope closes/invalidates confirmation and requires a new review.

Use `DeleteOptions.preconditions.uid` with the UID displayed in inventory; do not replace it with a newly read UID. A matching object already marked for deletion may return `deletion_requested` without sending another delete. If it is missing, return `404 resource_not_found` and refresh; if its UID differs, return `409 resource_conflict` and require the new object to be reviewed. The Kubernetes precondition must still protect against replacement after any preliminary read. [Kubernetes DeleteOptions](https://kubernetes.io/docs/reference/kubernetes-api/definitions/delete-options-v1-meta/).

Leave propagation policy and grace periods to Kubernetes's normal deletion behavior; do not set force, remove finalizers, or orphan dependents. An accepted delete does not prove the object and dependents have disappeared. Render `deletion_timestamp` as Terminating while visible and refresh to observe removal. [Kubernetes garbage collection](https://kubernetes.io/docs/concepts/architecture/garbage-collection/).

### Errors and audit

Keep the existing public error envelope `{code: string, message: string}`. Management validation must provide safe, useful messages rather than raw Kubernetes response bodies or echoed manifest content.

| HTTP | Code / meaning |
| --- | --- |
| 401 | `authentication_required` |
| 403 | Existing `insufficient_permissions` / `password_change_required`; `cluster_forbidden` for Kubernetes RBAC |
| 404 | `cluster_not_found` for unknown/inactive cluster; `resource_not_found` for missing delete target |
| 409 | `resource_conflict` for create collision or delete UID mismatch |
| 422 | `invalid_resource_type`, `invalid_resource_identity`, `invalid_namespace_scope`, `invalid_manifest`, `namespace_protected`, or `confirmation_required` |
| 502 | `cluster_error` for a sanitized Kubernetes failure |
| 503 | `cluster_unavailable` / `backend_unavailable`; `audit_unavailable` when audit intent cannot be persisted |
| 504 | `operation_outcome_unknown` when a mutation's result cannot be established after a transport timeout |

Use the existing generic `validation_error` for malformed request envelopes. Report manifest syntax location or field path when available, but do not expose rejected values. Do not pass mutation errors through the existing generic classifier if that would collapse conflicts/validation into an unavailable response.

Audit uses existing `record_audit`/`AuditAction`, with events `resource.create_requested`, `resource.create_result`, `resource.delete_requested`, and `resource.delete_result`. Take the actor from the validated session. Record the resolved cluster UUID/name, type, namespace/null, name, known UID, and a server-generated operation UUID string to correlate intent/result; never accept those audit identities from the client. Use an injectable UUID generator in focused tests.

Persist an intent before sending a Kubernetes mutation; if this fails, send no mutation. Record the observed result (`success`, `failure`, or `unknown`) separately with only safe error codes and returned UID where known. `delete_result` success means the API accepted deletion, not final garbage collection. The database and Kubernetes are not one transaction: if result recording fails after a successful call, preserve the known operation response and the already durable intent, and emit a sanitized server log with its operation ID; never falsely tell the user that an observed successful mutation failed or retry it. Validation/permission/protection denials do not produce success events.

### UI behavior

- Keep one selected cluster shared with the header; do not enable actions until a currently registered selection is resolved. Show a useful no-cluster/unavailable state instead of stale rows.
- Use the existing namespace selector. Namespace inventory ignores the namespace filter; creating a namespaced object requires an explicit namespace. If an all-namespaces view is exposed, each delete still uses the row's namespace and creation asks for one target namespace.
- Keep refresh/read requests keyed by cluster, type, and namespace; cancel or ignore stale responses. On scope change, clear inventory and pending dialogs immediately, then reload. Do not let a response from the previous scope repopulate the new view.
- A write already sent remains attached to its captured target; changing selection cannot cancel a Kubernetes operation. Scope any later feedback to the original target and never insert its result into another cluster's table.
- The create dialog has a labeled YAML textarea, visible target kind/cluster/namespace, pending state, and recoverable inline errors. Preserve the draft after a validation/API failure; clear it on success, explicit cancellation, or target change so it cannot be submitted to an unintended cluster.
- Show readable reasons for protected/terminating rows. Viewers see inventory and a read-only explanation, without create/delete controls. Hiding controls does not replace backend permission checks.
- Use accessible dialog title/description, keyboard operation, safe cancel focus for deletion, labeled confirmation input, `aria-invalid`/`aria-describedby` for field errors, `role="alert"` for failures, and announced success/pending state. Clear stale errors on field correction or target change and return focus to the initiating control on close.
- Render resource names, YAML, and errors as escaped text; never use raw HTML. Reuse the current light/dark theme tokens and responsive table/dialog patterns.

## Testing

Baseline observed during this feature-planning pass: **254 backend tests passed** (two dependency deprecation warnings), and frontend **`yarn verify` passed**, including compilation, TypeScript, and route generation. No application source changed between that run and this resumed spec; reuse the observed baseline. No live cluster write or browser verification was performed.

The root `AGENTS.md` Verify line has a sibling-directory shorthand that does not work literally after entering `backend`. Run the same two declared gates with the correct sibling path, from the repository root:

```sh
cd backend && .venv/bin/python3 -m pytest && cd ../k8s-ui && yarn verify
```

Focused coverage must exercise observable outcomes, not mirror helper implementation:

- All supported kinds and correct Kubernetes method/scope; Namespace handling and UID/timestamp serialization.
- Real session/role tests for admin/operator/viewer, restricted/deactivated users, plus protection checks that cannot be bypassed with direct API calls or mismatched YAML/query identity.
- Explicit cluster requirement, unknown/inactive clusters, per-record credentials, and interleaved requests proving no cross-cluster configuration leakage.
- Malformed/duplicate/multi-document/unsafe YAML, unsupported type/version, missing name, cross-namespace requests, read-only metadata, Kubernetes validation failure, and duplicate-name conflict.
- Exact confirmation, UID replacement races, missing and terminating targets, namespace deletion intent, native deletion options, and refresh-oriented feedback for uncertain outcomes.
- Audit intent failure before a call, accepted mutation with result-audit failure, success/failure correlation, and absence of manifest/credential content in errors/audits/logs.
- Existing discovery/metrics, authentication, cluster management, and Marketplace regression suite.

The frontend has no unit/browser test runner. Do not install one for this item. Run the frontend build and inspect the UI in an available running environment; identify any manual/live evidence still needed. A manual create/delete trial must use an explicitly selected disposable test namespace/cluster; do not mutate an unrelated live cluster just to obtain evidence.

## Notes for the AI

- The selected feature is 19a, not the first unchecked roadmap item 14. Do not expand into Helm or scale/restart.
- The user explicitly confirmed namespace protections for both roles. Do not ask for that permission policy again or add an admin bypass.
- The eight-type scope is the narrower option communicated during planning; do not silently add Secret/Ingress/PVC/ConfigMap management.
- Keep exact new API/schema choices in this spec distinguishable from existing discovery routes. Existing namespace tuples and resource summaries do not currently provide deletion UIDs; do not assume they do.
- Read the relevant installed Next.js guides and shadcn skill before writing frontend code. Existing dialogs are backed by Base UI; follow local component APIs rather than assuming Radix conventions.
- No `prototypes/` directory was found. This is an extension of the existing application design, not screenshot replication.
- No material product question remains for starting this item. The critique tightened explicit cluster targeting, request-local credentials, UID preconditions, namespace protection, async deletion feedback, redaction, and audit failure behavior.

## Implementation review — 2026-09-11

- Backend: implemented the eight-type live inventory, strict single-object YAML creation, UID-constrained deletion, isolated selected-cluster clients, namespace protections, and durable audit intent/result events. Hosting namespace uses the deployment downward API with the documented development fallback.
- UI: added the Manage resources sidebar entry and protected `/manage-resources` page, Kubernetes resources tab, type/namespace filters, searchable/paginated inventory, create dialog, and typed-confirmation delete dialog. Viewers have no mutation controls. Scope-keyed state, canceled/ignored reads, captured write targets, refresh-required conflict/unknown outcomes, and duplicate-submit guards were inspected in code. These UI interactions have not been observed in a browser.
- Reused installed shadcn components and Base UI primitives, following their composition, field, focus, and theme conventions. No runtime dependency or test runner was installed.

Verification evidence:

- `cd backend && .venv/bin/python3 -m pytest tests/test_resource_management.py -q`: **199 passed**, including real signed-cookie roles and deactivation, restricted sessions, all eight dispatches, malformed requests/YAML, protected targets, interleaved credentials, continuation tokens, duplicate creation, replacement races, terminating inventory, and audit/unknown-outcome cases. Kubernetes operations are mocked; this is not live-cluster evidence.
- `cd backend && .venv/bin/python3 -m pytest && cd ../k8s-ui && yarn verify`: **453 backend tests passed** with two existing dependency deprecation warnings; frontend production compilation, TypeScript, and route generation passed. The generated routes include `/manage-resources` and both management proxy routes.
- `cd k8s-ui && yarn tsc --noEmit`: passed. Targeted ESLint passed for the three management components, management page/proxies/helpers, DashboardShell, and cluster-selection hook. `git diff --check`: clean.
- In-memory Node assertions using the installed TypeScript compiler passed for management URL construction, explicit scope rejection, network/internal-error unknown-outcome handling, conflict/audit classification, fixed backend destinations, cookie forwarding, and stripping untrusted query/header fields. No network or installed frontend test harness was used.
- No browser tool was available, and the local UI URL was not reachable. No dev server was started and no live cluster mutation was performed. Visual appearance, keyboard/focus behavior, and a real authenticated create/delete round trip remain manual evidence to collect in an explicitly selected disposable cluster/namespace.

Review boundary:

- No findings are recorded; no independent review was requested. Configured audit, independent-review, check, and try-guide gates remain manual and were not invoked.
- To review manually, sign in as an admin/operator, open **Manage resources**, select an explicit disposable test cluster and namespace, choose a type, and use **Create resource** or a row's **Delete** action. Confirm a viewer remains read-only and protected/terminating rows show their reasons. Namespace creation uses cluster scope; Namespace deletion removes its contents.
- Kubernetes RBAC/admission and asynchronous deletion still govern real outcomes. Helm releases and repositories remain 19b/19c; no placeholder Helm actions were added.
- Branch: `feature/kubernetes-resource-management`. The completion commit is on this feature branch. The 19a build-plan checkbox is complete; parent 19 remains pending 19b/19c. Existing approved planning edits are preserved. No merge, push, or deployment was performed.
