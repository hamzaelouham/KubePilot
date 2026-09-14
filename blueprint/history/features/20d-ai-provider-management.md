# Current Feature

**Branch:** `feature/ai-provider-management`
**Status:** verified

## Goal

Add the administrator-only AI Providers Settings page for the three supported
provider IDs—`openai`, `openrouter`, and `ollama`. Each provider is represented by
server-owned metadata and an extensible adapter contract, can save its typed
non-secret configuration and write-only credential through the existing settings
store, and can return explicit configuration and connection-test status without
allowing one provider failure to break the Settings area.

This feature prepares provider configuration for the direct-provider AI work in
feature 21. It does not add model registration or change the existing assistant
streaming/tool/approval path.

## Design reference

Use [the provided Settings reference](../reference/ai-provider-settings-reference.png)
as the visual baseline. The provider page must preserve the existing KubePilot
shell: white top bar, cyan Settings band, left navigation, pale workspace,
large rounded Settings surface, compact secondary navigation, bordered cards,
calm navy typography, muted helper text, and cyan primary actions. Provider
cards should compose with this layout and spacing rather than introducing a new
dashboard, dark-first palette, or unrelated card system.

## In scope

- Register the allowlisted provider IDs and server-owned display/configuration
  metadata for OpenAI, OpenRouter, and Ollama.
- Persist provider configuration in the existing `ApplicationSetting` store and
  provider credentials in the existing encrypted `ApplicationCredential` store;
  no bootstrap environment variable becomes editable.
- Add typed FastAPI list/save/connection-test contracts under `/api/v1/settings/providers`.
- Validate every configured provider URL with `ProviderURLPolicy`, including
  internal-host allowlist rules and redirect revalidation at the network boundary.
- Keep API keys write-only: responses, audit context, exceptions, logs, and UI
  state expose only `api_key_configured` metadata.
- Make provider save atomic across configuration and credential replacement or
  clearing, with repository-first admin authorization and audit records.
- Add bounded, read-only provider adapters for connection tests. OpenAI and
  OpenRouter use their configured OpenAI-compatible models capability endpoint;
  Ollama uses its configured tags capability endpoint. Tests use a mocked HTTP
  seam and never require live provider credentials.
- Add the protected `/settings/providers` page, provider cards, accessible form
  labels/associations, save feedback, connection-test feedback, and loading,
  denied, invalid, empty/not-configured, and unexpected-error states.
- Replace the Settings shell's planned AI Providers marker with the live route.

## Out of scope

- AI model registry, model ownership, enabled/default model state, capabilities,
  availability registry, or assistant model selector changes (20e).
- Refactoring the Vercel AI Gateway integration to direct provider execution,
  streaming, tool calling, or model resolution (21).
- Arbitrary provider registration or user-supplied provider IDs.
- OAuth, integrations, secrets overview UI, audit-log UI, or AI Agents work.
- Editing Kubernetes bootstrap configuration or exposing environment variables.
- Background jobs, credential rotation workflows, provider discovery, model
  discovery persistence, or provider-specific write operations.

## Build loop

- Build on `feature/ai-provider-management`.
- Follow `workflow.stepReview: "feature"`: complete the small implementation
  steps, then present one review packet before `/complete`.
- `workflow.checkpointCommits` is disabled; `/complete` creates the final
  feature commit.
- Run focused backend tests while implementing logic. The final project gate is
  the declared Verify command: `cd backend && .venv/bin/python3 -m pytest && cd k8s-ui && yarn verify`.
- Do not start a dev server as part of implementation verification. Browser
  evidence is not claimed unless a later `/check` or `/try` run captures it.

## Build steps

- [x] **1. Define the provider registry and typed contracts.** Add a focused
  server-side provider registry with the exact IDs `openai`, `openrouter`, and
  `ollama`, stable labels, credential requirements, configuration schema, and
  adapter entry point. Add strict Pydantic request/response models for provider
  summaries, save actions, and connection-test results. Provider lookup must be
  dictionary-based so an unknown path ID fails before persistence or network
  access.

  **Done when:** the backend can enumerate the three known providers in stable
  order, rejects an unknown provider ID with the existing safe error shape, and
  focused registry/schema tests pass without importing the assistant runtime.

- [x] **2. Implement provider persistence and safe connection-test adapters.**
  Extend the application-settings service (or a focused provider service) to
  register provider setting keys and credential keys, validate the typed base URL
  with `ProviderURLPolicy`, and save configuration plus credential action
  (`unchanged`, `replace`, or `clear`) in one database transaction. Preserve an
  existing credential when the action is `unchanged`; reject credential material
  for providers that do not use one. Add bounded HTTP adapters with no automatic
  redirect bypass, redirect validation, a finite timeout, response-size limits,
  and normalized safe success/failure/blocked results. Expected provider failure
  is data returned by the test operation, not an exception that takes down the
  Settings page.

  **Done when:** persistence round trips provider configuration, replacement,
  preservation, and clearing; a failed validation, encryption setup, or database
  write leaves no partial provider mutation; mocked success, timeout, malformed
  response, unsafe redirect, and upstream failure produce stable redacted test
  results; focused service tests pass.

- [x] **3. Expose the protected FastAPI provider API and audit boundary.** Add
  `GET /api/v1/settings/providers`, `PUT /api/v1/settings/providers/{provider_id}`,
  and `POST /api/v1/settings/providers/{provider_id}/test` to the existing
  Settings router. Require `SETTINGS_READ` for listing and
  `SETTINGS_WRITE` for save/test operations; resolve the authenticated actor
  through the existing dependency before reading or mutating repository data.
  Return only provider metadata and safe status/message values. Save and clear
  actions use existing audit infrastructure with provider ID and action metadata
  only—never the API key, ciphertext, URL credentials, upstream body, or raw
  exception. Keep expected provider failures in a successful typed test response
  so one broken provider does not make the list endpoint fail.

  **Done when:** admin list/save/test calls work, operator/viewer calls receive
  the existing 403 contract, unknown IDs and invalid payloads receive safe 4xx
  responses, credential values never appear in response/audit/error text, and
  audit rows prove successful provider changes without sensitive context.

- [x] **4. Add the Settings provider proxy and administrator UI.** Add the
  same-origin Next.js proxy/client helpers for list, save, and test calls using
  the existing forwarded session cookie and backend error conventions. Create
  `/settings/providers` and a reusable provider-card view using the existing
  shadcn/Tailwind settings language and the linked visual reference. Each card shows server-owned provider name,
  configured/not-configured status, URL field, write-only API-key field where
  applicable, save action, test action, pending state, success state, and safe
  failure feedback. A blank key means unchanged; clearing is explicit. Use real
  labels and control associations, announce result text, preserve field values
  on failed saves, clear stale feedback when a new request begins, and keep
  other cards usable when one test fails. Render route-level loading, denied,
  backend-unavailable/unexpected-error, invalid-field, and not-configured states.
  Update `SettingsShell` so AI Providers is a live link with correct active
  navigation and no Planned badge.

  **Done when:** an admin can reach `/settings/providers`, view all three cards,
  submit a valid configuration, explicitly replace/clear a key, and see save or
  connection-test feedback without any key value rendered back; unavailable,
  denied, invalid, and provider-failure responses remain understandable and the
  rest of Settings stays navigable. TypeScript/lint checks for touched UI code
  pass.

- [x] **5. Integrate and run the final verification gate.** Review imports and
  route reachability from `main.py`, the Settings layout, and the Next.js app
  router; ensure provider settings are consumed only by this feature's service
  and are not accidentally wired into assistant model execution. Add or update
  focused backend tests and any repository-owned assistant/settings contract
  tests that cover the unchanged assistant boundary. Run the declared Verify
  command once after implementation and record only observed results.

  **Done when:** all new routes and UI files are reachable in the existing
  runtime, focused tests cover the security and state contracts, and the Verify
  command passes—or the exact failing command and evidence are handed off for
  review without claiming completion.

  **Observed verification handoff:** The focused provider/settings backend tests
  pass (12 tests), and the elevated Webpack production build passes with all
  provider routes reachable. The declared Verify command was also attempted;
  its backend run stalls in the pre-existing assistant TestClient fixture before
  the test body and was interrupted with exit 130, so the frontend half of that
  exact command did not run. The restricted Turbopack build separately fails on
  process/port permission errors. This feature is not marked verified from
  those results.

  **Final `/complete` verification:** The full declared Verify command
  (`cd backend && .venv/bin/python3 -m pytest && cd k8s-ui && yarn verify`) was
  re-run and passed on the feature branch: 536 backend tests passed and the
  Next.js production build completed with `/settings/providers` reachable. The
  only change needed was adding the two `application_settings` and
  `application_credentials` tables to the authoritative `EXPECTED_TABLES` list
  in `backend/tests/test_models.py`, which feature 20c added on master but did
  not include in that test. This feature adds no tables and introduced no
  regression.

## Files / areas

- `backend/app/services/application_settings.py` — existing typed settings and
  encrypted-credential registries and transaction helpers.
- `backend/app/services/ai_providers.py` — provider definitions, validation,
  adapter seam, connection-test normalization, and provider persistence logic.
- `backend/app/services/provider_url_policy.py` and
  `backend/app/services/credential_encryption.py` — existing SSRF and secret
  boundaries to reuse, not bypass.
- `backend/app/api/v1/settings.py` and
  `backend/app/api/v1/settings_schemas.py` — protected provider routes and
  strict API models.
- `backend/app/core/audit.py` — existing redacted settings/credential audit
  events; extend only with provider-specific event names if the existing event
  vocabulary cannot represent the action.
- `backend/tests/test_ai_providers.py`, `backend/tests/test_settings_access.py`,
  and `backend/tests/test_application_settings.py` — focused registry, service,
  authorization, persistence, and redaction coverage.
- `k8s-ui/app/api/settings/providers/route.ts` and
  `k8s-ui/app/api/settings/providers/[providerId]/route.ts` — same-origin proxy
  routes.
- `k8s-ui/app/settings/(admin)/providers/page.tsx`,
  `k8s-ui/components/settings-providers-view.tsx`, and
  `k8s-ui/lib/settings-providers.ts` — provider page, cards, and typed client.
- `k8s-ui/components/settings-shell.tsx` — activate the provider navigation
  entry while preserving the existing protected layout.
- No schema migration is expected: feature 20c already provides the durable
  `application_settings` and `application_credentials` tables. Add a migration
  only if implementation evidence shows the existing typed stores cannot carry
  the provider contract.

## Data / contracts

- Provider IDs are the server-owned allowlist: `openai`, `openrouter`, and
  `ollama`. Route IDs, setting keys, credential keys, labels, and adapter choice
  are never accepted as arbitrary client-defined provider metadata.
- Provider setting keys are stable per-provider keys in the existing registry
  (for example, `ai.provider.openai`); credential keys are stable per-provider
  keys (for example, `ai.provider.openai.api_key`). The exact registered keys
  are defined once beside the provider registry and reused by API, tests, and
  UI helpers.
- Persisted provider configuration contains only typed non-secret data, at
  minimum the configured `base_url`. API keys are encrypted through
  `CredentialEncryption`; plaintext is accepted only in the write request and
  is never returned, logged, audited, or placed in client state after the
  request. Ollama has no API-key field unless its provider definition explicitly
  requires one.
- Save request semantics are explicit: `api_key_action` is `unchanged`,
  `replace`, or `clear`; `replace` requires a non-empty bounded string, `clear`
  removes the encrypted credential, and `unchanged` leaves it untouched. The
  provider configuration and credential action commit atomically.
- `GET` returns a stable list of provider summaries with server-owned identity,
  saved non-secret configuration, and `api_key_configured`; it does not perform
  network calls or return secret material. A provider is `not_configured` until
  its required non-secret configuration and credential requirements are met.
- `POST .../{provider_id}/test` reads the saved secret only on the backend and
  returns a typed result such as `connected`, `not_configured`, `blocked`, or
  `failed`, plus a concise safe message. Provider failures do not expose raw
  upstream responses or turn the whole provider list into an error.
- Provider URLs are HTTP(S) only, bounded, credential-free, query/fragment-free,
  hostname-based, and validated through `ProviderURLPolicy`; internal hosts
  require the configured bootstrap allowlist. Every redirect target is checked
  by the same policy, and the client cannot choose a different adapter or URL
  outside the saved provider configuration.
- The backend is the trusted actor and tenant boundary for all provider reads,
  writes, credentials, network calls, and audits. The Next.js layer forwards the
  signed HTTP-only session cookie and renders backend results; it does not make
  provider calls or decide authorization.

## Testing

- Backend unit/API tests must cover the allowlist and unknown-provider rejection;
  strict payload validation; admin/operator/viewer access; atomic save,
  replacement, preservation, and clearing; encryption failure; SSRF and redirect
  enforcement; adapter success/failure/timeout/redaction; and audit content.
- Use a deterministic injected HTTP client/adapter seam. Do not contact OpenAI,
  OpenRouter, Ollama, or any external host in tests.
- UI verification is through the existing Next.js build and, if separately run,
  the repository's existing assistant/settings contract tests. No browser-test
  harness is added by this feature.
- Baseline observed while creating this spec: the declared backend Verify run
  collected 530 tests, then stalled after starting `tests/test_assistant.py`;
  it was interrupted with exit code 130, so the frontend build did not run.

## Notes for the AI

- Read the current Next.js guide under `k8s-ui/node_modules/next/dist/docs/`
  before writing Next.js code, as required by the repository instructions.
- Preserve the existing admin Settings layout, session-cookie bridge, FastAPI
  permission dependencies, and shadcn/Tailwind visual language.
- Keep provider configuration separate from feature 20e's model registry and
  feature 21's direct AI runtime migration. Do not make the assistant depend on
  a provider selected by this page yet.
- Treat provider status as bounded, explicit data. A connection failure is
  expected operational feedback, not a reason to hide or disable unrelated
  Settings sections.
- If the existing generic credential endpoints are reused by the UI, preserve
  their write-only response contract and ensure provider save semantics cannot
  leave configuration and credential updates half-applied.
