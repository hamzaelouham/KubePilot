# Feature 22a - Secrets and API key management

**Branch:** `feature/secrets-and-api-key-management`

**Status:** verified

## Goal

Give administrators one Settings page for CRUD-style management of secrets and API keys that KubePilot has explicitly registered. Administrators can see safe metadata, configure a missing credential, rotate or replace an existing value, and delete it with confirmation. Stored values remain write-only and are never returned, prefilled, masked from persisted data, copied, or revealed.

## Design reference

- [Settings providers and integrations](../../reference/settings-providers-integrations.png) guides card grouping, configured-state badges, and action hierarchy within the existing KubePilot shell.
- Do not reproduce the reference's masked persisted key or reveal control. KubePilot cannot read credential values back through normal APIs.

## In scope

- Activate `Secrets & Credentials` in the protected Settings navigation and add `/settings/credentials` under the existing admin-only Settings layout.
- List every server-registered credential definition with a safe display name, description, category, configured state, and last-updated timestamp.
- Support create/configure for a missing value, replace/rotate for an existing value, and confirmed deletion through the existing encrypted `ApplicationCredential` service.
- Start with the registered OpenAI and OpenRouter API keys. Later provider or integration modules become visible only by registering their own server-owned definitions.
- Keep provider configuration compatible: credential changes made here affect the same rows used by AI Provider settings and the Assistant runtime.
- Preserve backend authorization, allowlisting, encryption-at-rest, atomic mutation, audit redaction, strict response schemas, and safe error shapes.
- Cover loading, empty, configured, not-configured, saving, deleting, success, validation, denied, and unexpected-error states with accessible feedback.

## Out of scope

- Arbitrary user-named secrets, a general-purpose vault, bulk import/export, secret history, reveal/copy/download, or encryption-key rotation.
- Kubernetes `Secret` resources, kubeconfigs, service-account credentials, database/auth/session secrets, `KUBEPILOT_ENCRYPTION_KEY`, environment variables, or other bootstrap configuration.
- Slack, Gmail, Outlook, OAuth, connection testing, or integration workflows from the rest of Feature 22.
- Provider endpoint editing, model management, or replacing the existing AI Provider configuration page.
- Database schema or migration changes; the existing `application_credentials` table remains authoritative.

## Build loop

- Implement and verify the ordered steps, then present one feature-level review packet (`workflow.stepReview: feature`).
- Checkpoint commits are disabled. `/complete` creates the reviewed feature commit after all gates pass.
- Do not commit, merge, push, deploy, or publish during `/implement` without the separate workflow approval.

## Build steps

- [x] **1. Enrich the allowlisted credential contract with safe presentation metadata.** Extend the server-owned `CredentialDefinition` with a human display name, short safe description, and stable category (`provider` or `integration`); register OpenAI and OpenRouter definitions with that metadata; return it from the existing metadata-only credential endpoints without returning values or ciphertext. Reject unknown keys and values that are empty or whitespace-only, but otherwise treat secret text as opaque and do not trim or normalize it. Preserve exact create/replace/delete audit behavior and provider-store compatibility. Add focused service/API tests for registered metadata, configured and unconfigured rows, create/replace/delete, admin-only access, unknown identifiers, missing encryption key, response redaction, and audit redaction.
  **Done when:** backend tests prove only registered credential definitions can be listed or mutated, both provider credentials expose safe metadata, writes/deletes update the shared encrypted rows atomically, and no response or audit record contains secret material.

- [x] **2. Add the same-origin credential client boundary and reachable Settings route.** Add Next.js GET/PUT/DELETE proxy routes that forward only the signed session cookie to the existing FastAPI endpoints, encode the registered credential key as one path segment, disable caching, preserve upstream status/error responses, and return the repository-standard unavailable response on transport failure. Add a Zod-validated client module for the exact metadata contract. Replace the planned navigation label with a link to `/settings/credentials`, add the admin page, and keep the section inside the existing Settings shell. Add focused frontend tests for schema rejection/redaction expectations and proxy cookie/body/method forwarding using the existing Node test harness.
  **Done when:** an authenticated admin can reach the route, safe credential metadata crosses the proxy unchanged, malformed payloads fail closed, non-admin/unauthenticated responses remain denied by existing frontend and FastAPI controls, and focused frontend tests pass.

- [x] **3. Build the accessible CRUD-style credential management UI.** Render registered credentials as readable cards or rows grouped by category, with configured/not-configured badges and formatted update metadata. Use a password input with `autocomplete="new-password"` for configure/rotate; never prefill it, derive a masked value, or add reveal/copy controls. Clear transient secret input after success and when the editor closes. Require a named confirmation before deletion and warn that dependent providers or integrations will stop working. Disable conflicting actions while a mutation is pending, refresh local metadata after success, preserve entered input after recoverable save errors, and provide retryable loading/error plus empty states. Follow the existing shadcn/Tailwind Settings patterns and keep status/error announcements accessible.
  **Done when:** manual review shows create, rotate, cancel, confirmed delete, loading, empty, validation, denied, and backend-error behavior; no stored secret value appears in DOM state after a successful mutation; the focused frontend checks and declared Verify command are run with results recorded.

## Files / areas

- `backend/app/services/application_settings.py` - registered credential definitions, safe metadata, opaque-value validation, and existing encrypted mutations.
- `backend/app/services/ai_providers.py` - OpenAI/OpenRouter credential registration and shared-store compatibility.
- `backend/app/api/v1/settings.py` and `settings_schemas.py` - strict metadata-only API contracts and existing admin permission boundaries.
- `backend/tests/test_application_settings.py`, provider/settings API tests - allowlisting, authorization, encryption, lifecycle, and redaction coverage.
- `k8s-ui/app/api/settings/credentials/` - same-origin metadata and mutation proxies.
- `k8s-ui/lib/settings-credentials.ts` - strict client schemas and requests.
- `k8s-ui/app/settings/(admin)/credentials/page.tsx` and `k8s-ui/components/settings-credentials-view.tsx` - route and interactive management surface.
- `k8s-ui/components/settings-shell.tsx` and Settings overview copy - active navigation and availability text.
- `k8s-ui/tests/` - focused proxy/client behavior coverage using the existing Node harness.

## Data / contracts

- No new table is required. `ApplicationCredential.credential_key` continues to uniquely identify one encrypted value in PostgreSQL.
- Credential definitions are code-owned and allowlisted. Each definition has `credential_key`, `display_name`, `description`, and `category`; clients cannot create definitions or submit arbitrary keys.
- Metadata reads return only `credential_key`, `display_name`, `description`, `category`, `configured`, and `updated_at`. They never return plaintext, ciphertext, masked fragments, hashes, lengths, prefixes, or suffixes derived from a stored value.
- `PUT /api/v1/settings/credentials/{credential_key}` accepts `{ "value": string }`. The value must contain at least one non-whitespace character and stay within the existing 100,000-character bound; accepted values are encrypted exactly as submitted.
- `DELETE /api/v1/settings/credentials/{credential_key}` is safe when the registered credential is already absent and returns its unconfigured metadata state.
- FastAPI remains authoritative for `SETTINGS_READ` and `SETTINGS_WRITE`; the admin-only Next.js layout is defense in depth, not the authorization boundary.
- Successful create, replace, and delete operations retain the existing audit action names and record only the safe credential key and actor/result metadata.
- OpenAI and OpenRouter provider APIs continue to read and mutate the same credential rows. The credential page does not create a second source of truth.

## Testing

- Run focused backend service/API tests covering safe metadata, encrypted persistence, create/replace/delete, unknown keys, admin/operator/viewer/unauthenticated access, missing encryption configuration, transaction failure, and response/audit redaction.
- Run focused frontend Node tests for schema validation and GET/PUT/DELETE proxy behavior, including cookie forwarding and failure responses.
- Run the declared feature gate: `./scripts/verify-feature.sh`.
- Manually review `/settings/credentials` in light and dark themes at desktop and narrow widths, including keyboard/focus behavior and all mutation/error states.
- Final verification: `./scripts/verify-feature.sh` passed on 2026-09-21 with 12 focused backend tests, 13 Assistant tests, TypeScript validation, a successful Turbopack production build, and all 44 application pages generated. The focused credential client/proxy test also passed 4/4, and the broader backend credential/provider checks passed 18/18 during implementation.

## Notes for the AI

- Before implementation, read the relevant Next.js 16 route-handler and App Router guidance from `k8s-ui/node_modules/next/dist/docs/` as required by the repository instructions.
- Reuse the existing Settings layout, backend proxy helpers, API error shape, strict Pydantic/Zod validation, permission dependencies, audit service, credential encryption service, and provider registry patterns.
- Never log request bodies, secret form state, plaintext/ciphertext, authorization headers, cookies, or raw backend/upstream errors.
- Do not add a generic `POST` endpoint for arbitrary credential definitions. In this contract, “create” means configuring the missing value for a pre-registered credential through the allowlisted `PUT` endpoint.
- Keep the provider page behavior intact. Refreshes on either page must reflect mutations made through the other because both use the same encrypted record.
- Keep user-facing labels and descriptions server-owned so a later registered integration can appear without duplicating a frontend key map.
