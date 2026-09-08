# Current Feature

**Type:** Feature
**Build plan:** 18i
**Branch:** `feature/installation-progress-ui`
**Status:** verified

## Goal

Add the installation progress UI (18i): after the user submits the install
dialog (18e/18f) and gets a queued `job_id`, the dialog shows immediate live
feedback as Helm runs — `queued → running → succeeded/failed` — by polling the
18h status API. Closing the dialog only closes the UI; it never cancels the
installation (there is no cancel action anywhere in this feature).

## In scope

- Progress view in the install dialog (`components/install-dialog.tsx`):
  - After a successful `POST /api/marketplace/install`, the dialog transitions
    from the form to a progress view showing a summary line (package name,
    cluster, namespace, release name) and the current status.
  - Polls `GET /api/marketplace/installations/{job_id}` every 2000 ms using the
    file's existing `fetch` + `cache: "no-store"` + `AbortSignal` pattern,
    starting immediately on job acquisition and stopping on a terminal status or
    unmount.
  - Status rendering (existing `Badge` from `components/ui/badge.tsx`; a small
    inline `animate-spin` spinner SVG while non-terminal — no new dependency):
    - `queued` → Badge `secondary` "Queued", spinner
    - `running` → Badge `secondary` "Running", spinner
    - `succeeded` → Badge `default` "Succeeded" (terminal)
    - `failed` → Badge `destructive` "Failed" plus the job's `error_message` in
      an alert `role="alert"` (terminal)
    - `cancelled` → Badge `outline` "Cancelled" (terminal; reserved in 18g but a
      legal response, so it must render rather than spin forever)
  - Accessibility: the status region has `aria-live="polite"`; the terminal
    success/failure text is announced; every control has a visible label.
  - Close-only semantics: a "Close" button in the footer, the dialog X, Esc, and
    backdrop all just set `open=false` and reset the dialog for the next
    install — no cancel request, no confirmation dialog.
- Focused error handling for the poll itself:
  - Network failure or non-OK status response (e.g., 404/500 from 18h) shows an
    alert with a Retry button that triggers an immediate re-poll; the job id is
    never discarded and terminal statuses are never overwritten by a poll
    error while the last known status was already terminal.
- Build/lint green: `cd k8s-ui && yarn lint` and `cd k8s-ui && yarn verify`
  (next build) pass. Declared Verify passes at the end.

## Out of scope

- **18j** installation history table and its endpoint; a way to reopen a
  closed job's progress (closing discards the in-dialog view; the job keeps
  running and is only re-viewable through a future 18j surface)
- Job cancellation, retry-from-failure, or any new backend/API contract
- Any styling beyond the minimal needed (visual polish stays in 18l)

## Build loop

`workflow.stepReview: "feature"` (one review after all steps);
`workflow.checkpointCommits: "disabled"`. `/complete` creates the final feature
commit.

## Build steps

- [x] 1. **Progress view + polling.**
      In `components/install-dialog.tsx`, add a `JobProgress` subcomponent
      (same file, no new module): receives the job id and the summary fields,
      polls the 18h endpoint every 2000 ms, renders the summary line, status
      badge + spinner, terminal success/failure (with `error_message`), and
      footer Close button. Wire `submitInstall` to swap to it instead of the
      current `Installation queued (job …)` footer text.
      **Done when:** `cd k8s-ui && yarn lint` and `cd k8s-ui && yarn verify`
      pass, and a manual run shows queued → running → succeeded while the 18g
      worker processes a real install.
- [x] 2. **Poll resilience + accessibility.**
      Add poll-error handling (alert + Retry, immediate re-poll; never overwrite
      a terminal status, never discard the job id), `aria-live` support, and the
      closed-dialog reset path. Confirm by review that no cancel/uninstall call
      exists and every close path only unmounts the UI.
      **Done when:** `cd k8s-ui && yarn lint` and `cd k8s-ui && yarn verify`
      pass, and a code-level review confirms the close-only contract and abort
      cleanup on unmount.
- [x] 3. **Verify.**
      Run the declared Verify once:
      `cd backend && .venv/bin/python3 -m pytest` (unchanged 210) and
      `cd k8s-ui && yarn verify`. Self-review against In scope, then set
      `**Status:** verified`.
      **Done when:** both commands pass and the spec is marked verified.

## Files / areas

- `k8s-ui/components/install-dialog.tsx` — add `JobProgress`, rework the footer
  handoff after POST; everything else in this file stays
- `k8s-ui/components/ui/badge.tsx` — consumed (variants `secondary`, `default`,
  `destructive`, `outline`); no changes
- No backend files; no new dependencies

## Data / contracts

- Consumes exactly the 18h response shape: `job_id`, `package_name`, `cluster`,
  `namespace`, `release_name`, `status`
  (`queued|running|succeeded|failed|cancelled`), `error_message`,
  `created_at`, `started_at`, `completed_at`.
- Status string values are compared exactly against the backend contract; any
  unexpected status value is treated as "keep polling" with the current badge
  states (spinner), never as a crash.
- `job_id` comes only from the 18f POST response; the poll never guesses an id.
- Timestamps from the API are not rendered in 18i (they surface in 18j).

## Testing

- No frontend test runner exists in this project and 18i is UI-only, so there
  are no logic tests to add here (`verification.logicTests: when-configured`
  is satisfied by the unchanged backend suite at step 3). No browser tests
  exist; the manual try path below is the observable proof. Build + lint are
  the automated gates each step.

## Notes for the AI

- The Next.js version in this repo has breaking changes — read the relevant
  guide under `node_modules/next/dist/docs/` before writing code (per the
  `k8s-ui/AGENTS.md` block), though this change only uses client-side
  `fetch`/`useState`/`useEffect` already established in the file.
- `error_message` is server-provided text; React escaping is sufficient (render
  it as text, never with `dangerouslySetInnerHTML`).
- Keep the form's existing optimistic UX untouched (pkg null closes the dialog
  body via the `key` on `InstallDialogBody`); do not destabilize version /
  namespace loads.
- The footer currently renders `Installation queued (job {queuedJobId})` — that
  is the spot to replace; do not regress the disabled-until-valid submit state.

## Open questions

None. Whether closing the dialog should preserve a way to re-open a running
job's progress is deferred to 18j (history), which is the repository-native
place for it.