# Current Feature

**Feature 18n - Release actions UI**

**Branch:** `feature/release-actions-ui`

> **Status:** verified - all build steps checked; Verify green (backend 245 passed, `yarn verify` build+lint+typecheck clean).

## Goal

Admins and operators (same set that has `marketplace:release`) can act on a completed Marketplace install from the installation-history table: **Roll back** the release to its previous revision or **Uninstall** (delete) it. Both actions call the 18m backend endpoints (`POST /api/v1/marketplace/installations/{job_id}/rollback` and `/uninstall`), then show progress in the same queued/running/terminal dialog pattern the install flow uses. Viewers never see the action controls.

## In scope

- UI only. Backend from 18m is already shipped (endpoints, permission, audit, worker) - no backend changes.
- History rows gain an **Actions** column, present only for admin/operator users, with **Roll back** and **Uninstall** buttons on rows where `action === "install"` and `status === "succeeded"`. All other rows show no controls; viewers render the table without the Actions column.
- A release-action dialog that (1) confirms the action - **Uninstall** is destructive and uses the destructive variant/alert; (2) POSTs to the new proxy routes; (3) on 201 shows job progress polling `GET /api/marketplace/installations/{job_id}` until a terminal stage, with action-aware text (queued/running/succeeded/failed/cancelled) reusing the install `JobProgress` pattern (spinner + badge + error alert + retry).
- Two new Next.js API proxy routes mirroring `app/api/marketplace/install/route.ts`:
  - `POST /api/marketplace/installations/[job_id]/rollback`
  - `POST /api/marketplace/installations/[job_id]/uninstall`
- On a terminal result the history list refreshes so the new queued/running/succeeded job row appears (history is a job list; a rollback/uninstall creates a new row).

## Out of scope

- Revision picker, upgrades, managing releases the app did not install (backend contract).
- Actions on `failed` or `rollback`/`uninstall` source jobs (backend rejects with 422; rows simply show no buttons).
- 18l UI polish; backend changes (18m shipped).
- Changing the install flow or its dialogs.

## Build loop

- Branch: `feature/release-actions-ui` from `master` (`acbf108`). Per `blueprint/config.json`: `checkpointCommits` disabled (no checkpoint commits), `stepReview: feature` (one review checkpoint after all implementation steps; `/complete` creates the final feature commit).
- Quality gates (`regular`): audit, independent review, check, try guide all `manual` - run only when explicitly requested. Logic tests gate: no frontend test runner (documented in AGENTS.md; UI verification is `yarn verify`). `uiEvidence` is `when-available`.

## Build steps

- [x] 1. **Proxy routes** - add `k8s-ui/app/api/marketplace/installations/[job_id]/rollback/route.ts` and `.../uninstall/route.ts`, each a `POST` mirroring `k8s-ui/app/api/marketplace/install/route.ts` (forward cookie, proxy to `backendUrl() + /api/v1/marketplace/installations/{job_id}/rollback|uninstall`, keep `proxyResponse` passthrough of backend error bodies, `backendUnavailable("The marketplace service is unavailable")`).
   - Done when: `yarn verify` is clean and the routes follow the existing proxy pattern byte-for-byte except path/method.
- [x] 2. **History row typing + Actions column** - add `action: "install" | "rollback" | "uninstall"` to the `Installation` type in `k8s-ui/components/marketplace-history.tsx`. Add an Actions column whose cell renders the two buttons only when `row.original.action === "install" && row.original.status === "succeeded"`; otherwise render an empty span. Move `tableColumns` inside the component (or derive conditionally) so the Actions column is omitted entirely when the user cannot manage, so viewers see no action controls at all.
   - Done when: typecheck passes; the column is absent for viewers and present-but-inert elsewhere.
- [x] 3. **Permission plumbing** - `k8s-ui/components/marketplace-view.tsx` computes `canManage = user.role === "admin" || user.role === "operator"` and passes it to `<MarketplaceHistory canManage={canManage} />`. Keep the prop name stable for viewer/operator/admin.
   - Done when: typecheck passes and the prop flows from the session user.
- [x] 4. **Release action dialog** - new `k8s-ui/components/release-action-dialog.tsx` (or `release-actions.tsx`):
   - Confirm stage: reuse the existing `ui/dialog` / `ui/alert-dialog` components. **Uninstall** uses the destructive confirmation; **Roll back** uses a neutral confirmation. Both describe the target (`package · cluster · namespace · release`).
   - Submit stage: POST the action to its proxy route; on non-ok surface the backend error message (from `body.message`; covers 403 `insufficient_permissions` / `password_change_required`, 404, 422, 409 `release_action_conflict`, 503 `backend_unavailable`) with dismiss/retry - do not open the progress view.
   - Progress stage: on 201 `{job_id, status:"queued"}` poll `GET /api/marketplace/installations/{job_id}` exactly like install `JobProgress` (`POLL_MS` 2000, spinner + status badge + queued/running/succeeded/failed/cancelled labels, failed shows `error_message`, poll-error alert with Retry), with action-aware copy ("Rollback queued. Waiting for the background worker...", "Helm is rolling the release back.", "Rollback succeeded.", "Helm is uninstalling the release.", "Uninstalled.").
   - On closing after a terminal stage, refresh the history list. Keep the dialog open with the terminal message visible until the user closes it.
   - Done when: `yarn verify` clean; role/permission, error, and terminal paths are all wired; no install-flow regressions.
- [x] 5. **Full Verify** - `cd backend && .venv/bin/python3 -m pytest` and `cd k8s-ui && yarn verify`.
   - Done when: backend `245 passed` (unchanged) and `yarn verify` build+lint+typecheck clean.

## Files / areas

- `k8s-ui/app/api/marketplace/installations/[job_id]/rollback/route.ts` (new)
- `k8s-ui/app/api/marketplace/installations/[job_id]/uninstall/route.ts` (new)
- `k8s-ui/components/marketplace-history.tsx` (action field, Actions column, `canManage` prop)
- `k8s-ui/components/marketplace-view.tsx` (compute + pass `canManage`)
- `k8s-ui/components/release-action-dialog.tsx` (new; confirm + submit + progress stages)

## Data / contracts

- Row eligibility: only `action === "install" && status === "succeeded"` rows get buttons; the backend independently enforces this (safe double-guard).
- Proxy routes pass response bodies through unchanged (`proxyResponse`), so the client reads `body.message` exactly as the install dialog does. `backend_unavailable` returns `{code, message}` at 503.
- 201 `{job_id, status: "queued"}`; progress polls the existing GET status endpoint (no schema change).
- History list is jobs, not releases: each action creates a new row; the table shows the current job's own status (e.g. a succeeded rollback job). Buttons appear only on install rows, so a new rollback/uninstall job itself never shows action buttons.

## Testing

- No frontend test runner (per AGENTS.md); the gate is `yarn verify` (lint + typecheck + build). Mirror the existing component patterns (`"use client"`, explicit `status` discrimated unions, `role="alert"`, `aria-live` on progress).
- Manual verification notes for the review/`try` handoff: as operator - succeeded install row shows Roll back/Uninstall; queued/running/failed rows show none; run Roll back -> confirm -> progress appears and resolves to Succeeded; run Uninstall -> destructive confirm -> Succeeded; cancel a running action? (backend 409 guard on requeue); as viewer - no Actions column, no way to trigger an action; failed POST (e.g. uninstall a release that was already removed) surfaces the backend message with Retry.

## Notes for the AI

- Baseline entering the feature: backend `245 passed`; `yarn verify` clean (lint+typecheck+build); branch `feature/release-actions-ui` from `master` at `acbf108` (18m merged/pushed).
- Reuse the install `JobProgress`/`Spinner`/`isJobStatus`/`TERMINAL_JOB_STAGES`/`JOB_STAGE_*` patterns from `k8s-ui/components/install-dialog.tsx` (they are not exported - copy the pattern, do not refactor the install dialog).
- Do not touch backend files; do not start the dev server; verification is the pytest + `yarn verify` gate above.
- Keep action names stable (`rollback` | `uninstall`) and the row-state predicate in one place.

## Open questions

- Should the Actions column show for `failed` installs (cleanup of partial resources)? 18m scoped actions to `succeeded` only; keeping the UI and backend contract aligned (no buttons on failed rows). Flag in the review handoff.
- Single-button vs. menu for more actions later: the backend contract caps actions at Roll back + Uninstall for now; keep the column shaped so an upgrade action could slot in later (no menu abstraction yet).