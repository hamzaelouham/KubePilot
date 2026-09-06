# Feature 12: Users, Authentication & RBAC

**Type:** Feature
**Status:** verified
**Branch:** `feature/users-authentication-rbac`

## Goal

A complete multi-user authentication and authorization system built on the
current architecture — database-backed logins for any provisioned user, a
central permission model with exactly three roles (admin/operator/viewer),
admin-only user management, 15-day password expiration, forced password change,
self-service password change, audit logging, and full backend enforcement —
without breaking the existing authentication, sessions, Kubernetes
connectivity, or frontend behavior.

## Design decisions (resolved)

- **Identifier stays email.** Login is by `email` today and is the only existing
  identity. It is reused as the "username"; no second identifier or parallel
  auth model is introduced (`display_name` is out of scope). The Users table
  shows the email as the user name.
- **One authoritative RBAC module.** `backend/app/core/rbac.py` owns the `Role`
  enum, permission strings, the role→permission map (§12.2 matrix), and the
  `require_permission` dependency. No inline role checks anywhere else.
- **Restricted sessions.** A session rows gains `restricted`. When a login
  succeeds but the password is expired or `must_change_password` is set, the
  user gets a restricted session: `GET /api/v1/auth/me` and
  `POST /api/v1/auth/change-password` work; every other protected endpoint
  returns `403 {"code":"password_change_required",...}`. Changing the password
  clears the flag.
- **Auth endpoints stay dual-purpose yet compatible.** `login` keeps its
  `LoginResponse{cookie, expires_at}` contract and adds
  `change_required: bool`. `GET /auth/context` (identifier + role) is preserved;
  the frontend role-aware layer uses the richer `GET /auth/me`.
- **Config:** `KUBEPILOT_PASSWORD_TTL_DAYS` (default `15`),
  `KUBEPILOT_PASSWORD_MIN_LENGTH` (default `10`).
- **Two admin password operations** per §12.7 (reset w/ temporary password +
  force change) and self-service change per §12.7.
- **Delete vs deactivate:** deactivation is the primary action (soft, never
  breaks audit/history). `DELETE` performs a controlled physical deletion that
  surfaces `409 {"code":"user_has_history"}` when audit (or other FK) rows
  reference the user; otherwise it deletes after invalidating sessions.

## Permission matrix (authoritative, backend)

Permissions: `clusters:read|create|update|delete`, `resources:read|create|update|delete`,
`users:read|create|update|delete|reset_password|force_password_change`.

| Permission | Admin | Operator | Viewer |
| ---------- | :---: | :------: | :----: |
| clusters:read / resources:read | ✅ | ✅ | ✅ |
| clusters:create / clusters:update | ✅ | ✅ | ❌ |
| resources:create / resources:update / resources:delete | ✅ | ✅ | ❌ |
| clusters:delete | ✅ | ❌ | ❌ |
| users:* (read, create, update, delete, reset_password, force_password_change) | ✅ | ❌ | ❌ |

Every current cluster/resource/read endpoint requires a `resources:read`
permission (viewer minimum). User-management endpoints require the matching
`users:*` permission. No current MVP mutation endpoints exist for resources or
clusters; the map is the single source future mutations must use, and the
matrix is unit-tested exactly per §12.2.

## In scope

- DB: extend `user_accounts` (`is_active`, `updated_at`, `last_login_at`,
  `password_changed_at`, `password_expires_at`, `must_change_password`), add
  `restricted` to `sessions`, extend `audit_actions` (`target_user_id`, `result`,
  `context`); `Role` enum typed via SQLAlchemy `Enum` (native_enum off, portable
  to SQLite + Postgres). One additive alembic migration.
- Backend login rules per §12.9 (validate → status → expiry → session), role
  always resolved from the DB.
- Backend RBAC per §12.11, protecting all existing endpoints.
- User management API per §12.15 with admin safety rules per §12.16.
- Password lifecycle per §12.7/§12.8 (expiry, forced change, self-service).
- Audit logging per §12.17 (`AuditAction` rows, never secrets).
- Frontend per §12.3/§12.5/§12.12/§12.13/§12.15: `/settings/users`,
  `/settings/password`, login flow rework, admin-only nav, role-aware shell,
  backend-backed session (no client-generated cookies).
- Automated tests per §12.18 (backend pytest; no frontend test runner exists).

## Out of scope

- Username/display-name editing (§12.5 defers), user self-registration,
  invitations/emails, MFA, password history/reuse rules, K8s-write RBAC
  (app-internal gating only), resource/cluster mutation endpoints (future work
  will use the permission map).
- Changing the cookie format, PBKDF2 scheme, or `get_current_actor` name/shape
  (fields added, contract preserved).

## Build steps (phases, gated)

- [x] **Phase 1 — Database.** Inspect current models (done). Add the
  `user_accounts`, `sessions`, `audit_actions` fields above; the `Role` enum
  is enforced at the application boundary by `backend/app/core/rbac.py` (the
  existing `role` VARCHAR column is unchanged, so the migration stays purely
  additive and SQLite-safe); create and run the additive migration.
  - Done when: `PYTHONPATH=. alembic upgrade head --sql` adds exactly the new
    columns via plain `ADD COLUMN` (one batch rebuild, only for the
    `audit_actions` nullability change) and `.venv/bin/python3 -m pytest`
    passes (73 baseline) with no auth behavior changes. ✅ Verified.
- [x] **Phase 2 — Backend RBAC.** Add `backend/app/core/rbac.py` (`Role`,
  permissions, `ROLE_PERMISSIONS`, `require_permission`); protect every existing
  `/cluster/*` endpoint read path; extend `AuthenticatedActor` with `user_id`,
  `session_id`, `restricted` (see login rules in Phase 4 for restricted).
  - Done when: new `test_rbac_permissions.py` asserts the exact matrix and API
    tests show all three roles can read `/cluster/*`; Verify passes. ✅ 82 passed
    (73 baseline + 9 matrix/path tests).
- [x] **Phase 3 — User-management API.** `users.py` router in `main.py`:
  list/get/create/patch/delete + reset-password + force-password-change, all
  `users:*`-gated, audit-logged, with §12.16 safety rules.
  - Done when: `test_user_management.py` covers admin create/list/get/update/
    deactivate/reactivate/role/reset/force, operator+viewer 403 on every
    `/api/v1/users*` method, non-admin 401, no password fields in any response,
    last-active-admin protections, self-operation blocks; Verify passes.
    ✅ 20 API tests; 102 total. Deletion uses an explicit audit-history check
    (SQLite does not enforce FKs by default).
- [x] **Phase 4 — Password lifecycle.** Login-status/expiry flow, restricted
  sessions, `/api/v1/auth/me`, `/api/v1/auth/change-password`, session
  invalidation (deactivate/reset/force/change), TTL config.
  - Done when: `test_password_lifecycle.py` covers valid/invalid/unknown/
    disabled/expired/forced-change logins, restricted access 403, change
    success clearing restrictions and resetting expiry, other-session
    invalidation; migration SQL clean; Verify passes. ✅ 7 tests; 109 total.
    Env-admin is still bootstrapped on first login (kept for backward
    compatibility with existing deployments) and validated like any user.
- [x] **Phase 5 — Frontend.** Proxy routes (`/api/users/*`, `/api/auth/me`,
  `/api/auth/change-password`, `/api/auth/login`), reworked `lib/auth.ts` +
  login action (backend login only, `change_required` → password screen),
  `/settings/users` (shadcn table/badge/select/dialog/alert-dialog;
  create/edit/deactivate/reactivate/reset/force flows, expiry display),
  `/settings/password` (self-service + forced flow), admin-only nav +
  middleware route protection for `/settings/*`.
  - Done when: `yarn build` and `yarn lint` pass; read Next.js docs under
    `node_modules/next/dist/docs/` before editing per `k8s-ui/AGENTS.md`;
    shadcn additions reuse the existing registry (`components.json`). ✅ Build +
    lint pass. Note: `middleware.ts` migrated to `proxy.ts` (Next 16 renamed
    the convention; deprecated) with `/settings/:path*` added to the matcher;
    `lib/auth.ts` is server-only, shared types/constants live in the new
    client-safe `lib/auth-client.ts`.
- [x] **Phase 6 — End-to-end verification.** Real-session matrix via TestClient
  (admin full, operator operational-no-users, viewer read-only-no-mutations,
  403/401 paths, disabled/expiry/reset invalidation), plus the documented
  `Verify` command.
  - Done when: full pytest passes with the complete §12.18 suite, `yarn verify`
    compiles, and the live cluster run is queued as the manual try path. ✅
    `test_end_to_end_rbac.py` (7 tests) → 116 backend tests green; `yarn verify`
    (next build) green; migration SQL clean. Remaining manual path: run the app
    with a live Minikube cluster and exercise the UI (see `try`).

## Files / areas

- `backend/app/models/entities.py` — `UserAccount`, `Session`, `AuditAction` field additions; `Role` enum column.
- `backend/alembic/versions/<new>_add_user_rbac_columns.py` — additive migration (after `dd752e8644a9`).
- `backend/app/core/rbac.py` (new) — `Role`, `Permission`, `ROLE_PERMISSIONS`, `require_permission`.
- `backend/app/core/audit.py` (new) — `record_audit` helper + action constants.
- `backend/app/core/dependencies.py` — `AuthenticatedActor{identifier,role,user_id,session_id,restricted}`; resolve `restricted` + inactivity (Phase 4).
- `backend/app/api/v1/routes.py` — login rules, `/auth/me`, `/auth/change-password`, permission deps on reads.
- `backend/app/api/v1/users.py` (new) + `users_schemas.py` (new) — user CRUD + admin ops.
- `backend/app/core/config.py` — TTL + min-length env settings.
- Backend tests (new): `test_rbac_permissions.py`, `test_user_management.py`, `test_password_lifecycle.py`; inlined harness (cross-test imports fail in this repo).
- Frontend: `k8s-ui/lib/auth.ts`, `app/login/actions.ts`, `app/login/page.tsx`, `middleware.ts`,
  `app/api/users/route.ts`, `app/api/users/[id]/route.ts`, `app/api/users/[id]/reset-password/route.ts`,
  `app/api/users/[id]/force-password-change/route.ts`, `app/api/auth/me/route.ts`,
  `app/api/auth/change-password/route.ts`, `app/api/auth/login/route.ts` (new),
  `app/settings/users/page.tsx`, `app/settings/password/page.tsx`,
  `components/users-management.tsx`, `components/change-password-form.tsx`,
  `components/dashboard-shell.tsx` (admin nav), `components/ui/{select,dialog,alert-dialog}.tsx` (re-add).

## Data / contracts

- Status codes: `401 {"code":"authentication_required","message":"Authentication is required"}` everywhere an identity/session is missing or invalid (no account enumeration); `403 {"code":"insufficient_permissions","message":"Insufficient permissions for the required role"}` for role failures; `403 {"code":"password_change_required","message":"Password change required before accessing this resource"}` for restricted sessions.
- `password_expires_at` stored per user; expired ⇒ `current_time >= password_expires_at`. After any successful change: `password_changed_at=now`, `password_expires_at=now+TTL`, `must_change_password=false`.
- `GET /api/v1/users` → `{"items":[{id,email,role,isActive,passwordExpiresAt,passwordExpired,mustChangePassword,lastLoginAt,createdAt}]}`; never `password_hash`. `POST /api/v1/users` → `201`. `PATCH /api/v1/users/{id}` accepts `role|isActive|passwordExpiresAt|forcePasswordChange`, enforcing §12.16. `POST /reset-password` (temporary password in body), `POST /force-password-change`.
- `GET /api/v1/auth/me` → `{id,email,role,isActive,mustChangePassword,passwordExpiresAt,lastLoginAt}` (allowed for restricted sessions). `POST /api/v1/auth/change-password` body `{currentPassword,newPassword}`.
- Password policy: min length from `KUBEPILOT_PASSWORD_MIN_LENGTH` (default 10). Same `pbkdf2_sha256$120000$<sha256_hex>` fixed-salt scheme (existing) via a `passwords.py` module (No second hashing system).
- Audit: `AuditAction` rows with `action` in the §12.17 set, `actor_id` (null for login failures), `target_user_id`, `result`, optional `context`. Never passwords/hashes.

## Testing

- `cd backend && .venv/bin/python3 -m pytest` — existing 73 baseline must stay green; new suites per §12.18 (auth, admin, operator, viewer, security).
- Migration check per phase: `cd backend && PYTHONPATH=. alembic upgrade head --sql`.
- Frontend: `yarn build`, `yarn lint` (no test runner; `verification.uiEvidence: when-available` — live browser/mocks deferred to the minikube try path).
- Declared Verify: `cd backend && .venv/bin/python3 -m pytest && cd k8s-ui && yarn verify`.

## Notes for the AI

- Follow `k8s-ui/AGENTS.md` nextjs-agent-rules and Next.js docs before frontend edits; confirm shadcn items against `components.json`.
- Backend is the source of truth; frontend hiding is UX only.
- Forward the request `cookie` in proxy handlers; never set/read cookie values there except the login handler proxy.
- Preserve cookie/session format exactly; do not rewrite the session architecture.
- Do not log passwords, hashes, or cookie payloads; keep 401s generic.
- If an architectural conflict emerges, stop and document it (§12.20.16) instead of redesigning silently.