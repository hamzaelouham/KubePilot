# Fix — Persist job 'running' status when the worker claims it

**Type:** Fix
**Status:** verified
**Branch:** fix/worker-claim-persists-running-status

### The problem

Marketplace installs show the job stuck at **"Queued"** in the UI even while
Helm is actually installing — manually checking the cluster shows the chart
deployed and pods running, but the frontend never updates. Status jumps straight
from "queued" to "succeeded"/"failed", so progress is never surfaced.

Root cause is in the worker claim, not the UI or the status API:

- `backend/app/jobs/worker.py` → `claim_next_job()` executes
  `UPDATE installation_jobs SET status='running', started_at=...` and mutates the
  ORM row, but **never commits** the session (worker.py:42-61).
- The worker session only commits at the *end* of processing: `succeeded` after a
  successful `helm install --wait` (worker.py:141-144, up to 600s), or `failed`
  via `_fail_job` (worker.py:108-122).
- `get_installation_status` reads the row in a **separate** DB session, so it
  keeps seeing the last committed value — `queued` — for the entire duration of
  the Helm run.
- Because the claim is never committed, `started_at` is never persisted either
  (the live `installation_jobs` table shows `started_at = NULL` for every job),
  so the audit trail cannot show when a job started.

### The fix

Make `claim_next_job` commit the running transition immediately after a
successful atomic claim:

- After the conditional `UPDATE ... WHERE status='queued'` affects exactly one
  row (rowcount == 1), set the ORM row's `status`/`started_at` and `commit()` the
  session right away.
- The `rowcount == 0` path (job already claimed by another worker/cycle) must not
  commit or mutate.
- No other change: `_process_claimed_job` keeps committing `succeeded` on success;
  `_fail_job` still rolls back then writes `failed`. `requeue_running_jobs` (startup
  crash recovery) is unchanged and resets leftover `running` → `queued`.

Must not break: claim atomicity (only one claim succeeds), the existing
`test_worker.py` suite, terminal status transitions, or the requeue-on-startup
behavior.

### Build steps

**Step 1 — Commit the claim in `claim_next_job`.**
- [x] Done: `claim_next_job` commits the running transition; `test_claim_marks_running_and_started`
  updated (manual commit removed, fresh session asserts `running`/`started_at` immediately);
  focused `tests/test_worker.py` — 8 passed.

**Step 2 — Whole-suite verification.**
- [x] Done: full backend suite — **210 passed**.

### Verify

- `cd backend && .venv/bin/python3 -m pytest` (focused: `tests/test_worker.py`) — passed.
- Exact `Verify` command rerun at completion: `cd backend && .venv/bin/python3 -m pytest` (210 passed)
  then `cd k8s-ui && yarn verify` (next build clean).
- Live (Minikube deploy): start a Marketplace install and watch the install dialog
  — after submission it should move from **Queued** to **Running** ("Helm is
  installing the package.") within a poll cycle instead of staying on Queued while
  the chart deploys. On completion it lands on Succeeded/Failed. `started_at` is
  populated for the job row.

### Notes

- Additive, backend-only change; no frontend or manifest edits.
- The previous cert-manager install failures in the live DB are a separate chart
  issue (post-install `startupapicheck` Job) and out of scope here.