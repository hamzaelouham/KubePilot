# Current Feature

**Title:** Settings service and secure credential storage
**Type:** Feature
**Status:** implementation complete; full Verify limited by baseline assistant test timeout
**Branch:** `feature/settings-service-and-secure-credential-storage`

## Goal

Create the persistent backend foundation for KubePilot-managed runtime settings and external credentials. The service must give later provider and integration features one repository/service boundary, encrypt credential values at rest with a server-side Fernet key, expose only safe credential metadata through normal APIs, validate configurable provider URLs against an explicit SSRF policy, and audit sensitive administrative changes.

This feature keeps bootstrap/infrastructure configuration separate from mutable application configuration. `DATABASE_URL`, the session/authentication secret, Kubernetes service-account configuration, and `KUBEPILOT_ENCRYPTION_KEY` remain Kubernetes-managed bootstrap inputs; the Settings service must never turn the process environment into a generic editable database.

## In scope

- Add a typed application-settings repository/service with an allowlisted definition registry, rather than arbitrary key/value or environment-variable editing.
- Add persistent application-setting storage for future global runtime settings without registering screenshot-only or provider-specific fields before their planned features define them.
- Add a generic credential store for provider/integration credentials with stable server-owned credential identifiers, encrypted ciphertext, ownership/update metadata, and timestamps.
- Add a server-side encryption service using the maintained `cryptography` package's Fernet implementation and `KUBEPILOT_ENCRYPTION_KEY` from bootstrap/Kubernetes Secret configuration.
- Add admin-only Settings read/write permission coverage for global settings and credential metadata/mutations while preserving 20b's actor-scoped user preferences.
- Add safe credential metadata endpoints and write-only create/replace/delete operations; normal GET responses must never contain plaintext, ciphertext, decrypted values, or reveal/copy actions.
- Add audit events for application setting changes and credential creation, replacement, and deletion, with actor/resource/result metadata only and no secret payloads.
- Add a reusable provider base-URL policy that rejects malformed or credential-bearing URLs, unsafe URL components, and disallowed hosts/IP ranges before later provider connection code can request them.
- Update backend dependency/bootstrap documentation and Kubernetes manifests for the encryption-key contract without committing real secret material.
- Add focused backend tests for encryption, persistence, authorization, redaction, audit safety, allowlisted setting keys, and SSRF URL validation.

## Out of scope

- OpenAI, OpenRouter, Ollama, or any other provider implementation, connection test, model discovery, AI model registry, or Assistant integration; those belong to 20d, 20e, and 21.
- Provider/integration Settings cards, credential overview UI, OAuth flows, or integration workflows; 20d and 20f consume this backend foundation.
- A generic Settings UI/API that accepts arbitrary environment variable names, provider IDs, URLs, JSON keys, or database columns.
- Credential reveal/copy, plaintext secret reads, client-side/localStorage/cookie secret storage, key export, or automatic encryption-key rotation.
- Storing Kubernetes credentials, kubeconfigs, bearer tokens, authorization headers, or bootstrap secrets in the new tables.
- Changing the existing per-user `UserPreference` API or the 20b General/Appearance pages except where shared permission/service boundaries require compatibility adjustments.

## Build loop

1. Implement one small backend step and add its focused tests.
2. Run the narrowest relevant pytest selection and static/syntax checks after each step.
3. Review the diff for plaintext/ciphertext leakage, actor scope, key allowlisting, audit redaction, URL policy, and migration safety.
4. Run the declared project Verify command once at the end; record the existing assistant-suite limitation if it still stalls.
5. Continue through the feature steps without a checkpoint commit because the project uses feature-level review and disabled checkpoint commits.

## Build steps

### 1. [x] Define bootstrap encryption and server-side crypto boundary

Add the optional-at-boot `KUBEPILOT_ENCRYPTION_KEY` configuration field and deployment documentation, while making credential operations fail closed with the existing service-unavailable error convention when the key is absent or is not a valid Fernet key. Use `cryptography.fernet.Fernet`; do not implement encryption primitives, key derivation, or plaintext fallback. Keep the key outside PostgreSQL and browser/API responses.

Done when:

- The backend can construct the crypto service only from the server-side configured key, valid Fernet keys encrypt/decrypt round trips, invalid or absent keys cannot store/read credential values, and plaintext is never used as a fallback.
- Existing non-credential application startup and tests do not require a secret default, while Kubernetes/bootstrap examples clearly provide the new key before credential management is enabled.
- The encryption key is absent from logs, audit context, API payloads, client bundles, and database records.

### 2. [x] Add repository-backed settings and encrypted credential persistence

Add Alembic-backed tables/models for allowlisted application settings and credentials. The application-setting record stores only non-secret typed JSON values. The credential record stores a server-owned credential key, Fernet ciphertext, creator/updater metadata, and timestamps, with uniqueness enforced at the database boundary. Add focused repository/service methods that resolve keys through a definition registry, encrypt before persistence, decrypt only inside trusted backend code, preserve update metadata, and delete atomically.

Done when:

- Settings and credential records survive a new SQLAlchemy session and the migration SQL creates/downgrades the complete schema without changing existing tables unexpectedly.
- A credential row contains ciphertext that does not equal the submitted secret, and no repository/list method returns plaintext or ciphertext to an API response.
- Unknown setting/credential identifiers are rejected before persistence; duplicate identity is handled deterministically; replacing and deleting a credential updates/removes only the requested record.
- No Kubernetes credential, environment variable value, API key, OAuth token, or authorization header is imported into the store automatically.

### 3. [x] Expose strict admin Settings and credential metadata APIs

Extend the existing FastAPI Settings router with typed, `extra="forbid"` schemas and server-enforced admin authorization for global setting and credential operations. Provide safe configuration metadata/value responses only for registered non-secret settings and credential metadata (`credential_key`, configured state, and timestamps). Accept a secret only on create/replace, return metadata after mutation, and expose deletion without a reveal endpoint. Add dedicated write permission semantics while preserving the existing admin-only Settings access check.

Done when:

- Unauthenticated and non-admin callers receive the existing safe 401/403 responses for global Settings and credential endpoints; admin identity comes only from the existing FastAPI session dependency, never from request fields.
- GET/list responses never contain submitted secrets, Fernet ciphertext, secret-shaped audit context, or an arbitrary setting/env key; unknown fields, unknown identifiers, malformed values, and cross-resource paths are rejected.
- Create/replace/delete operations commit atomically, return stable non-sensitive response shapes, and cannot mass-assign model fields or alter bootstrap configuration.
- The existing 20b user preference routes remain actor-scoped and continue to work independently of the admin global-settings permission.

### 4. [x] Add SSRF-safe provider URL policy and audit events

Implement a reusable server-side URL validation/policy module for later provider connection code. Accept only the supported HTTP(S) URL shape, reject userinfo, query/fragment injection, malformed hosts, unsafe IP literals, and disallowed schemes. Require private/internal HTTP destinations to be explicitly allowlisted through bootstrap configuration (for example, a Kubernetes Ollama Service hostname), and provide a safe resolution/request-policy seam so later connection tests can block private, loopback, link-local, reserved, and metadata destinations and redirects.

Add audit event constants and service calls for setting create/update/delete and credential create/replace/delete. Audit records must identify the actor, safe credential/setting identifier, result, and timestamps without values or headers.

Done when:

- Unit tests cover allowed public HTTPS and explicitly allowlisted internal endpoints plus localhost/private/link-local/metadata/IP-literal, credentials, query, fragment, unsupported-scheme, malformed-host, and redirect-policy rejection cases.
- URL validation performs no network request as a side effect and later callers receive a clear typed rejection they cannot bypass by changing a provider ID or URL field.
- Every sensitive admin mutation emits exactly one redacted audit event after a successful transaction; failed validation/storage does not claim success and no secret appears in event context.

### 5. [x] Wire bootstrap/deployment contracts and final verification

Update `backend/requirements.txt`, backend environment documentation/examples, and Kubernetes Secret/deployment/configuration references for `KUBEPILOT_ENCRYPTION_KEY` and the server-side provider-host policy. Keep local placeholders clearly non-production and do not commit a real credential. Run migration SQL validation, focused tests, backend syntax checks, `git diff --check`, and the declared Verify command.

Done when:

- A fresh deployment can identify the bootstrap key/policy inputs without exposing their values in the UI or API, and a missing key causes credential operations to fail closed with an actionable safe error.
- Focused security/persistence tests, backend syntax, migration SQL validation, and frontend build pass.
- The full declared Verify result is recorded honestly; the known baseline behavior is a timeout at `tests/test_assistant.py` only if it remains reproducible after the in-scope changes.

Verification evidence:

- Focused Settings/credential/crypto/URL/RBAC tests: 23 passed.
- Backend syntax and `git diff --check`: passed.
- Alembic offline upgrade and downgrade SQL generation: passed.
- Frontend `cd k8s-ui && yarn verify`: passed.
- Declared full Verify: timed out after 120 seconds at `tests/test_assistant.py` after collecting 530 tests; no 20c assertion failure was reported.

## Files / areas

- `backend/app/core/config.py` for bootstrap configuration loading and safe validation.
- `backend/app/core/rbac.py`, `backend/app/core/dependencies.py`, and `backend/app/core/audit.py` for admin authorization, session actor identity, and redacted audit recording.
- `backend/app/models/entities.py`, `backend/app/models/base.py`, and a new Alembic revision under `backend/alembic/versions/` for persistent settings/credential records.
- A focused backend settings/configuration/credentials service and schemas under the existing `backend/app/services/` and `backend/app/api/v1/` conventions.
- `backend/requirements.txt`, `backend/.env.example`, `backend/README.md`, and `backend/deploy/kubernetes/secret.yaml` / `backend.yaml` / `configmap.yaml` for the bootstrap contract.
- Existing backend tests plus focused settings/credential/URL-policy tests under `backend/tests/`.
- `k8s-ui/app/api/settings/` only if the secure metadata API needs a same-origin proxy in this foundation; no provider/credential UI is in scope.

## Data / contracts

Bootstrap configuration:

```text
KUBEPILOT_ENCRYPTION_KEY
  Fernet key, Kubernetes Secret/bootstrap only; never persisted or returned

KUBEPILOT_PROVIDER_ALLOWED_HOSTS
  Optional comma-separated exact hostnames for approved private/internal
  provider endpoints; bootstrap policy, not a Settings-editable value
```

The existing `Settings` dataclass reads these values without exposing them as arbitrary editable settings. The encryption key may remain unset for deployments that do not use credential management, but all credential reads/writes must return the existing safe service-unavailable error until a valid key is configured. No generated/default key may be persisted or silently used.

Persistent records:

```text
ApplicationSetting
  id: UUID
  key: unique server-registered setting identifier
  value_json: non-secret JSON value validated by the key definition
  created_by_id / updated_by_id: authenticated admin UUID metadata
  created_at / updated_at: timestamps

ApplicationCredential
  id: UUID
  credential_key: unique server-registered provider/integration credential identifier
  ciphertext: Fernet-encrypted secret material; database-only ciphertext
  created_by_id / updated_by_id: authenticated admin UUID metadata
  created_at / updated_at: timestamps
```

Safe API shapes should be strict and metadata-only for credentials:

```text
GET    /api/v1/settings/configuration
PUT    /api/v1/settings/configuration/{registered_key}
GET    /api/v1/settings/credentials
PUT    /api/v1/settings/credentials/{registered_credential_key}
DELETE /api/v1/settings/credentials/{registered_credential_key}

credential list item:
{
  credential_key: string,
  configured: boolean,
  updated_at: timestamp | null
}

credential write body:
{
  value: string
}

credential write/delete response:
  metadata only; never value or ciphertext
```

Only server-registered keys can reach the repository. Global setting values are typed by their definitions; raw JSON mass assignment and arbitrary environment names are invalid. Credential identifiers are not accepted as instructions for network access. Provider-specific definitions and user-facing configuration are added by later features.

URL policy contract:

- HTTP and HTTPS are the only schemes considered.
- Userinfo, query strings, fragments, malformed/empty hosts, unsupported schemes, and direct unsafe IP literals are rejected.
- Private, loopback, link-local, reserved, multicast, unspecified, and cloud metadata destinations are denied unless the hostname is an exact bootstrap-allowlisted internal service name; later network callers must apply the same policy after DNS resolution and must not follow unvalidated redirects.
- URL validation is a pure policy step in 20c; it must not make an outbound request.

Audit contract:

- Add stable actions for `settings.create`, `settings.update`, `settings.delete`, `credential.create`, `credential.replace`, and `credential.delete` (or the repository's equivalent naming convention).
- Record actor ID, safe resource type/key, result, and timestamps only. Never record values, ciphertext, authorization headers, request bodies, or key material.

## Testing

- Backend focused tests: Fernet round trip and invalid/missing-key fail-closed behavior; ciphertext-at-rest and persistence; server-registered key enforcement; admin/operator/viewer/unauthenticated authorization; write-only responses; atomic replace/delete; audit redaction; and SSRF URL policy cases.
- Migration SQL: run the existing Alembic offline upgrade check and verify the new tables/constraints are represented.
- Backend syntax: run `cd backend && python3 -m compileall -q app`.
- Frontend: run `cd k8s-ui && yarn verify` if the same-origin metadata proxy or shared Settings types are touched.
- Final declared gate: run `cd backend && .venv/bin/python3 -m pytest && cd k8s-ui && yarn verify` from the repository's documented workflow, recording the exact result. At planning time the baseline collected 509 backend tests and stalled at `tests/test_assistant.py` until timeout; do not skip that test silently or claim the full gate passed.

## Notes for the AI

- Use every image in `blueprint/reference/` as ongoing inspiration for Settings hierarchy, content grouping, status treatment, and interaction patterns. References guide compatible content decisions only; the existing KubePilot layout, shell, sidebar, global navigation, typography, fonts, colors, spacing tokens, responsive behavior, and shadcn/ui design language are fixed and must not be changed or replaced.
- Reuse the existing SQLAlchemy session factory, Pydantic `extra="forbid"` style, FastAPI error handler, `require_permission`, `record_audit`, Alembic conventions, and Kubernetes Secret manifests.
- Keep credential encryption/decryption in one backend service. Never decrypt in route handlers for response construction, frontend code, logs, audit context, or background request metadata.
- Use a server-owned definition registry for application-setting and credential keys. Later provider/integration features extend that registry; they must not bypass it with arbitrary IDs.
- Treat URL validation as defense in depth. A later provider connection client must enforce the same host/IP/redirect policy at request time because validation alone cannot prevent DNS rebinding or redirect SSRF.
- Do not add a credential page to the currently planned Settings navigation in 20c; 20f owns the credentials overview UI. Keep the current layout and planned navigation unchanged.
- Do not make `KUBEPILOT_ENCRYPTION_KEY` editable through the Settings API, and do not place it in `.env` examples as a real reusable production secret.
