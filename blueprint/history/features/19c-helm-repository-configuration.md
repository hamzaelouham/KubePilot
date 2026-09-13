# Feature 19c: Helm repository configuration

Status: verified

## Goal

Add a professional repository-configuration surface under Manage resources for
KubePilot-managed Helm chart repositories. Repository connections are global
KubePilot application configuration, not Kubernetes resources and not scoped by
the selected cluster or namespace.

The feature supports authenticated users viewing configured repositories and
admins/operators adding, editing, and removing public HTTP(S) repository URLs.
It establishes the persisted chart-source records that Feature 19d will use
when an operator explicitly selects a repository, chart, and version for an
upgrade.

## Design reference only visual

Reuse the existing Manage resources page shell and visual language: its tabs,
DataTable, empty/loading/error/denied states, shadcn/ui dialogs and form
controls, confirmation patterns, spacing, typography, borders, status colors,
and toast behavior. The repository UI should feel like the existing Create
resource dialog and Helm release management surfaces without changing the
overall page layout.

## In scope

- Add a global, database-backed KubePilot Helm repository connection model.
- Store a repository name and public HTTP(S) URL, with created/updated metadata.
- Provide authenticated list access for configured repositories.
- Provide admin/operator create, update, and remove operations.
- Keep viewers read-only: they may see the repository list but receive no
  mutation controls and cannot mutate through the API.
- Validate repository names and URLs server-side, including safe name
  characters, required values, HTTP(S) scheme, and duplicate repository
  conflicts.
- Add backend permission checks for every mutation and audit records for
  successful create, update, and remove operations, including the repository
  identity and changed action metadata without storing secrets.
- Add the repository configuration section to Manage resources using the
  existing shadcn/ui and Tailwind patterns.
- Add add/edit dialogs, a destructive-action confirmation, disabled/pending
  states, refresh after successful mutations, and an operation toast for each
  outcome.
- Cover loading, empty, unauthorized/forbidden, validation, conflict, backend
  failure, and unexpected response states with the app's established patterns.
- Keep repository records available independently of the selected cluster and
  namespace so changing cluster selection cannot show stale or incorrectly
  scoped repository data.

## Out of scope

- Helm release upgrades, chart/version selection, chart-source resolution, or
  background upgrade jobs; those belong to Feature 19d.
- Repository credentials, private/authenticated repositories, secret storage,
  credential rotation, or exposing credentials to the browser.
- Discovering repositories from Kubernetes or treating repositories as
  cluster resources.
- Installing, rolling back, uninstalling, or otherwise changing releases.
- Remote repository connectivity checks or chart-index browsing during CRUD;
  source resolution is deferred to Feature 19d.
- Changes to the existing Manage resources layout or unrelated visual redesign.

## Build loop

Work on branch `feature/helm-repositories-and-upgrades`, implementing one
small step at a time. After each step, run the narrowest relevant checks and
review the diff. Before handoff, run the configured Verify command and present
the result for review. Do not merge, push, or deploy as part of this feature.

## Build steps

- [x] 1. Add the repository persistence model and migration, with global uniqueness
   and the public URL-only contract. Add authenticated repository CRUD APIs,
   centralized permission enforcement, validation/conflict responses, and
   audit events for successful mutations.
- [x] 2. Add the Manage resources repository configuration UI using the established
   table/dialog/confirmation/toast components. Connect it to the backend,
   preserve viewer read-only behavior, and handle all established request
   states without coupling the list to cluster or namespace selection.
- [x] 3. Add focused backend and frontend checks for validation, permissions,
   persistence, audit payloads, mutation refresh/toasts, and read-only viewer
   behavior. Run the repository's configured verification command.

## Files/areas

- `backend/app/models/entities.py` and a new Alembic migration for the global
  Helm repository entity.
- Backend API/router and permission/audit integration for repository CRUD,
  following the existing authenticated v1 route conventions.
- Backend repository tests alongside the existing resource, RBAC, and audit
  coverage.
- `k8s-ui/components/manage-resources-view.tsx` and a focused repository
  configuration component as needed.
- Frontend API/types module for repository list and mutation requests.
- Existing shadcn/ui/Base UI table, dialog, alert-dialog, input, button,
  badge, and toast components; do not add a parallel styling system.

## Data/contracts

- Repository record: stable identifier, unique display/name key, normalized
  public HTTP(S) URL, created-by/updated-by identity, and created/updated
  timestamps. No credential, token, password, or secret fields.
- List response returns all configured global repositories with the safe record
  fields above; it is not filtered by `cluster` or `namespace`.
- Create accepts `name` and `url`; update accepts the editable name and URL;
  remove accepts the repository identifier. The backend remains authoritative
  for normalization and validation.
- Invalid names/URLs return the existing validation error shape. Duplicate
  names or normalized URLs return the existing conflict/error shape. Missing
  records return the established not-found response.
- Successful mutations create audit entries identifying the repository and
  operation. Audit data contains no credentials because credentials are not
  supported by this feature.
- Feature 19d must consume these records and require an explicit repository,
  chart, and version selection for every upgrade; it must not infer a source
  from the selected cluster or persist a release association in 19c.

## Testing

- Backend unit/API tests for CRUD, global scope, validation, duplicate and
  missing-record handling, admin/operator permissions, viewer read-only access,
  and audit records.
- Frontend checks for list/create/edit/remove flows, pending states, toasts,
  confirmation, forbidden/empty/error states, and cluster-selection changes.
- Run the configured project Verify command before review; no browser test
  harness is currently configured.

## Notes for AI

- Follow `blueprint/context/coding-standards.md` and the existing repository,
  permission, audit, and Manage resources conventions.
- Keep global repository configuration separate from Kubernetes resource and
  Helm release discovery. Do not add cluster or namespace query parameters to
  repository CRUD merely because the page has those controls.
- Keep all mutations server-authorized and use safe typed API responses. Never
  execute a Helm command from the frontend and never place credentials in
  client state, logs, audit records, or API responses.
- Prefer existing shadcn/ui/Base UI primitives and Tailwind tokens; preserve
  the current Manage resources layout and operational visual hierarchy.
- Do not implement Feature 19d upgrade behavior in this feature.
