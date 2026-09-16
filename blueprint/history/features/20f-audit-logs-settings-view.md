# Feature 20f - Audit Logs settings view

**Type:** Feature  
**Status:** verified  
**Branch:** `feature/audit-logs-settings-view`  
**Build-plan item:** `20f. Audit Logs settings view`

## Goal

Add an admin-only Settings audit log view that exposes existing non-sensitive audit records for administrative, resource, Helm, provider/model, and AI activity. The view must make operational history searchable and filterable without exposing raw prompts, credentials, kubeconfig data, provider keys, secret payloads, or other sensitive context.

## In scope

- Backend read API for `AuditAction` rows with stable response schemas.
- Admin-only access through existing `settings:read` permission.
- Server-side filters for action category, result, actor, resource type, and date range.
- Server pagination ordered by newest records first.
- Safe context rendering with recursive redaction of sensitive keys and defensive handling for legacy malformed JSON context.
- Same-origin Next.js bridge under `/api/settings/audit-logs`.
- `/settings/audit-logs` page and Settings shell navigation replacing the planned Audit Logs placeholder.
- shadcn/ui-styled table/cards with loading, empty, denied, invalid-filter, and unexpected-error states.
- Focused backend tests for authorization, filtering, pagination, ordering, and redaction.

## Out of scope

- Slack, Gmail, Microsoft Outlook, or other integration registry work.
- Kubernetes AI agents builder or agent policy authoring.
- Changing the audit writer behavior for unrelated features except where a display contract needs a helper.
- Export/download, retention policy, deletion, or tamper-evident audit storage.
- Viewer/operator access to Settings audit logs.
- Displaying raw prompts, raw tool payloads, credentials, kubeconfig content, Secret data, or ConfigMap values.

## Build loop

- `workflow.stepReview` is `feature`, so implement the small steps below and present one feature-level review packet.
- `workflow.checkpointCommits` is disabled.
- Work on `feature/audit-logs-settings-view`.
- `/complete` creates the final feature commit after required verification passes.

## Build steps

- [x] **Step 1 - Backend audit log listing contract**

  Add backend schemas and a `GET /api/v1/settings/audit-logs` route in the existing Settings API. Reuse `AuditAction`, `AuthenticatedActor`, and `require_permission(Permission.SETTINGS_READ)`. Return newest-first rows with pagination metadata and stable fields: `id`, `created_at`, `actor`, `action`, `category`, `resource_type`, `resource_id`, `target_user`, `result`, and redacted `context`.

  Done when backend tests prove admin access works, viewer/operator access is denied, rows are newest-first, pagination is bounded, filters apply server-side, and sensitive context keys/values are redacted.

- [x] **Step 2 - Frontend bridge and typed client**

  Add a same-origin Next route under `k8s-ui/app/api/settings/audit-logs/route.ts` that forwards only the signed session cookie to FastAPI. Add a typed client helper in `k8s-ui/lib/` for audit-log list requests and normalized error messages.

  Done when the route uses `cache: "no-store"`, does not forward unrelated cookies or client identity claims, encodes filters safely, and the helper models the backend response without `any`-shaped audit records.

- [x] **Step 3 - Settings Audit Logs UI**

  Add `/settings/audit-logs` and a client component that uses the existing Settings shell, shadcn/ui primitives, badges, and table patterns. Include controls for category/result/resource type/date filters, a text filter for actor/resource/action, server pagination, refresh, and safe expandable context details.

  Done when the page shows loading, empty, denied, invalid-filter, backend-unavailable, and unexpected-error states; active filters are clearable; long values wrap without layout overlap; and no sensitive values are displayed in the UI.

- [x] **Step 4 - Verification and documentation touch-ups**

  Update nearby overview copy in the Settings landing page or shell only where it still says audit logs are merely planned. Run focused backend tests for the new route and the project Verify command.

  Done when the focused backend tests pass and `./scripts/verify-feature.sh` passes, or any remaining environment-only verification blocker is documented with the exact observed error and recovery path.

## Files / areas

- `backend/app/models/entities.py` - existing `AuditAction` source model.
- `backend/app/core/audit.py` - existing event names and audit writer.
- `backend/app/api/v1/settings.py` - add the audit log route beside existing Settings routes.
- `backend/app/api/v1/settings_schemas.py` - add response and filter schemas.
- `backend/tests/` - add focused Settings audit-log tests.
- `k8s-ui/app/api/settings/audit-logs/route.ts` - same-origin bridge.
- `k8s-ui/app/settings/(admin)/audit-logs/page.tsx` - Settings page entry.
- `k8s-ui/components/settings-shell.tsx` - make Audit Logs a real section.
- `k8s-ui/components/` - audit log view component, reusing existing UI primitives.
- `k8s-ui/lib/` - typed audit-log client helper.

## Data / contracts

- The API reads from existing `audit_actions`; no migration is expected unless implementation evidence shows an index is required for the chosen filters.
- `category` is derived from action prefixes and known event families:
  - `admin` for user, cluster, setting, credential, and provider configuration activity.
  - `resource` for Kubernetes resource create/delete events.
  - `helm` for marketplace, Helm release, and repository events.
  - `ai` for assistant, tool, proposal, and AI model activity.
  - `other` for records that do not match known families.
- Pagination must be stable and bounded. Use page/limit or cursor semantics consistently across backend, bridge, and UI; document the chosen shape in schemas and tests.
- Context is display metadata only. Parse JSON context when valid, treat malformed context as an opaque redacted string, and recursively redact keys containing sensitive terms such as `secret`, `token`, `password`, `credential`, `api_key`, `authorization`, `cookie`, `kubeconfig`, `prompt`, `messages`, and `raw`.
- The backend response must not expose full user records. Actor and target user summaries should be nullable and limited to stable display identity, such as id/email when available.
- Denied access returns the existing permission error shape from `require_permission`; the frontend should present it as a denied Settings state.

## Testing

- Add backend tests for:
  - admin can list audit logs;
  - operator/viewer are denied by `settings:read`;
  - filters by category/result/resource type/action/date work;
  - pagination is bounded and newest-first;
  - context redaction removes sensitive nested values and handles malformed JSON safely.
- Frontend verification should cover the real page states through build and, if a dev server is available during implementation, a browser/manual pass.
- Verification note: `backend/.venv/bin/python -m pytest tests/test_settings_audit_logs.py` and `cd k8s-ui && ./node_modules/.bin/tsc --noEmit` passed in the builder session. `cd k8s-ui && yarn next build --webpack` also passed and included `/api/settings/audit-logs` plus `/settings/audit-logs`. The user then ran the project build gate manually with `cd k8s-ui && yarn verify`; default Turbopack `next build` passed, including TypeScript, page data, static generation for 42 routes, and the new audit-log API/page routes.

## Notes for the AI

- Keep this slice boring and valuable: audit visibility, not automation.
- Do not build integrations or an AI agents builder in this feature.
- Do not broaden Settings access; this page is admin-only.
- Prefer the existing Settings route and shell patterns over introducing a separate admin surface.
- Keep audit context rendering defensive. Audit rows are internal operational data, but context can contain historical strings from many writers and should still be treated as untrusted display input.
- Use accessible labels for filters, announce loading/error states, and avoid layout shifts from long resource IDs or JSON fragments.
