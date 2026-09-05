# Current Feature

> **Generated file.** Holds the one feature, fix, or rollback being built right now.

**Feature 12c: Role-based access enforcement.**

**Type:** Feature

**Status:** verified

**Branch:** feature/role-based-access-enforcement

## Goal

Make the `admin | operator | viewer` roles from 12a/12b mean something on every
cluster endpoint and in the UI. The backend enforces a role-minimum gate on all
cluster operations through one explicit, tested policy source; the UI becomes
role-aware (shown actor role, admin-only surfaces already hidden). Because the
entire cluster surface is read-only today (no scale/restart/write actions exist
in the repo — see the overview's open question), the role matrix is: all three
roles may read cluster state; user management stays admin-only; any future
mutating cluster action requires at least `operator`.

## In scope

- A single role-policy module with a rank order (`viewer` < `operator` <
  `admin`) and a reusable `require_minimum_role(min_role)` FastAPI dependency
  that resolves the authenticated actor and returns `403` for roles below the
  minimum.
- Applying that gate to every existing cluster route (read-only today) with a
  `viewer` minimum, so each cluster endpoint goes through explicit role
  enforcement and any newly added role is denied by default until assigned a
  rank.
- Focused backend tests covering the role matrix on cluster reads and the
  gate's deny behavior, without touching the 12b admin routes' contract.
- Frontend role awareness: the signed-in actor's role shown in the dashboard
  shell header; the admin navigation entry and `/dashboard/admin` redirect
  stay as built in 12b (verified, not reworked).
- A `403` `{"code":"insufficient_permissions",...}` body for the new gate that
  does not reuse or alter the 12b admin message
  (`"Admin access is required"`).

## Out of scope

- Mutating cluster operations (scale, restart, delete, exec) — not built in the
  repo; the overview records "Basic resource actions" as an unbuilt MVP plan
  item that needs its own build-plan feature. This feature only pre-locks the
  `operator`+ floor for their future gate.
- Limiting what a `viewer` may read (YAML, logs, events, namespaces are all
  open to every authenticated role today). A stricter viewer policy is a
  product decision; see Open questions.
- Changes to the login, session, cookie, or `auth/context` contracts.
- Audit-action recording of role-gated events, per-user preferences, or
  per-namespace access.
- New URLs, new schemas, or UI action surfaces.

## Build loop

Plan steps on branch `feature/role-based-access-enforcement` (prefix from
config: `feature/`). `workflow.stepReview` is `feature` (one review after all
steps) and `workflow.checkpointCommits` are `disabled` — no per-step commits or
approval pauses; `/complete` makes the single work commit. No migration is
expected (pure code/tests); each step runs the declared Verify.
`verification.logicTests` is `when-configured` (pytest runner exists) and
`verification.uiEvidence` is `when-available` (the role badge needs a browser
on the minikube deploy; the redirect and hidden entry were already proven in
12b).

## Build steps

- [x] 1. **Backend role gate and cluster-route enforcement** - add
  `backend/app/core/roles.py` with `ROLE_RANK = {"viewer": 0, "operator": 1,
  "admin": 2}` and `require_minimum_role(min_role: str)` returning a FastAPI
  dependency that resolves the actor via `get_current_actor`, then raises `403`
  `{"code":"insufficient_permissions","message":"Insufficient permissions for
  the required role"}` when `ROLE_RANK[actor.role] < ROLE_RANK[min_role]` (and
  `500`/`KeyError`-safe for an unknown role — treat unknown roles as below
  every minimum). Apply `require_minimum_role("viewer")` to every cluster GET
  route in `backend/app/api/v1/routes.py` (`/cluster/status`, `/cluster/namespaces`,
  `/cluster/resources/{resource_type}`, resource detail, yaml, logs, events, and
  the four metrics routes), replacing each `_actor: Annotated[AuthenticatedActor,
  Depends(get_current_actor)]` with the gate. Keep `health`, `/auth/*`, and the
  `require_admin`-guarded `users` router exactly as they are — do not change
  the 12b `403` message or any `users` response.
  `Done when`: new `backend/tests/test_role_access.py` passes — viewer,
  operator, and admin each get `200` from `/api/v1/cluster/namespaces` and
  `/api/v1/auth/context`; unauthenticated gets `401`; and the dependency
  itself denies a viewer from a `require_minimum_role("operator")` route with
  the exact 403 body above; `.venv/bin/python3 -m pytest` green (baseline 94
  plus new cases); migration SQL check unchanged.
- [x] 2. **Frontend role-aware shell** - in
  `k8s-ui/components/dashboard-shell.tsx`, extend the existing `/api/auth/context`
  fetch (already present for admin-gating) to retain the actor `role` in state
  and render a small `Badge` with the role (`admin` / `operator` / `viewer`) in
  the header beside the existing controls, rendering nothing until the fetch
  resolves (no flash of a wrong role). Do not change the Admin nav entry logic
  or the `/dashboard/admin` server redirect from 12b; confirm operator and
  viewer never see the Admin entry and a non-admin hitting `/dashboard/admin`
  still redirects.
  `Done when`: `yarn build` compiles and `yarn lint` reports 0 errors; the
  badge text comes from `actor.role` (backend truth), not local guesswork; no
  new routes or cookie changes.

## Files / areas

- `backend/app/core/roles.py` — new: rank map + `require_minimum_role` gate.
- `backend/app/core/dependencies.py` — `require_admin` unchanged; imports for
  the new gate reused by routes (or the gate lives here and `roles.py` holds
  only the policy constants — pick the smaller layout, keep one source of
  truth for `ROLE_RANK`).
- `backend/app/api/v1/routes.py` — all cluster GET routes switch from
  `get_current_actor` to the viewer-minimum gate.
- `backend/tests/test_role_access.py` — new focused matrix tests reusing the
  `build_client` / `add_user` / `login` helpers already in
  `backend/tests/test_user_management.py`.
- `k8s-ui/components/dashboard-shell.tsx` — retain role from the existing
  auth-context fetch; render role `Badge` in the header.
- `k8s-ui/components/ui/badge.tsx` — existing primitive; no new dependency.

## Data / contracts

- Roles: fixed lowercase set `{"admin","operator","viewer"}` (12b contract);
  rank order `viewer` < `operator` < `admin` is the single policy constant.
- New gate 403: `{"code":"insufficient_permissions","message":"Insufficient
  permissions for the required role"}`. This message is for cluster/role-gated
  routes only; the 12b user-management 403 stays `"Admin access is required"`
  (unverifiable byte-for-byte preservation via the existing
  `test_user_management.py` assertions).
- Unknown/removed roles in the actor session resolve to below every minimum
  (deny), never a 500.
- `auth/context`, login, logout, user management, health: unchanged request,
  response, and status shapes.
- The frontend role badge is presentation only; the backend session is the
  trusted source. The frontend never opens a cluster endpoint based on local
  role claims.

## Testing

- Backend logic gate (runner exists): new `backend/tests/test_role_access.py`
  covering the three-role 200 matrix on a representative cluster read, the 401
  unauth path, the 403 deny path at the `operator` minimum, and an unknown-role
  deny (direct dependency test via an injected test route or a `TestClient`
  route override). Keep `test_user_management.py` untouched so the 12b
  contract stays pinned.
- Migrations: `cd backend && PYTHONPATH=. alembic upgrade head --sql` must
  render unchanged output (no schema change expected).
- UI: the declared `Verify` (`cd backend && .venv/bin/python3 -m pytest &&
  cd k8s-ui && yarn verify`) passes; `yarn lint` 0 errors. The role badge
  itself is browser evidence captured on the next minikube deploy
  (`uiEvidence: when-available`); the Admin-entry gating and non-admin redirect
  were verified live in 12b and must remain unchanged.

## Notes for the AI

- Backend is the enforcement point. The frontend badge is cosmetic; never gate
  a data fetch on a locally parsed role claim.
- Reuse the existing `build_client`/`add_user`/`login` test helpers from
  `backend/tests/test_user_management.py` directly (import them or duplicate
  the 30-line harness) rather than inventing a new fixture; do not modify
  `test_user_management.py`'s assertions.
- Preserve every existing 12b contract — especially the `users` 403 message and
  all `auth/context` behavior — and let the 12b tests prove that.
- The shell already fetches `/api/auth/context` to decide the Admin entry;
  extend that one fetch for the badge instead of adding a second request.
- Do not add write-capable buttons, action menus, or roles-based resource
  filters — there are no mutating endpoints, and the review gate forbids
  inventing scope pulled from a later feature.
- Read `k8s-ui/AGENTS.md` nextjs-agent-rules and the Next docs in
  `node_modules/next/dist/docs/` before editing frontend code.

## Open questions

- **Viewer read depth later.** When a real write/action feature arrives
  (scale/restart per the overview's open question, or 13/14), should `viewer`
  keep full read access (YAML, logs, events) or be limited to health/status
  reads? Non-blocking now: every current read stays open to all three roles and
  the write floor is pre-locked to `operator`; the stricter viewer policy is a
  product decision for that later feature.
- **Operator vs admin on future writes.** The matrix reserves only user
  management for `admin`; cluster actions would be `operator`+. No product
  signal separates them further; recorded as the default unless later
  disagree.