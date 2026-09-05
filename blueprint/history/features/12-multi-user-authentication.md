# Current Feature

> **Generated file.** Holds the one feature, fix, or rollback being built right now.

**Feature 12a: Multi-user authentication.**

**Type:** Feature

**Status:** verified

**Branch:** feature/multi-user-authentication

## Goal

Let any user stored in the application database sign in, instead of only the
single environment-configured admin. The configured admin (`KUBEPILOT_ADMIN_EMAIL`
/ `KUBEPILOT_ADMIN_PASSWORD`) is seeded into PostgreSQL on first login and remains
the master account, while every other login is verified against the user's stored
password hash. Sessions stay per-user and the shared signed cookie contract is
unchanged. Role enforcement and user provisioning belong to 12b/12c.

## In scope

- Backend login verifies credentials against `user_accounts` rows (stored PBKDF2
  hash) for all users.
- The environment-configured admin is seeded on first login; the env password
  wins for that account (if the admin's stored hash no longer matches the env
  password, the stored hash is refreshed on login), preserving today's behavior.
- Non-admin users can authenticate through the existing `POST /api/v1/auth/login`
  endpoint and receive a working signed cookie.
- Frontend `signInAction` stops pre-validating against env credentials and lets
  the backend decide; user-facing error states (`invalid`, `backend`) are kept.
- Login page helper copy stops saying the admin credential is required.
- Focused backend pytest coverage for login verification, admin seeding, and
  rejection paths.
- **Folded repairs (user-approved):** add `httpx` to `backend/requirements.txt`
  so the documented backend test command works on a fresh venv; fix the 9
  pre-existing `react-hooks/set-state-in-effect` lint errors in the 6 view
  components so `yarn lint` is green.

## Out of scope

- Creating or listing users from the UI or API (feature 12b).
- Any role checks on cluster endpoints or role-aware frontend navigation
  (feature 12c).
- Role assignment, password change flows, account deactivation.
- Changing the cookie/session format, the hash scheme, or the login request
  schema.

## Build loop

- `workflow.stepReview` = `feature`: one review after all steps complete; no
  per-step approval pauses.
- `workflow.checkpointCommits` = `disabled`: no per-step checkpoint commits.
  `/complete` creates the single feature commit.
- Branch is created by `/implement`.

## Build steps

- [x] 1. **Password helper module** - extract `_password_hash` from
  `routes.py` into `backend/app/core/passwords.py` as `hash_password` /
  `verify_password`, preserving the exact legacy scheme
  `pbkdf2_sha256$120000$<sha256_hex>` with the existing fixed salt so stored
  hashes stay valid. `verify_password` compares digests in constant time
  (`hmac.compare_digest`) and validates the stored scheme before use.
  `Done when`: existing `user_accounts.password_hash` values still verify, and a
  wrong password returns False (unit test in `test_auth_bridge.py` or a new
  `test_passwords.py`).

- [x] 2. **DB-backed login** - in `routes.py` `login`, replace the env-only
  credential check: normalize the email, look up the `UserAccount`. If the row
  is missing and the email is the configured admin email, seed the admin
  (role `admin`, hash from env password). If the row is missing otherwise,
  return the same 401 `authentication_required` used for every failure (no
  email enumeration). If the row exists, verify the submitted password against
  the stored hash; on mismatch return the same 401; if the email is the
  configured admin and the hash does not match the env password, refresh the
  stored hash to the env password. Issue the session row and signed cookie
  exactly as today.
  `Done when`: pytest covers non-admin correct/incorrect password login, admin
  seed on first login, and unknown-email 401; existing cookie resolution tests
  still pass.

- [x] 3. **Frontend login action trusts the backend** - in `k8s-ui/app/login/actions.ts`
  remove the `isValidCredential` gate; POST to `/api/v1/auth/login` directly,
  map HTTP 401 to `/login?error=invalid`, network failure to
  `/login?error=backend`, and on success call `createSession` with the returned
  cookie and `expires_at`. Remove the now-unused `isValidCredential` /
  `getAdminCredentials` helpers from `k8s-ui/lib/auth.ts`.
  `Done when`: a DB user (non-admin) sign-in sets the session cookie and lands on
  `/dashboard`, and wrong credentials or an unreachable backend render the
  existing error messages (manual browser check + `yarn lint` where deps exist).

- [x] 4. **Login page copy** - in `k8s-ui/app/login/page.tsx` replace the "Use
  the admin credential configured for the app to continue" hint so it states
  any provisioned app user account can sign in. Keep the prefilled defaults
  and the existing `invalid` / `backend` error rendering.
  `Done when`: the page no longer implies admin-only access and still shows
  identical error states (manual browser check where deps exist).

- [x] 5. **Backend tests for the auth bridge** - add focused pytest cases for
  the DB-backed login path: admin seed on first login, existing-user
  successful login, wrong password, and unknown email, asserting the same 401
  `authentication_required` shape and a valid session row for successes.
  `Done when`: `cd backend && python3 -m pytest` passes with the new cases
  (run where backend dependencies are installed; see Testing).

- [x] 6. **Backend test dependency** - add `httpx>=0.27,<1.0` to
  `backend/requirements.txt` so a fresh `pip install -r requirements.txt`
  supports the FastAPI `TestClient` used by the backend test suite.
  `Done when`: a fresh venv install of `requirements.txt` can collect and pass
  `pytest` (verify with the existing venv after install).

- [x] 7. **Frontend lint cleanup** - fix the 9 pre-existing
  `react-hooks/set-state-in-effect` lint errors in the 6 view components
  (cluster-view, core-resource-view, namespaces-view, overview-view,
  resource-detail-view, workloads-view) without changing visible behavior.
  `Done when`: `yarn lint` reports no errors.

## Files / areas

- `backend/app/core/passwords.py` (new) - `hash_password` / `verify_password`.
- `backend/app/api/v1/routes.py` - `login` route switches to DB-backed
  verification; imports the helpers.
- `backend/tests/test_auth_login.py` (new) - login/verification coverage for
  the DB-backed path.
- `k8s-ui/app/login/actions.ts` - drop the env pre-validation gate.
- `k8s-ui/lib/auth.ts` - remove `isValidCredential` / `getAdminCredentials`.
- `k8s-ui/app/login/page.tsx` - helper text only.
- `backend/requirements.txt` - add `httpx` (folded repair for the test gate).
- `k8s-ui/components/cluster-view.tsx`, `core-resource-view.tsx`,
  `namespaces-view.tsx`, `overview-view.tsx`, `resource-detail-view.tsx`,
  `workloads-view.tsx` - fold in the lint cleanup.
- No schema or migration change; `user_accounts.role` already exists and the
  `/auth/context` endpoint already returns the DB role.

## Data / contracts

- `POST /api/v1/auth/login` request/response unchanged:
  `LoginRequest {email, password}` -> `LoginResponse {cookie, expires_at}`.
- Every authentication failure returns 401 with
  `{"code": "authentication_required", "message": "Authentication is required"}`
  so callers cannot distinguish unknown emails from bad passwords.
- Password hash format is pinned to `pbkdf2_sha256$120000$<sha256_hex>` using
  the existing fixed salt; new users in 12b reuse `hash_password`. Verify uses
  the stored scheme string, not the raw secret, and compares in constant time.
- The signed cookie (`<payload>.<hmac-sha256>`, payload `{email, expiresAt}`)
  and the database `sessions` row format are unchanged; the Next.js middleware,
  `lib/auth.ts` session parsing, and FastAPI `get_current_actor` still agree.
- The env-configured admin remains the master: if the admin email has no row it
  is seeded with role `admin`, and if its stored hash does not match the env
  password the hash is refreshed at admin login. Non-admin users authenticate
  strictly against their stored hash.
- Roles (`admin`, `operator`, `viewer`) are read from the DB as today; 12a does
  not restrict any role at login or on cluster endpoints.

## Testing

- Backend: `cd backend && .venv/bin/python3 -m pytest` — **79 passed (was 73)**
  after 12a. New cases in `test_auth_login.py` cover admin seed on first login,
  non-admin correct/incorrect password, unknown-email 401, session cookie
  resolution for a non-admin user (`/auth/context` → `{identifier, role}`), and
  admin hash refresh when the env password changed.
- Frontend: `yarn build` — **passes**. `yarn lint` — **0 errors** (done-when for
  step 7 is met). The unused-`redirect` warning in `login/page.tsx` is gone; one
  pre-existing warning remains in `dashboard-shell.tsx:10`
  (`@next/next/no-location-assign-relative-destination`, out of scope). No
  frontend test runner exists.

## Notes for the AI

- Preserve the shared cookie format exactly (middleware.ts, lib/auth.ts, and
  FastAPI `get_current_actor` all parse it independently).
- Do not log passwords or cookie payloads; keep the 401 message generic.
- The fixed-salt PBKDF2 scheme is legacy but the stored hashes depend on it;
  do not rotate the scheme in this feature unless a migration plan is added.
- Follow the nextjs-agent-rules block in `k8s-ui/AGENTS.md` before editing
  frontend code (read the Next.js docs in `node_modules/next/dist/docs/` where
  present).
- `/complete` will run the final safety pass; `/fix` is the path for any bug
  discovered in 12a before 12b/12c begin.

## Open questions

None that block 12a. Product decisions for the broader RBAC feature are already
resolved: roles are admin/operator/viewer, provisioning is admin UI + API (12b),
and enforcement is backend + UI (12c).