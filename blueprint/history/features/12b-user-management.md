# Current Feature

> **Generated file.** Holds the one feature, fix, or rollback being built right now.

**Feature 12b: User management.**

**Type:** Feature

**Status:** verified

**Branch:** feature/user-management

## Goal

Add admin-only user provisioning to KubePilot. Admins can list users, create
new accounts with admin/operator/viewer roles and an initial password, change a
user's role, and deactivate accounts through backend API endpoints and a new
admin UI surface. Deactivating a user blocks their login and immediately
invalidates their existing sessions. Role enforcement on cluster operations
itself stays in 12c.

## In scope

- `UserAccount.is_active` persisted flag (new DB column) with deactivation
  semantics: login rejects inactive users with a generic 401 (no account
  enumeration), and the shared session resolver refuses any session for an
  inactive user (existing cookies stop working immediately).
- Backend admin-only API under `/api/v1/users`: list, create, change role,
  deactivate. All endpoints require an authenticated `admin` actor.
- Admin UI at `/dashboard/admin`: role-aware sidebar entry, users table, create
  user dialog, role change select, deactivate with confirmation.
- Migration for the new column; focused backend tests; UI build + lint clean.

## Out of scope

- Enforcement of admin/operator/viewer permissions on cluster operations —
  12c.
- User deletion, password reset flows, invitation/activation emails, user
  preferences, audit-action recording of user-management events — later.
- Password policy (minimum length/composition) beyond "non-empty"; no product
  decision exists in the plans (see Open questions).
- Changes to the shared cookie contract, PBKDF2 scheme, or `get_current_actor`
  identifier/role shape.

## Build loop

Plan steps on branch `feature/user-management` (prefix from config: `feature/`).
`workflow.stepReview` is `feature` (one review after all steps) and
`workflow.checkpointCommits` are `disabled` — no per-step commits or approval
pauses; `/complete` makes the single work commit. No step touches prod data;
the SQL-heavy migration check and the pytest suite are run at each step.

## Build steps

- [x] 1. **Persist active state and enforce it at the auth boundary** - add
  `is_active: bool` to `UserAccount` (not null, default `True`,
  `server_default="true"`), add an alembic migration (single additive `ALTER
  TABLE user_accounts ADD COLUMN`), and make login and the session resolver
  honor it: `login` returns the generic 401 body for an inactive account, and
  `_resolve_cookie_actor` returns `None` when the looked-up user is inactive
  (existing sessions die immediately; no session-row deletion).
  `Done when`: `cd backend && PYTHONPATH=. alembic upgrade head --sql` runs
  clean and shows the new column; `cd backend && .venv/bin/python3 -m pytest`
  passes (existing 79 plus new cases: inactive user's login → 401 with the
  generic body; a previously valid cookie for a deactivated user no longer
  authenticates `/api/v1/auth/context` → 401).
- [x] 2. **Admin-only user management API** - add a `require_admin` dependency
  (identical 401 as today when unauthenticated; 403
  `{"code":"insufficient_permissions","message":"Admin access is required"}`
  when the actor's role is not `admin`) and the endpoints with admin-only
  guard:
  - `GET /api/v1/users` → `{"items":[{"id","email","role","isActive","createdAt"}]}`, newest first; never returns `password_hash`.
  - `POST /api/v1/users` with `{email, password, role}` → `201` + user item;
    email is lowercased/stripped; role must be `admin`, `operator`, or
    `viewer`; password must be non-empty; duplicate email → `409`
    `{"code":"email_in_use",...}`; invalid role / empty password → `422`.
  - `PATCH /api/v1/users/{id}/role` with `{role}` → updated user item; unknown
    id → `404`; the env-configured admin account
    (`email == settings.admin_email`) is never demoted (`422
    {"code":"protected_admin_account",...}`).
  - `POST /api/v1/users/{id}/deactivate` → `200` `{"id", "isActive": false}`;
    idempotent (already-inactive returns the same body); unknown id → `404`;
    the env-configured admin account cannot be deactivated → same `422`
    protected body (lockout prevention; that account is the recovery path from
    12a).
  `Done when`: `.venv/bin/python3 -m pytest` passes with a new
  `test_user_management.py` covering list (admin ok, non-admin 403,
  unauthenticated 401), create happy path + duplicate 409 + bad role 422 +
  empty password 422, role change happy path + env-admin protection, deactivate
  happy path + idempotency + env-admin protection, and deactivated-user login
  → 401; `PYTHONPATH=. alembic upgrade head --sql` still clean.
- [x] 3. **Frontend proxy routes** - mirror the existing
  `app/api/cluster/namespaces/route.ts` pattern (forward the request `cookie`
  header verbatim to `KUBEPILOT_BACKEND_URL/...`, pass through status and body,
  single generic `503 {"code":"backend_unavailable",...}` on fetch failure):
  - `app/api/auth/context/route.ts` → `GET` `/api/v1/auth/context`.
  - `app/api/users/route.ts` → `GET` list and `POST` create (forward method,
    headers, and JSON body).
  - `app/api/users/[id]/route.ts` → `PATCH` role and `POST` deactivate.
  `Done when`: `yarn build` compiles and `yarn lint` reports 0 errors; each
  handler forwards cookies and returns the backend status/body unchanged
  (route exists for all four verbs); no handler sets cookies.
- [x] 4. **Admin UI with role-aware navigation** - add shadcn `select`,
  `dialog`, and `alert-dialog` primitives (`npx shadcn@latest add select
  dialog alert-dialog` in `k8s-ui/`, committing the generated files). New
  `/dashboard/admin` page (protected by the existing `/dashboard` middleware):
  the server page calls `/api/auth/context` and redirects non-`admin` actors to
  `/dashboard`, then renders the shell. `DashboardShell` fetches `/api/auth/context`
  once and shows an "Admin → Users" sidebar entry only for admins. A client
  `UsersManagement` component (mirroring existing view/table/badge/empty
  components) renders the users table with Active/Deactivated badges, in-place
  role select, create-user dialog (email / role / password with validation
  feedback), and deactivate-with-confirmation; list/actions flow through the
  step-3 proxy routes with loading, empty, and inline error states.
  `Done when`: `yarn build` and `yarn lint` pass; against a running backend an
  admin sees "Admin → Users" and can list, create, re-role, and deactivate a
  user; a non-admin has no Admin entry and `/dashboard/admin` redirects to
  `/dashboard`; the deactivated user's next login fails.

## Files / areas

- `backend/app/models/entities.py` — `UserAccount.is_active` column.
- `backend/alembic/versions/<new>_add_user_account_is_active.py` — additive
  migration (auto-increment order after `dd752e8644a9`).
- `backend/app/api/v1/routes.py` (or a sibling `users` router included in the
  existing `v1_router`) — the four endpoints; `backend/app/api/v1/users_schemas.py`;
  role constant set `{"admin","operator","viewer"}` (single source, reused by
  login/seed logic).
- `backend/app/core/dependencies.py` — `require_admin` guard.
- `backend/tests/test_user_management.py` — new focused tests; no changes to
  `test_auth_login.py` beyond any needed case reuse.
- `k8s-ui/app/api/auth/context/route.ts`,
  `k8s-ui/app/api/users/route.ts`,
  `k8s-ui/app/api/users/[id]/route.ts` — proxy handlers.
- `k8s-ui/app/dashboard/admin/page.tsx`, `k8s-ui/components/admin-users-view.tsx`
  — admin surface; `k8s-ui/components/dashboard-shell.tsx` — role-aware Admin
  nav entry.
- `k8s-ui/components/ui/{select,dialog,alert-dialog}.tsx` — shadcn additions.

## Data / contracts

- `UserAccount.is_active`: `boolean`, not null, default `true`; deactivation is
  a soft state change, never a row delete.
- Roles: fixed lowercase set `admin | operator | viewer` (matches 12a/overview);
  `UserAccount.role` default stays `operator`.
- `GET /api/v1/users` → `200` `{"items":[{"id","email","role","isActive","createdAt"}]}`;
  ordered newest `created_at` first; `password_hash` never serialized.
- `POST /api/v1/users` body `{"email","password","role"}` → `201` user item;
  errors `409` `{"code":"email_in_use","message":...}` and `422` (pydantic,
  field-level).
- `PATCH /api/v1/users/{id}/role` body `{"role"}` → `200` user item;
  `404` unknown id; `422` protected env-admin account (never demoted).
- `POST /api/v1/users/{id}/deactivate` → `200` `{"id","isActive":false}`,
  idempotent; `404` unknown id; `422` protected env-admin account.
- Authorization: all `/api/v1/users*` require the signed, session-validated
  cookie resolving to `role == "admin"`; `403`
  `{"code":"insufficient_permissions","message":"Admin access is required"}`
  for a non-admin actor, `401` `{"code":"authentication_required",...}`
  (existing) when unauthenticated/stale.
- Login/context for an inactive user: generic `401` "Authentication is
  required" — never distinguishes "bad password" from "deactivated".
- No cookie format, session row model, or `auth/context` shape changes.

## Testing

- Backend logic gate (`verification.logicTests: when-configured`, runner
  exists): extend `tests/` with `test_user_management.py`; run
  `cd backend && .venv/bin/python3 -m pytest` (baseline **79 passed** this
  session; must stay green with new cases).
- Migration SQL check per step:
  `cd backend && PYTHONPATH=. alembic upgrade head --sql`.
- UI: `yarn build` and `yarn lint` (0 errors; one pre-existing
  `dashboard-shell.tsx:10` warning stays).
- `verification.uiEvidence: when-available` — the interactive admin surface
  needs a live backend (minikube/cloud); capture in-browser behavior during
  the next minikube deploy rather than asserting it in this spec's checks.
- Declared Verify command is not configured in `AGENTS.md`; the fallback gate
  above (pytest + build + lint) is the evidence.

## Notes for the AI

- Read `k8s-ui/AGENTS.md` nextjs-agent-rules and the Next.js docs in
  `node_modules/next/dist/docs/` (where present) before editing frontend code,
  and confirm any referenced shadcn item via the repository `components.json`.
- Backend is the source of truth for roles; frontend gating is UX only.
- Route handlers must forward the request's `cookie` header (they are
  same-origin proxies); never set or read cookie values in handlers.
- Preserve the fixed-salt PBKDF2 scheme and the `KUBEPILOT_ADMIN_EMAIL` env
  seed/refresh semantics from 12a exactly.
- The env admin (`settings.admin_email`) can sign in and be listed/read, but
  is never deactivated or demoted by this API; its role stays `admin`.
- Keep `/api/v1/users` responses free of `password_hash`; do not log passwords
  or cookie payloads.
- shadcn additions land as committed source under `components/ui/` (base-nova
  style, `@/` aliases) — no runtime dependency changes beyond the generated
  files.

## Open questions

- Password policy at account creation (e.g., minimum length) is not defined in
  the plans. Non-blocking: 12b validates non-empty and notes that a policy can
  be added later (12c or a `/fix`).
- Reactivation of a deactivated account is not in the 12b scope line; if an
  operator needs it before 12c, it is a small follow-up (`/fix` or 12c).