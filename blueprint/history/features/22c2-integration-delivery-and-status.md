# Feature 22c2 - Integration delivery and status

**Type:** Feature

**Branch:** `feature/integration-delivery-and-status`

**Status:** verified

## Goal

Build the delivery layer on top of the completed 22c1 connection contracts. Trusted backend event producers must be able to enqueue bounded, idempotent notifications for connected Slack, Gmail, and Microsoft Outlook accounts; a durable worker must deliver them with safe provider error handling, observable status/history, and administrator retry controls without exposing tokens, message payloads, or provider response bodies.

## Design reference

Extend the protected `/settings/integrations` surface and its supplied reference direction: [settings-providers-integrations.png](../reference/settings-providers-integrations.png). Keep delivery history compact and operational: status badges, provider, event type, redacted destination hint, attempts, timestamps, safe error code, refresh, and retry actions. Do not add a general notification center, workflow builder, destination-management form, or message composer in this feature.

## In scope

- Define a server-only `IntegrationDeliveryRequest` envelope for trusted backend event producers. It carries a stable idempotency key, supported provider, provider-specific destination reference, event type, subject, plain-text body, and optional initiating actor metadata.
- Persist an encrypted delivery job for each accepted request, retaining only safe provider/status/event metadata in queryable columns. Enforce one application-level delivery record per idempotency key and return the existing record on duplicate enqueue without making another provider call.
- Extend the 22c1 Slack, Gmail, and Outlook adapters with a normalized send operation. Slack sends plain text to a channel reference; Gmail and Outlook send plain-text email to a validated recipient reference. Tokens are decrypted and refreshed only inside the backend adapter/service boundary.
- Run delivery jobs through the existing FastAPI background worker lifecycle and settings (`KUBEPILOT_WORKER_ENABLED`, `KUBEPILOT_WORKER_POLL_SECONDS`), with atomic claiming, restart requeue, bounded automatic retries, and terminal status transitions.
- Classify provider failures into safe stable codes. Retry only known transient failures such as rate limits, upstream 5xx responses, and pre-response transport failures; do not automatically retry authorization, validation, unsupported-scope, or ambiguous outcome failures that could duplicate an external send.
- Add protected Settings APIs for paginated delivery status/history and administrator-requested retry of a failed delivery. The enqueue contract is backend-only; browsers cannot submit arbitrary provider destinations or message content.
- Add delivery audit events for queue, start, retry scheduling, success, failure, outcome-unknown, and manual retry. Audit context contains only provider, delivery ID, status, attempt count, and normalized error code; never message text, recipients, channels, tokens, or provider bodies.
- Add a minimal delivery-history panel to Settings Integrations with loading, empty, denied, unavailable, error, retrying, succeeded, failed, and outcome-unknown treatments. Keep Teams, GitHub, and Webhooks catalog-only.

## Out of scope

- New provider connections, OAuth flows, credentials, scopes, or connection ownership; consume only the normalized Slack/Gmail/Outlook contracts from archived 22c1.
- A general workflow builder, configurable AI agent behavior, Kubernetes event-rule engine, automatic alert producers, or delivery triggers. Future producers call the backend enqueue service explicitly.
- Destination/channel configuration, address books, templates, rich HTML/attachments, provider-specific message editing, or a browser message composer. Destinations are supplied by trusted event producers per request and are not persisted as reusable Settings configuration.
- Exactly-once external delivery. Idempotency prevents duplicate local queueing; provider calls without a provider-native idempotency key remain at-least-once, and ambiguous outcomes become terminal `outcome_unknown` until an administrator decides whether to retry.
- Arbitrary providers, API-key-only connector flows, webhooks, Teams, GitHub, direct provider calls from Next.js, or exposing a public enqueue endpoint.
- New browser-test infrastructure. Use the configured backend tests, frontend lint/build, migration SQL validation, and available manual evidence only.

## Build loop

Configuration uses feature-level review (`workflow.stepReview: "feature"`) with checkpoint commits disabled. Keep the migration, worker, APIs, and Settings history panel buildable after each step. `/complete` owns the final feature commit and plan archival. Feature 22d must consume only the stable enqueue and delivery-status contracts established here.

## Build steps

- [x] **1. Define the delivery event contract and durable job storage.** Add a typed, backend-only `IntegrationDeliveryRequest` plus an `IntegrationDeliveryJob` SQLAlchemy model and Alembic migration. Store provider, connection reference, idempotency key, event type, redacted destination hint, encrypted destination/subject/body envelope, lifecycle status, attempt counters, retry timing, safe error code, actor metadata, and timestamps. Add unique and query indexes for idempotency, status, provider, and due work.

  **Done when:** supported providers and required envelope fields are validated before persistence; unknown/catalog-only providers, blank or oversized content, invalid destinations, duplicate idempotency keys, and disconnected connections fail safely; duplicate enqueue returns the original safe job metadata; plaintext message content is absent from queryable API fields, audit rows, and logs; migration SQL passes.

- [x] **2. Extend provider adapters with normalized delivery sends.** Add a narrow `send`/delivery result contract to the 22c1 adapter protocol and implement Slack `chat.postMessage`, Gmail `users.messages.send`, and Outlook Graph `sendMail` using plain-text payloads and provider-owned destination validation. Preserve backend-only token refresh and normalize response, rate-limit, transport, authentication, and ambiguous-outcome errors without leaking upstream bodies.

  **Done when:** each adapter can be mocked without live credentials; successful sends return only a normalized optional external receipt; 429/5xx and known pre-response transient errors are retryable, authorization/validation errors are terminal, and timeouts or uncertain responses are marked outcome-unknown; no adapter logs or returns tokens, message bodies, recipient addresses, channel IDs, or raw provider payloads.

- [x] **3. Add idempotent queue processing, retries, status transitions, and audit.** Extend the existing worker cycle with atomic delivery-job claiming, startup requeue for interrupted work, provider dispatch, safe success/failure persistence, and audit events. Use a fixed bounded policy of at most three automatic attempts with bounded backoff (first retry after one minute, second after five minutes); manual retry starts a fresh bounded attempt window only after an administrator explicitly retries a terminal failed job.

  **Done when:** concurrent workers cannot claim the same queued job; duplicate event enqueue never creates a second provider call; queued/running/succeeded/failed/outcome-unknown transitions and timestamps are durable; only retryable known failures return to queued; terminal failures never loop; restart recovery requeues interrupted work safely; audit context is redacted and records queue/start/retry/success/failure/unknown outcomes.

- [x] **4. Add protected delivery status and retry APIs.** Add typed FastAPI routes under `/api/v1/settings/integrations/deliveries` for paginated history/detail and `POST /{delivery_id}/retry`. Require `SETTINGS_READ` for observation and `SETTINGS_WRITE` for manual retry, use the existing authenticated actor boundary, and return stable error shapes. Do not expose a queue/enqueue route to browsers.

  **Done when:** admins can filter or page safe delivery metadata by provider/status/time, retry only eligible failed jobs, and observe normalized status/error results; viewers/operators receive the existing Settings permission response; missing, running, succeeded, or outcome-unknown retry requests do not mutate jobs; responses contain no encrypted payload, message, destination, token, or provider body.

- [x] **5. Add minimal Settings delivery history UI and same-origin bridges.** Add Next.js same-origin proxies for delivery history/detail/retry and extend `SettingsIntegrationsView` with a compact delivery-history section. Keep provider connection cards unchanged except for a link/summary to delivery activity; use existing Settings audit and status styling.

  **Done when:** the UI handles loading, empty, unauthorized, backend-unavailable, malformed, unexpected-error, queued/running, succeeded, failed, and outcome-unknown states; it shows only safe provider/event/status/attempt/time/error metadata; Retry is available only for eligible failed rows, announces results accessibly, and refreshes server state; no client route receives a token, message payload, raw destination, or provider response.

- [x] **6. Add focused delivery security, worker, provider, API, migration, and regression tests.** Cover contract validation, encrypted payload persistence, idempotency, connection scoping, adapter send/error mapping, atomic claims, retry timing/limits, restart recovery, outcome-unknown handling, audit redaction, permission boundaries, retry eligibility, same-origin proxy behavior, and UI build/lint.

  **Done when:** mocked provider tests pass without live credentials; duplicate and concurrent enqueue paths perform at most one provider call; transient and terminal errors produce the documented statuses; unauthorized or malformed requests perform no mutation; `./scripts/verify-feature.sh`, `yarn lint`, migration SQL validation, and `git diff --check` pass; unavailable browser evidence is recorded rather than claimed.

## Files / areas

- `backend/app/models/entities.py` and `backend/alembic/versions/` - durable integration delivery job schema, encrypted payload reference, status/retry fields, constraints, and indexes.
- `backend/app/integrations/base.py`, `slack.py`, `google.py`, and `microsoft.py` - normalized send contract, provider payloads, destination validation, and safe error classification.
- `backend/app/services/integration_delivery.py` - trusted event envelope validation, encryption, idempotent enqueue, safe status projection, manual retry, and connection/token boundary.
- `backend/app/jobs/worker.py` or a focused delivery worker module registered by `backend/app/main.py` - atomic claim, dispatch, retry/backoff, restart recovery, and terminal audit outcomes.
- `backend/app/api/v1/integrations.py` and `integration_schemas.py` - protected delivery history/detail/retry routes and safe response models.
- `backend/app/core/audit.py` and Settings audit categorization - `integration.delivery.*` audit actions with redacted context.
- `backend/tests/test_integration_delivery.py`, `test_integration_adapters.py`, and related Settings tests - contract, provider, worker, API, permission, and redaction coverage.
- `k8s-ui/app/api/settings/integrations/deliveries/` - same-origin history/detail/retry proxies.
- `k8s-ui/components/settings-integrations-view.tsx` - delivery history/status/retry panel with accessible state feedback.

## Data / contracts

### IntegrationDeliveryRequest

- Backend-only immutable request with `idempotency_key`, provider ID (`slack`, `gmail`, or `outlook`), `event_type`, `destination`, `subject`, `body`, and optional initiating actor UUID.
- `idempotency_key` is producer-generated, stable for the intended notification, and unique across the application. The queue service returns the existing safe job projection for a repeated key without dispatching again.
- `event_type` is a bounded opaque identifier for audit/filtering. `body` and optional `subject` are plain text only and are bounded before encryption. The request may contain provider-specific destinations, but browser clients cannot construct or submit it.

### IntegrationDeliveryJob

- One application-level durable job per idempotency key, linked to the 22c1 `IntegrationConnection` and retaining the provider ID, event type, safe redacted destination hint, encrypted destination/subject/body envelope, status, attempt count, max attempts, next-attempt timestamp, safe last-error code, actor reference, and lifecycle timestamps.
- Status values are `queued`, `running`, `succeeded`, `failed`, and `outcome_unknown`. `queued` with a future `next_attempt_at` represents an automatic retry wait; no separate retrying state is exposed.
- Automatic retry policy is fixed at three total attempts with one-minute then five-minute backoff. Manual retry is an administrator action on a terminal `failed` job and resets a new bounded attempt window; it is never available for `outcome_unknown` without a deliberate future policy change.
- The encrypted envelope is decrypted only by the worker/service immediately before provider dispatch. Safe list/detail responses never expose its fields or raw destination. Provider response bodies and raw exception text are discarded after error normalization.
- A worker crash or restart requeues `running` jobs with no completed provider result. A provider timeout or ambiguous transport result is terminal `outcome_unknown` because the external side effect may already have occurred.

### Provider delivery adapter

- The adapter protocol adds `send(access_token, destination, subject, body)` and returns a normalized `DeliveryReceipt` with only an optional provider receipt ID and safe result metadata.
- Slack accepts a provider channel reference and posts plain text through `chat.postMessage`; Gmail accepts one validated recipient and sends a plain-text RFC 822 message through `users.messages.send`; Outlook accepts one validated recipient and sends a plain-text Graph message through `/me/sendMail`.
- Adapter errors carry only stable application codes plus internal retryability/outcome classification. The API, audit row, log, and UI receive normalized codes such as `integration_provider_unavailable`, `integration_rate_limited`, `integration_connection_invalid`, `integration_delivery_rejected`, `integration_delivery_outcome_unknown`, and `integration_delivery_expired`.
- Token refresh stays behind the existing encrypted connection service. A terminal authentication/refresh failure marks the connection through the existing safe connection status path; transient delivery failures do not unnecessarily disconnect a healthy connection.

### API shapes and authorization

- `GET /api/v1/settings/integrations/deliveries` returns paginated safe items with delivery ID, provider, event type, redacted destination hint, status, attempt count, max attempts, next-attempt time, safe last-error code, and created/started/completed timestamps. It accepts provider, status, and date/page filters bounded by the existing Settings API conventions.
- `GET /api/v1/settings/integrations/deliveries/{delivery_id}` returns the same safe projection for one job.
- `POST /api/v1/settings/integrations/deliveries/{delivery_id}/retry` returns the requeued safe projection only for a terminal `failed` job; it records the authenticated administrator as the retry actor.
- Read routes require `Permission.SETTINGS_READ`; retry requires `Permission.SETTINGS_WRITE`. The enqueue service is not routed through Next.js or exposed as a browser API.
- Errors use the existing `{ "code": string, "message": string }` shape. Stable lifecycle errors include `integration_delivery_not_found`, `integration_delivery_not_retryable`, `integration_delivery_duplicate`, `integration_delivery_invalid`, `integration_delivery_not_connected`, `integration_delivery_outcome_unknown`, `integration_provider_unavailable`, and `integration_rate_limited`.

### Audit and privacy

- Audit actions use `integration.delivery.` prefixes: `queued`, `started`, `retry_scheduled`, `succeeded`, `failed`, `outcome_unknown`, and `retry_requested`.
- Audit context is limited to provider, delivery ID, safe status, attempt count, and normalized error code. It never contains idempotency keys, event payloads, subjects, message bodies, email addresses, channel IDs, tokens, raw exceptions, or provider response bodies.
- Delivery history is operational metadata, not a message archive. The UI and APIs do not return message content or reusable destination configuration.

## Testing

- `./scripts/verify-feature.sh` - required local feature gate; backend focused tests run when backend application/test files change, followed by the Assistant suite and frontend production build.
- `cd backend && python3 -m pytest` - full backend regression suite when needed for final completion or CI.
- `cd backend && PYTHONPATH=. alembic upgrade head --sql` - migration SQL validation.
- `cd k8s-ui && yarn lint` - frontend lint; existing unrelated warnings remain non-blocking unless new findings appear.
- `git diff --check` - whitespace and patch sanity.
- Planning baseline: `./scripts/verify-feature.sh` passed on the clean master baseline; backend pytest was correctly skipped because no backend changes were present, the Assistant suite passed 13 tests, and the Turbopack build passed with 44 generated routes.
- Feature evidence: `./scripts/verify-feature.sh` passed with 15 focused backend tests, 13 Assistant tests, and a successful Turbopack production build generating 45 pages/routes. `yarn lint` passed with 0 errors and 13 pre-existing warnings; migration SQL validation passed for the delivery-job migration; `git diff --check` passed.
- No browser test command is configured. Manual browser evidence is optional under `verification.uiEvidence: "when-available"`; do not claim external delivery without mocked provider evidence or safe rendered evidence.

## Notes for the AI

- Treat 22c1 connection rows, encrypted token material, and provider adapters as the only credential boundary. Do not copy or expose token fields in delivery jobs, APIs, logs, audits, or client bundles.
- Treat message content and destinations as untrusted event data. Validate length, plain-text encoding, provider-specific destination shape, and supported provider before encryption or queueing; never interpolate content into shell commands or HTML.
- Preserve at-least-once semantics and make ambiguous external outcomes explicit. Never silently retry a timeout when the provider may have accepted the message.
- Use the existing worker process and poll settings. Do not add Celery, RQ, a second queue service, or a new deployment unless implementation evidence proves the existing worker cannot safely process delivery jobs.
- Keep Teams, GitHub, Webhooks, and AI agent workflows out of this feature. 22d will define agent behavior under `/assistant` separately.

## Open questions

- Confirm with deployment owners that the existing worker process is enabled in production (`KUBEPILOT_WORKER_ENABLED=true`) for queued delivery. The implementation can be tested with the existing worker disabled and jobs left queued, but live delivery requires the deployment prerequisite.
