# Feature 22c1 - Integration connection lifecycle

**Type:** Feature

**Branch:** `feature/integration-connection-lifecycle`

**Status:** verified

**Archived:** 2026-09-29

## Goal

Replace the local preview connection state in the Settings Integrations catalog with backend-authoritative connection lifecycle support for Slack, Gmail, and Microsoft Outlook. Administrators must be able to configure provider application credentials through the existing credential store, start a scoped OAuth connection, see safe connection status, test an established connection, and disconnect it without exposing secrets or claiming that delivery is implemented.

## Design reference

Reuse the shipped protected `/settings/integrations` catalog and its supplied KubePilot reference direction: [settings-providers-integrations.png](../reference/settings-providers-integrations.png). Preserve the calm operational shell, connected/available grouping, compact status treatment, responsive cards, and explicit security messaging. This feature changes the cards from local preview state to real server-backed connection state; delivery controls remain deferred to 22c2.

## In scope

- Add a backend-authoritative integration connection registry for the initial supported providers: Slack, Gmail, and Microsoft Outlook through their provider APIs.
- Register the provider application credentials needed for OAuth in the existing `CredentialDefinition` registry so administrators manage them through Settings Credentials; never accept arbitrary credential keys.
- Add one application-level connection per supported provider, with safe external identity metadata, granted-scope metadata, lifecycle status, timestamps, and server-only encrypted token material.
- Add one-time, expiring, actor-bound OAuth authorization state so callbacks cannot be replayed, forged, or reassigned to another administrator.
- Add explicit provider contracts and adapters for authorization URL creation, callback exchange, identity normalization, token refresh/revocation where supported, and connection testing.
- Add protected API routes to list connection metadata, begin authorization, complete callbacks, test a connection, and disconnect a connection. Return only safe metadata and normalized error codes.
- Reuse the existing `SETTINGS_READ` and `SETTINGS_WRITE` permission boundaries and the existing same-origin Next.js proxy pattern; Settings mutations remain administrator-only through current RBAC.
- Add audit events for authorization start, successful connection, failed authorization, connection test result, and disconnect. Audit context must contain only provider/status/error metadata and never tokens, codes, state values, raw callback URLs, or provider response bodies.
- Replace the 22b local preview state for the supported providers with server state and real loading, not-configured, authorization-pending, connected, revoked/expired, test-failed, denied, backend-unavailable, and unexpected-error treatments.
- Keep Microsoft Teams, GitHub, and Webhooks visible as catalog-only entries with no connect or external-service behavior until a later connector contract is approved.

## Out of scope

- Notification or automation event producers, destination/channel configuration, message templates, delivery jobs, retry policy, idempotency, delivery history, or delivery UI; these belong to 22c2.
- A general workflow builder or configurable AI agent behavior; agent workflows remain under `/assistant` in 22d.
- Per-user or multi-tenant connection ownership. Connections are application-level Settings resources, and the initiating administrator is retained only as audit metadata.
- Returning, copying, logging, or rendering OAuth access tokens, refresh tokens, client secrets, authorization codes, raw state values, or arbitrary provider payloads.
- Arbitrary credential identifiers, browser-side provider SDKs, direct provider calls from Next.js, or trusting browser role claims.
- Teams, GitHub, Webhooks, arbitrary integrations, API-key-only connector flows, or generic Kubernetes Secret management.
- New browser-test infrastructure. Use the existing backend test runner and production build; manual browser evidence remains optional under project configuration.

## Build loop

Configuration uses feature-level review (`workflow.stepReview: "feature"`) with checkpoint commits disabled. Keep the backend migration, API, and Settings UI buildable after each step. `/complete` owns the final feature commit and plan archival. Feature 22c2 must consume only the normalized connection and status contracts established here.

## Build steps

- [x] **1. Define the connection domain and encrypted lifecycle storage.** Add focused SQLAlchemy models and an Alembic migration for one application-level connection per provider plus one-time OAuth state records. Register Slack, Google/Gmail, and Microsoft/Outlook application credential definitions in the existing Settings credential service, and encrypt all token material with the existing `CredentialEncryption` boundary.

  **Done when:** the schema enforces a unique supported provider connection and one-time OAuth state records have an actor, provider, state digest, expiry, consumed timestamp, and safe indexes; tokens are never stored in plaintext; unknown provider/credential keys are rejected; migration SQL passes; existing credential tests still pass.

- [x] **2. Add explicit provider contracts and initial adapters.** Create a narrow integration adapter protocol and registry for Slack, Gmail, and Microsoft Outlook covering authorization URL creation, callback exchange, normalized identity/scopes, connection testing, refresh/revocation where supported, and safe provider error translation. Read application credentials only on the backend and keep provider-specific scopes inside adapters rather than accepting scopes from the browser.

  **Done when:** each supported provider has a deterministic adapter seam that can be mocked in tests; Teams, GitHub, Webhooks, and unknown providers resolve to a safe unsupported error; adapters do not log or return secret material; provider failures normalize to stable application error codes without leaking upstream response bodies.

- [x] **3. Implement secure OAuth initiation and callback handling.** Add authorization-start and callback endpoints that create a cryptographically random, hashed, short-lived state bound to the authenticated administrator and provider, validate the exact callback state once, exchange the code server-side, normalize the external identity/scopes, and persist the connection atomically. Reject expired, consumed, mismatched, missing-credential, denied-scope, provider-error, and replayed callbacks without changing an existing valid connection.

  **Done when:** a callback cannot succeed without a matching unexpired state and provider; state reuse, actor mismatch, and provider mismatch are rejected; callback failures produce safe status/error results and audit records; successful callbacks persist only encrypted token material and safe identity/scope metadata; no OAuth code, state, token, or raw provider response reaches a browser response, audit row, or log.

- [x] **4. Add connection status, test, disconnect, and audit APIs.** Extend the FastAPI settings boundary with typed routes under `/api/v1/settings/integrations` for safe listing, authorization start/callback, test, and disconnect. Enforce existing Settings permissions, use stable JSON error shapes, refresh tokens only inside the adapter boundary, revoke/clear credentials on disconnect, and add `integration.*` audit classification to the Settings audit view.

  **Done when:** admins can observe provider, status, safe account label, granted scopes, last test time, and safe last-error code; non-admins receive the existing permission response; test and disconnect mutations are actor-audited; repeated disconnect is idempotent; credential values and external response bodies are absent from every response and audit context.

- [x] **5. Replace the catalog preview state with real connection UI and same-origin bridges.** Add Next.js route handlers that forward only the signed session cookie and required callback query parameters to FastAPI. Update `SettingsIntegrationsView` so supported cards start from server data, Connect begins the authorization flow, connected cards expose Test and Disconnect actions, and catalog-only providers remain clearly unavailable. Preserve loading, empty/not-configured, denied, backend-unavailable, callback success/failure, and unexpected-error feedback with accessible status announcements.

  **Done when:** `/settings/integrations` never invents connected state after refresh; no client component receives a token or client secret; Connect, Test, and Disconnect surface the normalized backend result; unsupported catalog entries cannot call connector APIs; focusable controls have labels and status changes are announced without exposing provider payloads.

- [x] **6. Add focused security, contract, migration, and regression tests.** Cover provider registry validation, permission boundaries, credential registration, encrypted persistence, OAuth state expiry/consumption/actor binding, callback replay and failure paths, normalized provider errors, safe response/audit redaction, test/disconnect behavior, and the Next.js proxy contract. Run the project Verify command, backend focused tests selected by the feature gate, frontend lint/build, migration SQL validation, and diff checks.

  **Done when:** the new backend test file(s) pass with mocked provider adapters and no live provider credentials; unauthorized and malformed flows perform no connection mutation; `./scripts/verify-feature.sh`, `yarn lint`, and `git diff --check` pass in the verification environment; unavailable browser evidence is recorded rather than claimed.

## Files / areas

- `backend/app/models/entities.py` and `backend/alembic/versions/` - connection and OAuth-state persistence with constraints and indexes.
- `backend/app/services/application_settings.py` - registered integration application credentials and shared encrypted credential access.
- `backend/app/services/credential_encryption.py` - server-only encryption boundary; do not weaken or duplicate it.
- `backend/app/integrations/` - new provider protocol, registry, normalized result/error types, and Slack/Gmail/Outlook adapters.
- `backend/app/api/v1/settings.py` or a focused settings integrations router registered from `backend/app/api/v1/routes.py` - typed connection lifecycle endpoints.
- `backend/app/api/v1/settings_schemas.py` - safe request/response models and normalized error contracts.
- `backend/app/core/audit.py` and Settings audit categorization - integration lifecycle events and safe context.
- `backend/app/core/rbac.py` and `backend/app/core/dependencies.py` - existing Settings authorization and authenticated actor boundaries.
- `k8s-ui/app/api/settings/integrations/` - same-origin list, authorize, callback, test, and disconnect proxies.
- `k8s-ui/components/settings-integrations-view.tsx` - server-backed cards, supported-provider actions, and accessible state feedback.
- `backend/tests/test_integration_connections.py` and related existing Settings tests - focused lifecycle, security, and redaction coverage.

## Data / contracts

### Integration provider registry

- Supported provider IDs are the stable server-side values `slack`, `gmail`, and `outlook`.
- Provider adapters own authorization endpoints, provider-specific scopes, token exchange/refresh/revocation, identity normalization, and upstream error translation. The browser may select only a registered provider ID; it cannot supply scopes, endpoints, redirect targets, or credential keys.
- Catalog-only IDs `teams`, `github`, and `webhooks` return `integration_not_supported` from lifecycle APIs and never reach an external provider.

### IntegrationConnection

- One application-level row per supported provider, with a unique `provider` value.
- Stores an internal UUID, provider, lifecycle `status` (`not_connected`, `authorizing`, `connected`, `error`, or `revoked`), normalized external account identifier/label, granted scope names, encrypted access/refresh token material, safe last-error code, last-tested timestamp, creator/updater actor references, and created/updated timestamps.
- Token fields are server-only encrypted material using the configured Fernet boundary. API schemas expose only safe metadata; a missing or invalid encryption key fails closed.
- Connection replacement is atomic. A failed callback does not overwrite an existing connected row; disconnect clears token material and marks the connection revoked/idempotently disconnected.

### IntegrationOAuthState

- Stores only a cryptographic digest of the random state, provider, initiating actor, expiry, consumed timestamp, and created timestamp; the raw state is never persisted or audited.
- State is single-use, short-lived (10 minutes), provider-bound, and actor-bound. Consuming it and persisting the resulting connection occur in one database transaction.

### Credential definitions

- Provider application credentials are registered, fixed server-side integration keys surfaced through the existing Settings Credentials page. They are never accepted as arbitrary browser-controlled identifiers and are never returned as plaintext.
- The implementation must document the exact registered keys and display metadata in the provider registry/tests. Client IDs may be stored through the same metadata-only credential surface for one consistent admin flow; client secrets remain write-only.

### API shapes

- `GET /api/v1/settings/integrations` returns provider ID, display name, supported status, lifecycle status, safe external account label, granted scopes, last-tested timestamp, safe error code, and whether required application configuration is present.
- `POST /api/v1/settings/integrations/{provider}/authorize` returns a provider authorization URL and an expiry timestamp; it never returns a standalone raw state value or credentials.
- `GET /api/v1/settings/integrations/{provider}/callback` accepts only provider callback parameters, validates the stored state, and returns/redirects to a safe success or failure result without tokens or raw upstream data.
- `POST /api/v1/settings/integrations/{provider}/test` validates the stored connection through the adapter and returns normalized status plus safe error metadata.
- `DELETE /api/v1/settings/integrations/{provider}` revokes/clears the connection and returns the safe disconnected metadata; repeated deletion is idempotent.
- Error bodies follow the existing `{ "code": string, "message": string }` shape. Stable codes include `integration_not_supported`, `integration_not_configured`, `integration_not_connected`, `integration_state_invalid`, `integration_state_expired`, `integration_callback_denied`, `integration_provider_unavailable`, `integration_scope_denied`, `integration_connection_invalid`, and `integration_encryption_unavailable`.

### Authorization and audit

- Read/list operations require `Permission.SETTINGS_READ`; authorization, callback completion, test, and disconnect mutations require `Permission.SETTINGS_WRITE`. The existing role mapping keeps these Settings permissions administrator-only.
- OAuth callback authorization comes from the consumed server-side state and its actor, not from a browser role claim or callback query parameter.
- Audit actions use the `integration.` prefix: authorization started, connected, authorization failed, test succeeded/failed, and disconnected. Context is limited to provider, connection ID, safe status/error code, and operation result; never include tokens, codes, state, raw URLs, provider bodies, or message content.

### Delivery boundary

22c1 establishes connection and test contracts only. 22c2 may use the normalized provider ID, connection UUID, safe status, and backend-only adapter send boundary, but must define its own event, destination, queue, retry, and delivery-history contracts before implementation.

## Testing

- `./scripts/verify-feature.sh` - required local feature gate; backend focused tests run when backend application/test files change, followed by the Assistant suite and frontend production build.
- `cd backend && python3 -m pytest` - full backend regression suite when needed for final completion or CI.
- `cd backend && PYTHONPATH=. alembic upgrade head --sql` - migration SQL validation.
- `cd k8s-ui && yarn lint` - frontend lint; existing unrelated warnings remain non-blocking unless new findings appear.
- `git diff --check` - whitespace and patch sanity.
- Verification evidence: the feature-focused backend suite passed 23 tests (`test_integration_adapters.py`, `test_integrations.py`, and `test_application_settings.py`); backend bytecode compilation, migration SQL generation, and `git diff --check` passed; the Assistant suite passed 13 tests; and `yarn lint` passed with 13 pre-existing warnings and no errors. The exact required `./scripts/verify-feature.sh` passed all 23 backend tests, all 13 Assistant tests, TypeScript compilation, and the Turbopack production build with 44 generated routes. A direct `yarn next build --webpack` production build also passed. No browser evidence was available.
- No browser test command is configured. Manual browser evidence is optional under `verification.uiEvidence: "when-available"`; do not claim OAuth or provider behavior without a safe test seam or rendered evidence.

## Notes for the AI

- Keep this feature application-level and administrator-controlled; do not introduce per-user connector ownership or a generic secret manager.
- Treat all provider callback values and response bodies as untrusted external data. Validate provider/state/actor relationships before mutation and translate errors at the adapter boundary.
- Never derive an OAuth redirect origin from an untrusted `Host` header, never put a client secret in a Next.js client bundle, and never send a provider token through a browser route.
- Reuse existing Settings credentials, permissions, audit redaction, same-origin proxy, SQLAlchemy, and Alembic patterns rather than adding parallel infrastructure.
- Do not implement delivery in this branch. Keep the normalized connection status and adapter seam stable for 22c2.

## Open questions

- Confirm the deployment-controlled public callback origin/configuration key before enabling provider callbacks. The safe implementation assumption is a server-only `KUBEPILOT_PUBLIC_URL`; it must not be inferred from an untrusted request host. This blocks the callback integration step if deployment does not provide an approved public origin.
