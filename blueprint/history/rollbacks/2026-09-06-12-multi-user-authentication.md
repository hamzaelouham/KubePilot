# Rollback: Feature 12a - Multi-user authentication

**Type:** Rollback
**Status:** verified
**Branch:** `rollback/multi-user-authentication`
**Target feature:** 12a - Multi-user authentication
**Target archive:** `blueprint/history/features/12-multi-user-authentication.md`
**Target commit:** `7fa352ec17dde4bad0b26d4a1422d0bb43efeffe`
**Target parent:** `1f2b110a8552419af6bc957d0c8974562aaf5dbf`
**Reason:** Bugs found while testing the RBAC/multi-user features against Minikube
(group rollback: 12c and 12b already reversed; 12a is last).

## Goal

Restore the product behavior that existed before 12a (the feature-03-era
single-environment-admin login) while preserving Blueprint history, later
approved repairs that are independent of multi-user authentication, and the
already-recorded 12b/12c rollbacks.

## Scope

### Reverse

- The 12a product diff: DB-backed login (seeding non-admin `user_accounts`
  verification), the `passwords.py` helper, `test_auth_login.py`, the frontend
  `signInAction` DB-auth pass-through and login-page copy, and removal of the
  frontend env-credential pre-validation gate. Login returns to the feature-03
  contract: the env-configured admin credentials (`KUBEPILOT_ADMIN_EMAIL` /
  `KUBEPILOT_ADMIN_PASSWORD`) authenticate via the same signed-cookie flow.

### Preserve (compatibility work)

- The `httpx` requirement in `backend/requirements.txt` — folded repair from
  12a; the documented backend test command (FastAPI `TestClient` → `httpx`) needs
  it on fresh venvs.
- The 6 view-component lint fixes (cluster/core-resource/namespaces/overview/
  resource-detail/workloads view) — folded repair from 12a; reversing them would
  re-introduce the 9 `react-hooks/set-state-in-effect` errors and fail
  `yarn lint`.
- The archived 12a spec, the `blueprint/history/rollbacks/*` pair, build-plan
  and project-plan changes, Blueprint context, adapter skills, prototypes, and
  the unrelated `636b48f chore(ci)` commit.

### Out of scope

- Destructive data migration — `user_accounts`/`sessions` rows stay stored and
  unused (code-only reversal, no downgrade)
- Unrelated cleanup or refactoring

## Product paths

- `backend/app/api/v1/routes.py`
- `backend/app/core/passwords.py` (new)
- `backend/requirements.txt`
- `backend/tests/test_auth_login.py` (new)
- `k8s-ui/app/login/actions.ts`
- `k8s-ui/app/login/page.tsx`
- `k8s-ui/components/cluster-view.tsx`
- `k8s-ui/components/core-resource-view.tsx`
- `k8s-ui/components/namespaces-view.tsx`
- `k8s-ui/components/overview-view.tsx`
- `k8s-ui/components/resource-detail-view.tsx`
- `k8s-ui/components/workloads-view.tsx`
- `k8s-ui/lib/auth.ts`

## Later-change risk

**Classification:** Overlap, likely compatible

| Later commit | Shared path or contract | Required handling |
| ------------ | ----------------------- | ----------------- |
| `6353bbc feat(user-management)` (12b) | `routes.py` | Net-zero (fully rolled back) |
| `2397243 feat(role-enforcement)` (12c) | `routes.py` | Net-zero (fully rolled back) |
| `3c2436d revert: roll back 12c` | `routes.py` | Restored 12-era state |
| `6351d49 revert: roll back 12b` | `routes.py` | Restored 12-era state |

Verified: `git diff 7fa352ec HEAD` over all 13 product paths is **empty** — every
later delta on these files has already been reversed, so the target's reverse
patch applies cleanly. No product dependency on the 12a login behavior remains at
`HEAD`; the signed-cookie/session format and Next.js middleware are unchanged by
this rollback.

## Build steps

^- [x] Apply target commit `7fa352ec`'s product diff in reverse with the Type:
  Rollback guard in `/implement`.
  - Done when: the reverse patch applies only to the 13 product paths, protected
    Blueprint paths are unchanged, and the staged diff replaces exactly the 12a
    changes (no 12b/12c/CI edits are reverted).
^- [x] Re-apply the two approved compatibility repairs: `httpx` in
  `backend/requirements.txt` and the 6 view-component lint fixes.
  - Done when: `requirements.txt` still pins `httpx`, and the 6 view components
    keep the lint-clean, behavior-preserving form from 12a.
^- [x] Run the project checks and the observable removal path below.
  - Done when: backend pytest passes (73 tests, the auth-bridge tests removed),
    `yarn verify` builds, `yarn lint` reports 0 errors, and the login flow no
    longer accepts a non-admin DB user.

## Verification

- Build: `cd backend && .venv/bin/python3 -m pytest && cd k8s-ui && yarn verify`
- Tests: `.venv/bin/python3 -m pytest` (expect **73** passed; 6 auth-bridge cases
  removed), plus `yarn lint` (0 errors)
- Removed behavior: `backend/app/core/passwords.py` and
  `backend/tests/test_auth_login.py` deleted; `login` verifies only the
  env-configured admin credentials (seeding/refresh of `UserAccount` and non-admin
  verification gone); `k8s-ui/lib/auth.ts` regains the env-credential helpers and
  `signInAction` pre-validates against them; the login page tells the user the
  admin credential is required.
- Regression path: signing in with the env-configured admin still yields a
  working session, lands on `/dashboard`, and cluster views load; the dashboard
  middleware and `/api/v1/auth/context` keep verifying the signed cookie.

## Notes for the AI

- Stop on patch conflicts or evidence of an unplanned dependency.
- Do not delete the original feature archive.
- Do not broaden this rollback beyond the product paths and compatibility work
  above. The individual lint fixes are already approved and behavior-preserving;
  re-apply them as the exact 12a versions, not new refactors.