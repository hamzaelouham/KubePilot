# Rollback: Feature 12c - Role-based access enforcement

**Type:** Rollback
**Status:** verified
**Branch:** `rollback/role-based-access-enforcement`
**Target feature:** 12c - Role-based access enforcement
**Target archive:** `blueprint/history/features/12c-role-based-access-enforcement.md`
**Target commit:** `2397243dce9f3ca7e9bd8e67c0ae80dfb4ad4452`
**Target parent:** `636b48f0e38688541743cfeab41bc2d9b3d81a7e`
**Reason:** Bugs found while testing the RBAC/multi-user features against Minikube.

## Goal

Restore the product behavior that existed before 12c (the state right after 12b
completed) while preserving Blueprint history and later work.

## Scope

### Reverse

- The 12c product diff: the `require_minimum_role` backend gate on the 11 cluster
  read routes, the new `backend/app/core/roles.py`, the new
  `backend/tests/test_role_access.py`, and the role badge / `actorRole` logic in
  `k8s-ui/components/dashboard-shell.tsx`.

### Preserve

- The archived 12c spec at `blueprint/history/features/12c-role-based-access-enforcement.md`
- 12b behavior (admin user provisioning, `require_admin`, `"Admin access is
  required"` 403, admin nav) and 12 multi-user authentication behavior
- Blueprint context, build-plan/project-plan, adapter skills, the rollback spec,
  prototypes
- The unrelated `636b48f chore(ci)` commit (AGENTS.md, package.json, .gitignore)

### Out of scope

- Cascading rollbacks of 12b and 12 in this spec (sequenced separately)
- Destructive data migration
- Unrelated cleanup or refactoring

## Product paths

- `backend/app/api/v1/routes.py`
- `backend/app/core/roles.py` (new)
- `backend/tests/test_role_access.py` (new)
- `k8s-ui/components/dashboard-shell.tsx`

## Later-change risk

**Classification:** No overlap

Target `2397243` is the newest commit on `master`; no later commits touch these
paths. The only commits after the target-parent are the 12c squash itself and
none afterward. `636b48f chore(ci)` (the parent) is preserved untouched.

| Later commit | Shared path or contract | Required handling |
| ------------ | ----------------------- | ----------------- |
| (none after target) | — | — |

Confirmed during planning: 12c's contracts (`require_minimum_role`, `ROLE_RANK`,
`actorRole`, role Badge) are imported only within the four product paths above.
12b's `require_admin` and route imports are separate and unaffected; no frontend
component other than `dashboard-shell.tsx` references the badge.

## Build steps

- [x] Apply target commit `2397243`'s product diff in reverse with the Type:
  Rollback guard in `/implement`.
  - Done when: the reverse patch applies only to the four product paths, protected
    Blueprint paths are unchanged, and the staged diff replaces exactly the 12c
    changes (no 12b/12/CI edits are reverted).
- [x] Run the project checks and the observable removal path below.
  - Done when: backend pytest passes (94 tests, the 9 role tests removed), the
    k8s-ui build and lint pass, no `require_minimum_role` remains in the app, and
    12b's admin gating still works.

## Verification

- Build: `cd backend && .venv/bin/python3 -m pytest && cd k8s-ui && yarn verify`
- Tests: `.venv/bin/python3 -m pytest` (expect 94 passed)
- Removed behavior: `require_minimum_role` no longer exists anywhere in
  `backend/app` or `backend/tests`; `backend/app/core/roles.py` and
  `backend/tests/test_role_access.py` are deleted; `dashboard-shell.tsx` no longer
  renders a role `<Badge>` or derives nav from `actorRole`; no `403
  insufficient_permissions` path remains.
- Regression path: a viewer-only session can still authenticate and reach the
  cluster resource routes (200), the Admin menu and `/users` provisioning still
  work only for admins (12b), and the header/theme (features 15/16) render as
  before.

## Notes for the AI

- Stop on patch conflicts or evidence of an unplanned dependency.
- Do not delete the original feature archive.
- Do not broaden this rollback beyond the product paths above.
- **Subsequent rollbacks (sequenced, NOT this spec):** after this rollback
  completes/merges, run `/rollback 12b` and then `/rollback 12` to remove the
  remainder of the RBAC/multi-user group in reverse integration order. Each gets
  its own spec, implement, check, and complete cycle.