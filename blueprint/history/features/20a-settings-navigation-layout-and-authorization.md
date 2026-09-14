# Feature 20a - Settings navigation, layout, and authorization

**Branch:** `feature/settings-navigation-layout-and-authorization`
**Status:** verified

## Goal

Introduce the centralized administrator Settings entry point and reusable protected layout for KubePilot. An administrator can open `/settings` and see the planned Settings information architecture in the existing application shell; a non-admin cannot access the centralized Settings surface even by entering the URL manually. Existing `/settings/clusters`, `/settings/users`, and `/settings/password` behavior remains intact until their policies are intentionally moved or expanded by later work.

## In scope

- Add an admin-only `Settings` item to the existing Administration navigation using the existing Lucide/shadcn visual language.
- Add the `/settings` root and an admin route-group layout that can host future Settings sections without wrapping the legacy settings routes.
- Render a reusable secondary Settings navigation with these labels: General, Appearance, AI Providers, Models, Integrations, Secrets & Credentials, Audit Logs, and AI Agents.
- Render a useful Settings overview/empty state that clearly distinguishes this shell from the not-yet-implemented configuration modules; do not create editable configuration fields in this feature.
- Reuse `DashboardShell`, current typography/colors/spacing, current light/dark theme provider, and existing responsive layout primitives.
- Enforce the centralized Settings boundary in both layers:
  - Next.js server route guard uses the backend-loaded authenticated user and redirects unauthenticated users to `/login` and non-admin users to `/dashboard`.
  - FastAPI adds an admin-only Settings permission and a minimal protected access endpoint for the new Settings API boundary. The trusted actor comes from the signed HTTP-only session resolved against PostgreSQL; no client role claim is authoritative.
- Preserve accessible loading, unexpected-error, and no-module-yet states. There are no user-controlled form fields or validation errors in this shell-only feature.

## Out of scope

- General or Appearance persistence, theme changes beyond the existing user-menu implementation, application configuration fields, feature toggles, or configuration precedence.
- Credentials, encryption, provider connection tests, AI provider/model registries, integrations, audit-log data/UI, AI Agents behavior, or the Phase 2 AI provider refactor.
- Any Vercel AI Gateway, OpenAI, OpenRouter, Ollama, FastAPI/Kubernetes, Helm, or existing assistant behavior changes beyond the Settings authorization seam.
- Replacing or broadening the existing permissions for `/settings/clusters`, `/settings/users`, or `/settings/password`.
- Database migrations or persistent Settings records.

## Build loop

Configuration uses `workflow.stepReview: "feature"` and `checkpointCommits: "disabled"`. Implement the small steps in order, keep the app buildable after each step, then present one feature-level review packet. Do not commit from this feature spec; `/complete` owns the final feature commit after the required gates pass.

## Build steps

- [x] **Step 1: Add the backend Settings authorization seam.** Add an admin-only `settings:read` permission to the existing RBAC registry, a typed `GET /api/v1/settings/access` response exactly `{ "allowed": true }`, and the matching Next.js same-origin proxy. Reuse `get_current_actor`/`require_permission` and the existing error envelope; do not add a broad settings permission or accept a provider/section identifier from the request.

  **Done when:** an authenticated admin receives `200` with the stable access response; an operator or viewer receives `403` with the existing `insufficient_permissions` error; an unauthenticated request receives the existing `401` error; the proxy forwards only the session cookie and preserves status/body. Add focused backend coverage in the existing pytest style.

- [x] **Step 2: Add the protected centralized Settings route group.** Add a server-side admin Settings helper that validates the backend-loaded user and the protected Settings access seam, then add an `app/settings/(admin)/layout.tsx` route-group layout that checks it before rendering children. Add `/settings` without changing the existing sibling routes. Keep the admin check server-side and route-level so direct navigation cannot bypass it; use the existing login/dashboard redirect conventions.

  **Done when:** `/settings` renders only for an active admin; anonymous users are redirected to `/login`; operator/viewer users are redirected to `/dashboard`; the existing password-forced redirect and legacy cluster/password routes still resolve under their current policies; the route does not trust URL parameters or browser storage for identity.

- [x] **Step 3: Extend the existing shell navigation and create the Settings shell.** Add the Settings item and active title/icon handling to `components/dashboard-shell.tsx`. Create a focused `SettingsShell`/navigation component that composes the existing shell, preserves cluster/theme/user controls, and presents the approved secondary section labels. Keep future section destinations inert or clearly unavailable until their corresponding build-plan item exists; do not create dead links or fake configuration state.

  **Done when:** an admin sees Settings under Administration and the active state is correct on `/settings`; non-admin users do not see the centralized Settings link; the page is usable at narrow and wide widths in both themes; existing dashboard, cluster, user, password, Marketplace, and Manage resources navigation remains unchanged.

- [x] **Step 4: Add the Settings overview states and accessibility behavior.** Add the `/settings` overview content plus route loading and unexpected-error fallbacks using existing shadcn primitives. The overview should explain that configuration modules will be delivered incrementally, show the section hierarchy without implying that unimplemented modules are connected, and provide an accessible recovery/navigation path when the server-side access check fails.

  **Done when:** normal, loading, no-module-yet, denied, and unexpected-error outcomes have visible, concise, accessible treatment; focus/labels are sensible for the navigation; no secrets, environment variables, or editable settings appear in rendered HTML or API responses.

- [x] **Step 5: Run the feature verification gate and review the final diff.** Run the documented Verify command once the implementation is complete, plus the focused Settings authorization tests and frontend verification as applicable. Record actual results and inspect the final changed-file set for scope drift.

  **Done when:** focused authorization tests pass; `cd k8s-ui && yarn verify` passes; the documented combined Verify result is recorded honestly; the final diff contains only the Settings navigation/layout/authorization work and its tests/docs needed to support it.

## Files / areas

- `k8s-ui/components/dashboard-shell.tsx` — Administration navigation, icon, active resource title, and existing shell composition.
- `k8s-ui/components/settings-shell.tsx` (new) — centralized Settings shell and secondary navigation.
- `k8s-ui/app/settings/(admin)/layout.tsx` (new) — server-side protected route-group layout.
- `k8s-ui/app/settings/(admin)/page.tsx` (new) — Settings overview/empty state.
- `k8s-ui/app/settings/(admin)/loading.tsx` and `error.tsx` (new) — loading and unexpected-error states.
- `k8s-ui/lib/auth.ts` — server-side Settings admin/access helper, reusing the existing session/backend user flow.
- `k8s-ui/app/api/settings/access/route.ts` (new) — same-origin access proxy.
- `backend/app/core/rbac.py` — admin-only `settings:read` permission.
- `backend/app/api/v1/settings.py` and typed schema area (new) — protected access endpoint.
- `backend/app/main.py` — register the Settings router using the existing FastAPI router pattern.
- `backend/tests/test_settings_access.py` (new) — admin, non-admin, unauthenticated, and proxy/API contract coverage as appropriate to the repository test seam.

Do not modify existing Settings page implementations except where a shared navigation import or route-group boundary requires a minimal compatibility adjustment.

## Data / contracts

- **Authorization:** `settings:read` is granted to `admin` only. The backend resolves the actor from the signed `kubepilot_session` cookie, validates expiry/activity/session persistence, and applies `require_permission`; the browser cannot elevate by changing a role value.
- **Backend access response:** `GET /api/v1/settings/access` returns `{ "allowed": true }` for an authorized admin and no secret/configuration data. Authentication and permission failures use the existing `ErrorResponse` shape and codes (`authentication_required`, `insufficient_permissions`). Unexpected failures use the existing generic error boundary.
- **Frontend proxy:** `GET /api/settings/access` forwards the request cookie to FastAPI, does not accept a body or arbitrary settings key, and passes through the backend status and JSON response using existing proxy conventions.
- **Route boundary:** new centralized Settings pages live under `app/settings/(admin)` so the admin layout does not accidentally change the existing `/settings/clusters`, `/settings/users`, or `/settings/password` policies. The authenticated `/settings` path itself is handled by the new admin route group.
- **Persistence:** none in 20a. The Settings shell must not read or expose process environment variables, bootstrap secrets, API keys, cookies, or mutable configuration values.
- **Navigation:** section labels are an information-architecture contract only in 20a. Later 20b–20g items own their destinations and data behavior.

## Testing

- Focused backend pytest: `cd backend && .venv/bin/python3 -m pytest tests/test_settings_access.py`.
- Frontend verification: `cd k8s-ui && yarn verify`.
- Final project gate: use the exact `Verify` command in `AGENTS.md`: `cd backend && .venv/bin/python3 -m pytest && cd k8s-ui && yarn verify`.
- No browser test harness is configured, so do not add one in this feature. Manual route/theme/responsive proof can be performed later with `/try` or `/check`.
- Baseline observation before implementation: the declared combined Verify command collected 503 backend tests and stalled at the first `tests/test_assistant.py` case; it was interrupted before the frontend phase. Do not claim a passing baseline, and record the post-implementation result separately.
- Final verification observation: focused Settings pytest passed (`2 passed`), backend syntax compilation passed, and the full backend suite passed (`505 passed in 346.43s`). The documented combined Verify command then failed at its `cd k8s-ui` segment because it runs from `backend` and resolves the path as nonexistent `backend/k8s-ui`. From the project root, `cd k8s-ui && yarn verify` reached the Next.js 16.3.3 Turbopack build but failed in this environment with `creating new process / binding to a port / Operation not permitted`; the documented Next.js fallback `cd k8s-ui && yarn next build --webpack` passed, including TypeScript, static page generation, and the `/settings` and `/api/settings/access` routes. The exact command/path and environment failures remain recorded rather than being reported as a passing combined Verify result.
- Completion repair: `tests/test_assistant.py` now enters `TestClient` through its context manager and sets its temporary SQLite/auth/worker environment before FastAPI lifespan startup. This keeps the assistant HTTP tests isolated from process-level deployment settings; assistant coverage passes outside the restricted sandbox.

## Notes for the AI

- Read the current Next.js 16 route conventions before implementing any route files if the relevant `node_modules/next/dist/docs/` guidance is needed.
- Keep the new Settings shell visually native to `DashboardShell`; reuse `next-themes`, existing `Card`/`Separator`/`Badge`/`Skeleton`/`Alert`/`Button` components, and current CSS tokens.
- Do not put all future configuration options into this page as placeholders that look editable. The overview is a navigational shell, not a mock settings backend.
- Preserve the distinction between the centralized admin Settings area and legacy self-service/password or cluster-management routes.
- The backend endpoint is an authorization seam, not a generic environment-variable API. Never accept arbitrary provider IDs, setting keys, or environment names here.
- Keep errors concise and safe. Never log or serialize cookies, credentials, environment values, or role claims supplied by clients.
