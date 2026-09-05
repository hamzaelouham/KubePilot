# Rollback: Feature 12b - User management

**Type:** Rollback
**Status:** verified
**Branch:** `rollback/user-management`
**Target feature:** 12b - User management
**Target archive:** `blueprint/history/features/12b-user-management.md`
**Target commit:** `6353bbcd3f2df4fcc2d7baa62a3fc516541679a9`
**Target parent:** `d353ddae8de236c555b66e716808e6e3054b5094`
**Reason:** Bugs found while testing the RBAC/multi-user features against Minikube
(group rollback: 12c already reversed, 12b next, 12 last).

## Goal

Restore the product behavior that existed before 12b (the state right after 12
completed) while preserving Blueprint history and later work. This is the second
rollback of the RBAC/multi-user group; 12c is already reversed on `master`.

## Scope

### Reverse

- The 12b product diff: the `is_active` column + alembic migration, admin-only
  `/api/v1/users` endpoints and `require_admin`, the frontend admin surface
  (`/dashboard/admin`, `UsersManagement`, admin proxy routes, role-aware Admin
  nav in the shell), and the `select`/`dialog`/`alert-dialog` shadcn additions.

### Preserve

- The archived 12b spec at `blueprint/history/features/12b-user-management.md`
- 12 multi-user authentication behavior (login page, cookie/session,
  `auth/context`, seed admin) and the 12-era product state
- The 12c rollback archive, build-plan/project-plan, Blueprint context, adapter
  skills, prototypes
- The `636b48f chore(ci)` commit (AGENTS.md, package.json, .gitignore)

### Out of scope

- The subsequent 12 rollback (sequenced separately)
- Destructive data migration — the `is_active` column already applied to the
  Minikube DB stays stored but unused (code-only reversal, no downgrade)
- Unrelated cleanup or refactoring

## Product paths

- `backend/alembic/versions/570583371bec_add_user_accounts_is_active.py`
- `backend/app/api/v1/routes.py`
- `backend/app/api/v1/users.py`
- `backend/app/api/v1/users_schemas.py`
- `backend/app/core/dependencies.py`
- `backend/app/main.py`
- `backend/app/models/entities.py`
- `backend/tests/test_user_management.py`
- `k8s-ui/app/api/auth/context/route.ts`
- `k8s-ui/app/api/users/[id]/route.ts`
- `k8s-ui/app/api/users/route.ts`
- `k8s-ui/app/dashboard/admin/page.tsx`
- `k8s-ui/components/admin-users-view.tsx`
- `k8s-ui/components/dashboard-shell.tsx`
- `k8s-ui/components/ui/alert-dialog.tsx`
- `k8s-ui/components/ui/dialog.tsx`
- `k8s-ui/components/ui/select.tsx`

## Later-change risk

**Classification:** Overlap, likely compatible

| Later commit | Shared path or contract | Required handling |
| ------------ | ----------------------- | ----------------- |
| `2397243 feat(role-enforcement)` (12c) | `routes.py`, `dashboard-shell.tsx` | Net-zero: fully reversed by the next row; current files match the 12b-completed content |
| `3c2436d revert: roll back 12c` | `routes.py`, `dashboard-shell.tsx` | Reverted 12c's deltas; listed files now equal the 12b-era content, so 12b's reverse patch applies cleanly |

No remaining consumers of 12b assets at `HEAD`: the frontend `/api/auth/context`
proxy is only called by 12b assets (`dashboard-shell.tsx` at HEAD is the 12b-era
shell which reverts to the 12-era shell shown not to reference it);
`select`/`dialog`/`alert-dialog` are imported only by `admin-users-view.tsx`;
the admin page depends only on 12b files. No compatibility edits required.

## Build steps

- [x] Apply target commit `6353bbc`'s product diff in reverse with the Type:
  Rollback guard in `/implement`.
  - Done when: the reverse patch applies only to the 17 product paths, protected
    Blueprint paths are unchanged, and the staged diff replaces exactly the 12b
    changes (no 12/12c/CI edits are reverted).
- [x] Run the project checks and the observable removal path below.
  - Done when: backend pytest passes (79 tests, the user-management tests
    removed), the k8s-ui build and lint pass, no `/api/v1/users*` route remains
    in the backend, and the frontend has no admin proxy routes, `/dashboard/admin`
    page, or Admin nav.

## Verification

- Build: `cd backend && .venv/bin/python3 -m pytest && cd k8s-ui && yarn verify`
- Tests: `.venv/bin/python3 -m pytest` (expect 79 passed)
- Removed behavior: `GET/POST /api/v1/users`, `PATCH .../role`, `POST
  .../deactivate` no longer exist; `require_admin` and the
  "Admin access is required" 403 path are gone; `app/dashboard/admin/page.tsx`
  and `components/admin-users-view.tsx` are deleted; the shell shows no
  Admin/Users nav; `components/ui/{select,dialog,alert-dialog}.tsx` and the
  `is_active` alembic revision are deleted.
- Regression path: a valid 12-era session still logs in and reaches the dashboard
  and cluster views; `/login` and the dashboard gate middleware redirect
  unauthenticated users as before; header/theme (features 15/16) render with the
  retained primitives.

## Notes for the AI

- Stop on patch conflicts or evidence of an unplanned dependency.
- Do not delete the original feature archive.
- Do not broaden this rollback beyond the product paths above.
- **Subsequent rollback (sequenced, NOT this spec):** after this rollback
  completes/merges, run `/rollback 12` to remove multi-user authentication, with
  its own spec, implement, check, and complete cycle.