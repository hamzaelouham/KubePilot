# Feature 22d4 - Agent integrations

**Type:** Feature
**Build plan:** 22d4
**Branch:** `feature/agent-integrations`
**Status:** Verified

## Goal

Let administrators attach explicit, shared notification destinations to an
enabled or disabled Assistant agent through the existing `/assistant/agents`
management surface. Destinations use the already-connected Slack, Gmail, or
Microsoft Outlook integrations and the existing encrypted delivery queue, so a
future scheduled or event-triggered run can notify a bounded, reviewed target
without receiving provider credentials or arbitrary destinations from the
model. This slice includes an administrator-invoked test delivery; automatic
run and event triggers remain 22d5.

## In scope

- Add a persisted notification-destination association for a shared agent,
  supporting multiple destinations per agent and an enabled/disabled state.
- Allow only the existing supported providers: `slack`, `gmail`, and
  `outlook`. Reuse the existing Settings-managed connection and credential
  lifecycle; do not add another OAuth, token, or Settings navigation flow.
- Add provider-owned destination validation and normalization. Slack accepts
  the target format supported by its existing adapter; Gmail and Outlook accept
  a validated mailbox recipient. Store the normalized target encrypted and
  expose only a user-supplied label and safe destination hint after submission.
- Add an admin-only test-delivery action that queues a fixed KubePilot test
  message through the existing `IntegrationDeliveryJob` worker. Return the
  existing queued/status contract and show safe delivery progress without
  exposing message content, credentials, or the raw target.
- Provide a reusable server-side dispatch service keyed by agent and
  destination ID for 22d5. It must resolve the destination and current
  connected integration on the server, generate its own idempotency key, and
  call the existing encrypted, retrying delivery path.
- Preserve existing integration delivery statuses (`queued`, `running`,
  `succeeded`, `failed`, and `outcome_unknown`) and audit outcomes, adding only
  safe agent/destination source metadata where needed.
- Add loading, empty, invalid, disconnected, denied, provider failure,
  duplicate/idempotent, queued, retrying, succeeded, failed, and uncertain
  outcome states to the agent management UI.

## Out of scope

- New provider connectors, Slack/Gmail/Outlook OAuth flows, credential storage,
  provider scopes, or arbitrary Webhooks/Teams/GitHub destinations.
- Automatic notifications on agent completion, schedules, external events,
  background ownership, run history, or designated-owner permission checks;
  these belong to 22d5.
- An autonomous notification tool in the 22d3 foreground conversation. A
  notification is sent in this slice only through the explicit administrator
  test action; 22d5 will consume the dispatch service for configured triggers.
- Message-template builders, rich attachments, arbitrary HTML, file uploads,
  user-supplied provider API payloads, or delivery content persisted in audit
  records.
- Changes to Kubernetes/Helm tools, proposal approval semantics, agent model
  selection, skills, or capability permissions.

## Build loop

- Follow `workflow.stepReview: "feature"`: implement the small steps, then
  present one feature-level review packet.
- `checkpointCommits` is disabled; no checkpoint commit is offered.
- Work locally on `feature/agent-integrations`. `/complete` owns the final
  feature commit and merge approval.

## Build steps

- [x] **1. Add the server-authoritative destination model and API.** Extend the
  existing agent/integration seams with a normalized destination association
  linked to `AIAgent` and the existing `IntegrationConnection`. Add a stable
  UUID, agent foreign key, provider ID, label, encrypted normalized target,
  safe destination hint, uniqueness digest, enabled state, actor/timestamps,
  and the required migration. Add nested read/write/test-delivery endpoints
  behind the same reader/writer boundaries as agent management: reads use the
  existing Assistant read permission, while create/update/delete/test use the
  existing admin Settings-write boundary. Reject unsupported providers,
  invalid provider targets, disabled/missing agents, duplicate destinations,
  and disconnected integrations with stable safe error codes.

  **Done when:** backend tests prove admin CRUD and test-delivery access,
  non-admin denial, provider/target validation, encrypted persistence,
  uniqueness, disabled-destination behavior, disconnected-connection errors,
  and no raw target or credential in response/error/audit payloads.

- [x] **2. Reuse the durable delivery and audit path for agent notifications.**
  Add an `enqueue_agent_notification` service that resolves an agent-owned
  destination by ID, rechecks the current connected integration, decrypts the
  target only inside the backend boundary, and delegates to the existing
  `IntegrationDeliveryRequest`/worker path. Generate the idempotency key on the
  server from the request-scoped test invocation or future trigger identity;
  never accept it, the provider, or the destination string from the client.
  Preserve encrypted payloads, bounded retries, `outcome_unknown`, safe
  `destination_hint`, and existing delivery audit events. Associate safe agent
  source metadata with delivery status without storing notification content.

  **Done when:** service tests prove a connected destination queues exactly one
  delivery for a repeated idempotency key, a disconnected/revoked connection
  queues nothing, worker success/retry/failure/unknown states remain intact,
  and audit records contain provider/status/source IDs only.

- [x] **3. Add destination management and explicit test delivery to the Agent UI.**
  Extend the existing agent editor and its same-origin Next.js bridges with a
  Notifications section. Load safe supported-connection metadata and agent
  destinations, let an administrator add/edit/enable/disable/delete a labeled
  destination, and require replacement input instead of returning an existing
  raw target. Disable or explain actions when the provider is not connected;
  preserve unsaved-edit protection and existing agent CRUD behavior. Add a
  clearly explicit `Send test notification` action with a fixed server-owned
  test message, then render the returned delivery ID/status and refreshable
  queued/running/succeeded/failed/uncertain states using existing UI patterns.
  Keep viewer/operator surfaces read-only and never render provider tokens,
  encrypted values, raw delivery bodies, or untrusted provider data as markup.

  **Done when:** an admin can configure and test a connected Slack, Gmail, or
  Outlook destination; empty, loading, validation, denied, disconnected,
  backend-unavailable, duplicate, and delivery-error states are actionable and
  accessible; and the UI never accepts a client-selected provider/destination
  outside the server-owned destination record.

- [x] **4. Add regression coverage and complete the feature gate.** Extend
  backend integration, agent, delivery, and audit tests plus the frontend agent
  tests for destination contracts, forged provider/target/agent IDs,
  authorization, redaction, idempotency, connection revocation, safe delivery
  states, and test-action UI behavior. Run the declared
  `./scripts/verify-feature.sh`, recording focused tests, build result, and any
  environment limitation without weakening the gate.

  **Done when:** focused backend and frontend tests pass, the production build
  passes, the manual review path is documented, no new provider or schedule
  scope has leaked into the diff, and final Verify has no unwaived failure.

## Files / areas

- `backend/app/models/entities.py` and a new Alembic migration for the
  agent-destination association and safe delivery source metadata.
- `backend/app/api/v1/agents.py`, `backend/app/api/v1/agent_schemas.py`, and
  new agent-notification schemas/routes for server-authoritative CRUD and test
  delivery.
- `backend/app/services/agents.py`, `backend/app/services/integrations.py`,
  `backend/app/services/integration_delivery.py`, and a focused notification
  service for validation, destination resolution, idempotency, and dispatch.
- `backend/app/integrations/{base,slack,google,microsoft}.py` for provider-owned
  destination validation/send contracts; do not duplicate provider auth logic.
- `backend/app/jobs/integration_delivery_worker.py` and
  `backend/app/core/audit.py` for existing queue states and safe audit events.
- `k8s-ui/components/assistant/agents/editor.tsx` and `view.tsx`, the existing
  integration metadata/status helpers, and matching
  `k8s-ui/app/api/assistant/agents/...` bridges.
- `backend/tests/test_agents.py`, `backend/tests/test_integrations.py`,
  `backend/tests/test_integration_delivery.py`,
  `backend/tests/test_integration_adapters.py`, and frontend agent/Assistant
  tests.

## Data / contracts

- Destination writes accept only `{ provider_id, label, destination, enabled }`
  with bounded lengths. The server validates and normalizes the target through
  the selected provider adapter, encrypts it with the existing application
  encryption service, stores a server-side uniqueness digest, and returns only
  `{ id, provider_id, label, destination_hint, enabled, connection_status,
  updated_at }`. The raw `destination` is write-only after submission.
- Supported provider IDs are exactly `slack`, `gmail`, and `outlook`; the
  server ignores or rejects client attempts to use catalog-only providers or
  to substitute an integration connection.
- Notification routes resolve the authenticated actor from the signed session
  cookie and resolve agent, destination, connection, and credentials from the
  database. The browser never sends provider credentials, integration tokens,
  permissions, delivery payloads, or a replacement destination to the delivery
  worker.
- Test delivery uses a fixed server-owned event type such as
  `agent_notification_test` and a bounded plain-text body. It returns the
  existing delivery ID and queued status; provider delivery is asynchronous.
- Delivery uses the existing encrypted payload, destination hint, retry limits,
  safe error codes, and `outcome_unknown` distinction. Any source agent or
  destination ID added to delivery metadata is non-secret and excluded from
  message content/audit payloads.
- Destination deletion removes only the association. It must not disconnect
  the shared provider, delete credentials, cancel already queued deliveries, or
  erase delivery history; queued work re-resolves connection state when it is
  claimed and reports a safe failure if the connection is no longer usable.

## Testing

- Backend: test destination CRUD, provider adapter validation, encryption and
  redaction, admin-only mutations, read access, connection lifecycle changes,
  duplicate/idempotent test requests, queue/worker status transitions, safe
  audits, and no mutation of provider credentials.
- Frontend: extend agent tests for safe destination projections, write-only
  target fields, same-origin/session forwarding, validation/error states, and
  explicit test-delivery status rendering.
- Final gate: `./scripts/verify-feature.sh`.
- Observed final verification: `./scripts/verify-feature.sh` passed with 26
  focused backend tests, 27 Assistant/frontend tests, and the Turbopack
  production build including TypeScript, page generation, and route
  optimization. A follow-up status-refresh UI adjustment was made after that
  run and is covered by the focused TypeScript/build checks; the final gate is
  rerun before handoff.
- Manual review path: open `/assistant/agents` as an administrator, edit an
  existing agent, add a Slack, Gmail, or Outlook destination using an already
  connected provider, save it, and confirm only the label and safe hint remain
  visible. Use `Test`, confirm the returned delivery ID starts as `queued`, then
  use `Refresh status` to observe the backend-owned delivery state. Repeat as a
  viewer to confirm the destination list is read-only and mutation controls are
  absent. Live provider delivery still requires a configured connected provider;
  no browser harness or live provider evidence is claimed here.
- No repository Browser tests command is configured. Browser claims require
  direct evidence during `/check` or `/try`; do not claim visual or live
  provider delivery proof from unit tests or a production build.

## Notes for the AI

- The existing Settings Integrations page remains the only place to connect,
  authorize, test, or disconnect Slack/Gmail/Outlook. Agent configuration only
  selects an already-connected provider and stores its bounded target.
- Agent destinations are shared installation configuration, so agent writers
  use the current admin Settings-write boundary. Operators/viewers may inspect
  only the safe agent projection allowed by the existing agent read boundary.
- A notification is an external side effect. This slice makes only the
  administrator's explicit fixed test action queue a delivery; no model prompt,
  skill instruction, agent completion, schedule, or external event may trigger
  one until 22d5 defines that trigger and its actor recheck.
- Treat provider responses and destination labels as untrusted data. Render
  plain text only, bound all lengths, avoid raw HTML/Markdown execution, and
  never put notification bodies, tokens, instructions, or raw targets in audit
  context or browser state.
- Keep delivery uncertain outcomes visible and non-retriable unless the
  existing authenticated Settings delivery-retry path is used. Do not silently
  duplicate external sends.

## Open questions

None. This spec intentionally chooses shared admin-managed destinations and an
explicit test-delivery seam; 22d5 owns automatic notification triggers.
