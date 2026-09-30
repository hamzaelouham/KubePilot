# Feature 22d5 - Schedules and events

**Type:** Feature
**Build plan:** 22d5
**Branch:** `feature/agent-schedules-and-events`
**Status:** Verified

## Goal

Allow an administrator to configure paused or active automated triggers for an AI agent, including a simple daily schedule such as `0 12 * * *` and Kubernetes-event matching. Each unattended run must execute only the agent's permitted investigation and configured notification behavior, recheck the designated owner's live permissions at run time, and appear in the existing Background Jobs experience with status, timestamps, bounded logs, and safe failure details.

Operations that change Kubernetes or Helm resources remain human-approved work. An administrator or operator uses the existing authenticated Assistant flow to inspect and approve those actions manually; a scheduled or event-triggered run must never approve or execute them on its own.

## In scope

- Admin-only automation configuration for an existing enabled agent:
  - create, edit, pause/resume, and remove triggers;
  - select a designated owner whose live authorization is checked for every run;
  - select already-configured notification destinations;
  - validate the trigger before saving and record configuration changes in the audit stream.
- Two v1 trigger kinds:
  - `schedule`, using standard five-field cron (`minute hour day-of-month month day-of-week`) with no seconds, macros, or nonstandard extensions;
  - `kubernetes_event`, matching the existing Kubernetes event projection with optional namespace, kind, name, type, and reason filters.
- A required IANA timezone for scheduled triggers, with the project default timezone used only when the existing application settings explicitly provide one. Store the timezone with the trigger so daylight-saving changes are evaluated consistently.
- A scheduler that evaluates due schedules and newly observed matching Kubernetes events, creates at most one run for each schedule occurrence or event identity, and does not backfill an unbounded backlog after downtime.
- A persisted agent background run/job lifecycle using the existing Background Jobs conventions: `queued`, `running`, `succeeded`, `failed`, and `cancelled`; created, started, and completed timestamps; safe result/error information; bounded log output; and an inspectable run identifier.
- Worker execution that rechecks, immediately before execution:
  - designated owner exists, is active, and still has the required permissions for the selected cluster/scope;
  - the agent remains enabled and its assigned skills/tools/model configuration are still valid;
  - referenced cluster and notification integrations remain available and enabled.
- Unattended execution limited to read-only workload investigation and sending notifications through the existing encrypted integration-delivery service. Destinations must be configured before the run and cannot be supplied dynamically by the agent.
- A safe `approval_required`/`permission_denied`/`configuration_invalid` result outcome for runs that cannot proceed or discover work requiring a mutation. The run must explain the next manual Assistant action without exposing protected prompts, tool arguments, credentials, or provider payloads.
- Background Jobs list/detail/log integration reusing the existing Helm job presentation and same-origin API patterns. Administrators can distinguish queued, running, successful, failed, cancelled, paused-trigger, and approval-required states without opening raw provider data.
- Admin-configurable global run retention in the agent automation area: terminal agent runs and their bounded logs are retained for a configurable number of days, defaulting to 30, with a validation range of 1–365 days. Cleanup must never delete active runs or audit records; retention changes are audited.
- Accessible agent automation UI states for loading, empty, invalid cron/timezone, missing owner, missing permissions, disabled agent/destination, paused trigger, queued/running/succeeded/failed/cancelled run, approval required, and retention validation errors.
- Focused backend and frontend regression coverage plus the repository migration SQL check.

## Out of scope

- Public webhooks, external event buses, arbitrary external event types, or user-defined code execution. Kubernetes-event matching is the only event trigger in this slice.
- Automatic approval, execution, or retry of Kubernetes/Helm mutations. Manual approval continues to use the existing Assistant proposal/action flow and the caller's current authenticated permissions.
- Creating notification providers, credentials, destinations, or agent capabilities from a trigger run.
- Replacing the existing Helm installation worker, integration-delivery worker, Assistant model/tool system, or Background Jobs page with a new parallel framework.
- Per-trigger or per-agent retention policies, archival storage, exported logs, browser-test harness setup, or deployment/CI changes.
- Catch-up of every missed cron occurrence after a scheduler outage; one current due occurrence may be coalesced, with deduplication preserving at-most-once enqueueing.

## Build loop

Implement the steps below on `feature/agent-schedules-and-events`. Keep each step small, run its focused tests, and stop for review after the complete feature packet because `workflow.stepReview` is configured to review at feature scope. Do not commit, merge, push, or deploy as part of this feature spec or implementation pass.

## Build steps

1. [x] **Persist automation configuration and run contracts**

   Add the migration, ORM/schema contracts, validation, RBAC checks, audit events, and API behavior for trigger configuration, designated owners, global retention, and agent run records. Define indexes/constraints for enabled trigger lookup and unique schedule-occurrence/event deduplication. Preserve safe error responses and avoid storing secrets or raw model/tool payloads.

2. [x] **Implement trigger evaluation and guarded enqueueing**

   Add the scheduler path for five-field cron schedules and Kubernetes-event matching. Normalize timezone-aware occurrences, coalesce missed work, deduplicate event identities, and enqueue background runs atomically. Paused/invalid triggers must not enqueue work. Keep trigger evaluation bounded and ensure a trigger cannot create overlapping duplicate runs for the same occurrence/event.

3. [x] **Implement guarded agent-run execution**

   Add the worker claim/transition lifecycle using the existing background-job conventions. Recheck the designated owner's active status and permissions, agent configuration, cluster scope, model/tool availability, and destinations after claiming and before execution. Run only read-only investigation plus configured notification dispatch through the existing notification service; record redacted bounded logs, safe result/error codes, audit events, and terminal timestamps. Surface approval-required outcomes instead of invoking mutation tools.

4. [x] **Integrate admin configuration and Background Jobs UI**

   Extend the agent management UI with trigger creation/edit/pause/resume/delete and retention controls. Extend the Background Jobs list/detail/log flow to show agent runs alongside Helm jobs, including trigger, owner, result, retry/attempt information if present, and safe logs. Reuse existing loading, empty, error, status, dialog, permission, and same-origin API patterns; keep controls keyboard accessible and announce status changes appropriately.

5. [x] **Verify retention and regression behavior**

   Add cleanup for terminal runs older than the configured retention, test migration SQL and retention bounds, cover scheduler/worker/API/UI edge cases, run the focused Verify command, and review the final diff for authorization, deduplication, redaction, and query-count regressions.

## Files / areas

- `backend/app/models/entities.py` and the next Alembic migration: automation trigger, agent-run, retention, indexes, and relationships.
- `backend/app/api/v1/assistant.py` and the existing agent/marketplace API modules: trigger, retention, run-history, and background-job contracts.
- `backend/app/core/rbac.py`, `backend/app/core/audit.py`, and agent notification services: admin configuration authorization, per-run owner rechecks, safe audit records, and notification reuse.
- `backend/app/jobs/worker.py` plus a focused scheduler/agent-run worker module if separation keeps the Helm worker maintainable: due evaluation, atomic claims, lifecycle, retention cleanup, and bounded logging.
- Existing backend Assistant, agent notification, worker, migration, RBAC, and API tests.
- `k8s-ui/components/assistant/agents/*`, agent management routes, and `k8s-ui/components/background-jobs-view.tsx` / `background-job-dialog.tsx`: trigger/retention controls and run inspection.
- Existing Next same-origin API routes for Assistant/background jobs and focused Assistant/frontend tests.

Prefer extending existing background-job and notification abstractions over introducing a second status or log contract. Exact module names may be adjusted after the current repository APIs are inspected during implementation.

## Data / contracts

### Automation trigger

Store an automation trigger with at least:

- stable ID, agent ID, trigger kind, enabled/paused state, designated owner user ID, creator/updater IDs, and timestamps;
- for schedules: validated five-field cron expression and IANA timezone;
- for Kubernetes events: optional namespace, kind, name, type, and reason matchers;
- configured notification destination IDs, limited to destinations already owned/configured for the agent;
- last evaluation/enqueue metadata sufficient for observability without using it as the only deduplication guarantee.

Configuration writes require the existing administrator settings permission. A trigger cannot be enabled without an active owner, valid trigger definition, enabled agent, and valid referenced destinations.

### Agent background run

Store at least:

- stable run/job ID, trigger ID, agent ID, designated owner ID, selected cluster/scope, trigger kind, scheduled occurrence or event identity, and a unique deduplication key;
- `queued | running | succeeded | failed | cancelled` status, attempt count if the worker framework exposes it, result code, safe error message, created/started/completed timestamps, and bounded redacted log output;
- enough display metadata for the Background Jobs list/detail view without persisting prompts, model context, raw tool arguments/results, tokens, credentials, or provider response bodies.

Use a database uniqueness constraint or equivalent atomic insert for the deduplication key. A worker crash must leave the same recoverable/requeue behavior as existing background jobs, and a run must be revalidated after it is claimed so permissions revoked after enqueueing take effect.

### Execution and approval boundary

The scheduled execution context is server-created and cannot be altered by agent instructions. It may inspect configured cluster resources and enqueue notifications through `enqueue_agent_notification(...)`. It may not mutate Kubernetes/Helm resources, approve proposals, change agent scope/capabilities, create credentials/destinations, or route a notification to an unconfigured destination. When a requested conclusion requires a mutation, record an approval-required result with a link/instruction to start the existing Assistant flow manually.

Manual Assistant execution remains the authenticated admin/operator's responsibility and is not represented as an unattended scheduled run.

### Retention

Persist one admin-controlled global `retention_days` setting for agent runs. Default to 30; accept only integers from 1 through 365. A scheduled cleanup removes terminal run rows and their bounded logs after the cutoff, leaves queued/running records untouched, and never removes audit events. The API and UI must return a stable validation error for out-of-range values.

## Testing

- Backend unit/API tests cover cron and timezone validation, due-occurrence coalescing, Kubernetes-event matching, event/schedule deduplication, paused/invalid triggers, owner permission/active-state rechecks, mutation-tool refusal, configured notification dispatch, safe errors, audit records, status/log transitions, worker recovery, retention bounds, and cleanup.
- Backend tests assert that listing triggers/runs and resolving owner/destination status do not introduce an avoidable per-row query pattern; use batched/preloaded lookups where the existing data model requires connection checks.
- Frontend Assistant/agent tests cover creating/editing/pausing/resuming triggers, validation and permission states, retention controls, and rendering approval-required/failed/successful runs with safe status text.
- Background Jobs tests cover agent runs appearing beside Helm jobs, detail/log loading, status labels, empty/loading/error states, and no raw secret/provider payload rendering.
- Run the repository migration SQL check and the focused `./scripts/verify-feature.sh` after implementation. The planning preflight already passed the current Assistant suite (27 tests) and Next production build; this is baseline evidence only and does not replace feature-specific tests.
- Browser testing is not configured and is out of scope for this feature.

## Notes for the AI

- Keep unattended execution investigation-only. The user's example—daily at noon, check workload health, and notify Slack—is the reference happy path.
- Use the existing encrypted integration-delivery path for Slack and other configured destinations; do not decrypt or expose credentials in API responses, logs, or UI.
- Follow the existing Helm Background Jobs lifecycle and presentation so operators have one place to inspect queue state, timestamps, failures, and logs.
- Recheck live authorization at run time rather than trusting the permissions held when the trigger was configured or enqueued.
- Prefer simple, explicit contracts over a general workflow engine. Five-field cron plus Kubernetes events is sufficient for this slice.
- Preserve the existing 22d3/22d4 agent and notification behavior and avoid taking scope from 22d6.
