# Current Feature: AI model management

**Type:** Feature 20e

**Status:** verified

**Branch:** `feature/ai-model-management`

## Goal

Add an administrator-managed AI model registry owned by the existing allowlisted
OpenAI, OpenRouter, and Ollama providers. Persist model identity, display name,
enabled/default state, capabilities, and checked availability; expose a safe
enabled-and-available read contract for the future Assistant selector without
changing the Assistant's current AI Gateway runtime in this feature.

## In scope

- A persisted `AIModelConfig` registry with one provider owner and one external model identifier per record.
- Administrator-only list, create, update, delete, availability-check, and set-default APIs under Settings.
- A read-only authenticated contract that returns only models eligible for a future Assistant selector.
- Explicit capabilities for streaming, tool calling, reasoning, vision, and large-context support.
- Explicit `unknown`, `available`, and `unavailable` availability states with safe status messages and check timestamps.
- A Models Settings page with loading, empty, error, create/edit, enable/disable, availability-check, default, and delete flows.
- Audit records for model mutations and default changes without credentials or raw provider responses.
- Backend service/API tests, migration SQL verification, frontend type validation, and production build verification.

## Out of scope

- Removing AI Gateway, initializing provider SDKs, resolving runtime models, or changing `/api/assistant` behavior.
- Adding the Assistant model selector or attaching tools according to model capabilities; those remain features 21a–21d.
- Automatic provider catalog synchronization, scheduled health checks, model discovery/import, pricing, token limits, usage accounting, or benchmarking.
- Adding providers beyond the existing `openai`, `openrouter`, and `ollama` allowlist.
- Storing provider credentials, endpoints, or upstream response bodies in model records or returning them from model APIs.
- Models for integrations, embedding-only workflows, image generation, or other non-Assistant workloads.

## Build loop

Implement all steps on `feature/ai-model-management`. The configured workflow
uses one feature-level review after the steps are complete
(`workflow.stepReview: "feature"`) and checkpoint commits are disabled.
`/complete` creates the final feature commit.

## Build steps

- [x] **1. Add the persistent model registry and migration.** Add `AIModelConfig` to the existing SQLAlchemy model package and create an Alembic migration. Store an internal UUID, allowlisted `provider_id`, trimmed case-preserving `external_model_id`, trimmed `friendly_name`, `enabled`, `is_default`, capability booleans, availability state/message/check timestamp, actor references, and timestamps. Enforce one external ID per provider and at most one global default at the database boundary.

  **Done when:** migration upgrade/downgrade SQL defines the registry, foreign keys, uniqueness constraints/indexes, and defaults; duplicate provider/model identities and multiple defaults cannot be persisted; model and migration tests pass.

- [x] **2. Implement model services and administrator APIs.** Add focused schemas and a model-registry service, then expose `GET/POST /api/v1/settings/models`, `PUT/DELETE /api/v1/settings/models/{model_id}`, `POST /api/v1/settings/models/{model_id}/check`, and `POST /api/v1/settings/models/{model_id}/default`. Reuse `SETTINGS_READ`/`SETTINGS_WRITE`, the provider allowlist, encrypted credential access, URL policy, bounded HTTP behavior, transaction handling, and audit infrastructure from provider management.

  **Done when:** only admins can read or mutate Settings models; unknown providers and malformed input are rejected; CRUD and default changes are atomic and audited; availability checks never expose credentials or raw upstream content; focused API/service tests cover success, denied, invalid, duplicate, missing, provider-failure, and rollback behavior.

- [x] **3. Define selector eligibility and safe state transitions.** Add an authenticated `GET /api/v1/assistant/models` response containing only internal model ID, provider ID/name, external model ID, friendly name, capabilities, and default state for records where `enabled=true` and `availability=available`. Keep at most one returned default and never silently choose a replacement.

  **Done when:** setting default is allowed only for an enabled, available model; disabling, deleting, or changing the identity of the current default is rejected until another default is selected; changing a non-default provider/external identity resets availability to `unknown`; a successful catalog lookup marks exact model presence `available` and absence `unavailable`; configuration, network, blocked-URL, oversized, or malformed-response failures produce `unknown` with a safe message; selector-contract tests prove disabled, unknown, unavailable, and unconfigured-provider models are excluded.

- [x] **4. Add the Models Settings interface.** Promote Models from the planned label in `SettingsShell` to `/settings/models`, add the page and client view, and add typed/Zod-validated frontend helpers plus same-origin Next proxy routes. Reuse existing shadcn cards, badges, controls, dialogs, and confirmation patterns to show provider ownership, external ID, friendly name, capabilities, enabled/default state, availability, and last check.

  **Done when:** an administrator can load, create, edit, enable/disable, check, set default, and delete permitted model records with concise inline feedback; loading, empty, invalid, denied, unavailable, and unexpected-error states are visible and accessible; destructive deletion requires exact model confirmation; unavailable providers do not break the rest of the registry; frontend typecheck/build passes.

- [x] **5. Complete regression and migration verification.** Run focused model tests, the full backend suite, Alembic SQL generation, frontend lint/type validation, and the declared project Verify command. Review `/settings/models` against the deployed Minikube environment when live provider configuration is available, without claiming provider availability that was not observed.

  **Done when:** all automated fallback gates pass; existing provider management and Settings authorization remain unchanged; the Models page has a clear manual try path for configured and unconfigured providers; any Turbopack sandbox limitation or unavailable live provider is recorded as an environment limitation rather than a passing integration result.

## Files / areas

- `backend/app/models/entities.py`, `backend/app/models/__init__.py` — `AIModelConfig` persistence and exports.
- `backend/alembic/versions/` — model-registry migration with provider/model and global-default uniqueness.
- `backend/app/services/ai_models.py` — CRUD, default invariants, selector eligibility, catalog checks, and safe availability transitions.
- `backend/app/services/ai_providers.py` — minimally share existing allowlisted provider configuration, credential, URL-policy, and bounded-catalog request behavior; preserve current provider APIs.
- `backend/app/api/v1/settings_schemas.py`, `backend/app/api/v1/settings.py` — administrator model schemas and routes.
- `backend/app/api/v1/assistant.py` — authenticated eligible-model read endpoint only; no runtime model initialization.
- `backend/app/core/audit.py` — model registry/default audit event names.
- `backend/tests/test_ai_models.py` and applicable Settings/Assistant/provider tests — persistence, service, API, authorization, security, and regression coverage.
- `k8s-ui/app/settings/(admin)/models/page.tsx`, `k8s-ui/components/settings-models-view.tsx` — Models page and management interface.
- `k8s-ui/lib/settings-models.ts`, `k8s-ui/app/api/settings/models/**` — strict response validation and same-origin proxies.
- `k8s-ui/components/settings-shell.tsx` — activate Models navigation while leaving later Settings sections planned.

## Data / contracts

- `AIModelConfig.id` is the stable internal UUID used by Settings mutations and the future Assistant selector; clients never use the external model string as a route identifier.
- `provider_id` is one of `openai`, `openrouter`, or `ollama`. It references the code-owned provider registry because feature 20d does not persist provider rows; arbitrary provider IDs are rejected.
- `(provider_id, external_model_id)` is unique. `external_model_id` is trimmed, non-empty, case-preserving, and bounded to 255 characters. `friendly_name` is trimmed, non-empty, and bounded to 128 characters.
- Capabilities serialize as an explicit object of booleans: `streaming`, `tools`, `reasoning`, `vision`, and `large_context`. No capability is inferred from a provider name or model ID.
- New models default to `enabled=false`, `is_default=false`, and `availability=unknown`. Capability values are supplied explicitly by the administrator; the UI may begin with all capability checkboxes clear but must show their meaning.
- Availability is not administrator-editable. `POST .../check` performs the only feature-20e provider call, compares the exact external ID against the allowlisted provider's normalized catalog, and updates status, a safe bounded message, and `availability_checked_at`. List/create/update/default/delete do not contact providers.
- Catalog adapters normalize model identifiers from each allowlisted provider behind one service interface and are covered with fixed test responses. Provider URLs, redirects, credentials, timeouts, and response-size limits retain feature 20d's fail-closed policy.
- `available` means a successful current catalog response contained the exact external ID; `unavailable` means a successful valid catalog response did not contain it; `unknown` means no successful determination exists or the check could not safely complete.
- There may be zero or one global default. A default remains visibly flagged if a later explicit check changes it away from `available`, but it disappears from the eligible selector response; the backend never silently promotes another model.
- Model API errors use the existing `{detail: {code, message}}` shape with stable not-found, validation, duplicate/conflict, and default-conflict codes. Upstream bodies, credentials, stack traces, and internal URLs are never included.
- `GET /api/v1/assistant/models` requires an authenticated application user but not Settings administration. It is read-only and returns only selector-safe model metadata; feature 21c will consume it and decide how the selector is presented.
- All Settings model reads/writes remain global application configuration and admin-only, matching the existing Settings boundary; there is no cluster, namespace, user, or tenant scope on a model record.

## Testing

- Focused backend tests: `.venv/bin/python3 -m pytest tests/test_ai_models.py` from `backend/`.
- Full backend tests: `cd backend && .venv/bin/python3 -m pytest`.
- Migration SQL: `cd backend && PYTHONPATH=. alembic upgrade head --sql`.
- Frontend checks use the repository's existing lint/type/build scripts; no frontend unit or browser runner is configured.
- Declared project Verify command: `cd backend && .venv/bin/python3 -m pytest && cd ../k8s-ui && yarn verify`.
- Planning baseline on 2026-09-15: the declared command completed the backend suite with `536 passed in 290.85s`; frontend `yarn verify` reached Next.js 16.3.3 Turbopack but the agent's managed execution sandbox forbade creating its helper process/binding its port while processing `app/globals.css`. The user then ran `yarn verify` directly from `k8s-ui/` in the normal local environment: Turbopack compiled successfully, TypeScript passed, all 37 pages generated, and the command completed in `14.95s`. Together these are passing backend and frontend baseline evidence, although the exact combined command must still be rerun during implementation/completion. Use `yarn next build --webpack` only as the fallback inside the managed agent environment if its Turbopack restriction recurs.
- Implementation verification on 2026-09-15: focused model/provider/authorization tests passed (`21 passed`), migration SQL generation reached `j6e7f8a9b0c1`, touched frontend ESLint passed, `yarn tsc --noEmit` passed, and `yarn next build --webpack` generated all 39 routes. The first full suite exposed the expected-table assertion in `tests/test_models.py`; after adding `ai_model_configs` and its constraint checks, the exact declared Verify command passed with `549 passed in 407.09s` followed by a successful Next.js 16.3.3 Turbopack build, TypeScript check, and generation of all 39 pages in `76.95s`.
- Completion verification on 2026-09-15: the exact declared Verify command passed in this final session against the complete working tree — backend `549 passed in 351.18s`, then frontend `yarn verify` compiled, typed, and generated all 39 pages in `39.70s`.
- Repository-wide `yarn lint` still reports 19 pre-existing errors in unrelated AI Elements, appearance/general Settings forms, and the carousel primitive. No feature-20e file appears in that failure set; the touched-file ESLint command passes.
- Live Minikube/provider interaction was not run by the agent during implementation. Availability against real configured providers remains the manual review path; no live provider result is claimed.
- Manual proof should use the GitHub-Actions-built branch images deployed to Minikube, because local `yarn dev` cannot access the live cluster data used by this project.

## Notes for the AI

- Preserve the existing Settings admin layout and `SETTINGS_READ`/`SETTINGS_WRITE` authorization. The eligible Assistant model endpoint is the sole non-admin model read surface and must return only its narrow allowlisted shape.
- Keep credentials in `ApplicationCredential`; decrypt them only inside the backend availability check and never persist or log plaintext.
- Reuse feature 20d's provider definitions and network protections rather than creating a second endpoint/credential registry.
- Treat all upstream catalog data and administrator-entered labels as untrusted text. Render text only; never interpret names or messages as HTML.
- Do not wire the registry into `k8s-ui/app/api/assistant/route.ts`, remove `AI_GATEWAY_API_KEY`, or add provider SDK packages. Those are feature 21 responsibilities.
- Before implementation changes to Next.js files, read the relevant local Next.js 16 guides under `k8s-ui/node_modules/next/dist/docs/` as required by `AGENTS.md`.