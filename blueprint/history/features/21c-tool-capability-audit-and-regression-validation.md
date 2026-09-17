# Current Feature

**Type:** Feature 21c
**Name:** Tool capability, audit, and regression validation
**Branch:** `feature/tool-capability-audit-and-regression-validation`
**Status:** verified

## Goal

Make each Settings-managed AI model's declared tool capability authoritative at
runtime: tool-capable models retain the existing Kubernetes and Helm workflows,
while streaming models without tool support remain usable for conversation but
receive no operational tools. Record safe, durable provider/model and tool
outcomes without prompts, credentials, tool payloads, or raw provider data, and
lock the direct-provider Assistant behavior down with focused regression tests.

## In scope

- Treat the persisted `AIModelConfig.supports_tools` value returned by FastAPI as
  the server-owned source of truth for Assistant tool availability.
- Allow enabled, available, streaming-capable models into the Assistant even
  when `supports_tools` is false.
- Resolve the selected internal model and its capabilities before constructing
  the Next.js `ToolLoopAgent`; register the existing tool set only when the
  resolved model supports tools.
- Keep non-tool models conversational with appropriate instructions and no
  Kubernetes, Helm, proposal, approval, or execution tools.
- Enforce the same capability at the FastAPI inference boundary so a forged or
  stale request cannot forward tool definitions to a non-tool model.
- Record terminal inference outcomes with trusted actor, internal model,
  provider, duration, tool mode, result, and a safe normalized error code where
  applicable.
- Preserve and regression-test the existing authenticated FastAPI tool audit,
  authorization, proposal, approval, cluster-scope, and redaction boundaries.
- Verify direct OpenAI, OpenRouter, and Ollama-compatible streaming plus both
  tool-capable and conversational-only Assistant paths.

## Out of scope

- New providers, model-discovery behavior, capability auto-detection, or changes
  to administrator-declared model capabilities.
- New Kubernetes or Helm tools, autonomous actions, or any LLM-accessible
  approval/execution tool.
- Slack, Gmail, Outlook, AI-agent templates, schedules, or other feature 22 work.
- Persisted conversations, prompts, model responses, tool arguments/results,
  Kubernetes logs, provider response bodies, or credentials in audit records.
- Redesigning the Assistant or Settings UI, adding a browser-test harness, or
  changing CI/deployment configuration.

## Build loop

- Implement the ordered steps on the feature branch and keep the project
  working after each step.
- `workflow.stepReview` is `feature`, so present one review packet after all
  steps rather than pausing after each step.
- Checkpoint commits are disabled. `/complete` creates the reviewed feature
  commit after all required verification passes.

## Build steps

- [x] **Step 1: Enforce model tool capability across the runtime boundary.**
  Update backend model eligibility/runtime resolution to accept streaming models
  with or without tools and carry the trusted capability forward. Resolve the
  selected/default model metadata in the authenticated Next.js route before
  creating the agent. Tool-capable models receive the existing registry;
  conversational-only models receive no tools and no operational instructions.
  Reject a non-tool model request that nevertheless contains tool definitions or
  an operational `tool_choice` with a stable, sanitized capability-mismatch
  error. Preserve internal UUID selection, provider credentials, same-origin
  checks, bounded history, cancellation, and existing safe provider errors.
  **Done when:** focused frontend and backend tests prove tool-capable models can
  still call the existing registry, non-tool models stream text with an empty
  tool surface, and forged tool payloads for non-tool models never reach a
  provider or FastAPI operational endpoint.

- [x] **Step 2: Add terminal provider/model audit outcomes and harden tool audit.**
  Record exactly one `assistant.inference` audit event for each accepted
  inference attempt, including streams that complete, fail before headers, fail
  during iteration, time out, or are cancelled. Derive actor/session identity
  from FastAPI authentication and provider/model/tool capability from the
  database-resolved runtime model. Keep the existing `assistant.tool` event for
  validated tool execution, using consistent success/failure results and only
  bounded safe metadata. Do not store messages, prompts, responses, tool
  arguments/results, log content, cookies, authorization headers, API keys,
  decrypted credentials, external error bodies, or arbitrary exception text.
  **Done when:** backend tests assert terminal success/failure/cancellation and
  tool success/failure records, exactly-once behavior, trusted attribution, and
  explicit absence of sensitive request, provider, and Kubernetes content.

- [x] **Step 3: Complete direct-provider and Assistant regression coverage.**
  Extend the focused Assistant/runtime suites for default and selected internal
  models, OpenAI/OpenRouter/Ollama-compatible streaming, capability mismatch,
  tool-free conversation, tool chaining, safe normalized errors, cancellation,
  and unchanged proposal/approval isolation. Run lint, TypeScript checking,
  focused backend tests, the Assistant test, and the declared feature Verify
  command; retain observable failure output rather than weakening a check.
  **Done when:** the focused backend suites, `yarn test:assistant`, `yarn lint`,
  TypeScript checking, and `./scripts/verify-feature.sh` all pass, with the
  production build completing in an environment where Turbopack may create its
  required local worker process.

- [x] **Step 4: Restore the existing frontend lint baseline.**
  Apply behavior-preserving React/Next.js refactors to the 20 existing lint
  errors reported by `yarn lint` in AI Elements, Settings forms, the shared
  carousel, and related UI components. Move render-time ref access or mutation
  into safe state/effect/event patterns, avoid synchronous state cascades in
  effects, and keep component identity stable. Do not disable rules, add ignore
  patterns, suppress findings, redesign UI, or change product behavior.
  **Done when:** full `yarn lint` reports no errors, existing warnings are
  recorded without being promoted into unrelated scope, and frontend Assistant
  tests plus TypeScript checking still pass.

## Files / areas

- `k8s-ui/app/api/assistant/route.ts` - authenticated selection, capability
  resolution, agent construction, and safe route errors.
- `k8s-ui/lib/assistant/model-resolver.ts` and
  `k8s-ui/lib/assistant/models.ts` - internal model resolution and validated
  capability metadata.
- `k8s-ui/lib/assistant/agent.ts`, `tools.ts`, and `instructions.ts` - conditional
  tool registration and conversational-only instructions.
- `k8s-ui/tests/assistant.test.mjs` - AI SDK routing, streaming, tool, and
  tool-free regression coverage.
- Existing lint-failing files under `k8s-ui/components/ai-elements/`, the
  Settings forms, and `k8s-ui/components/ui/carousel.tsx` - narrow,
  behavior-preserving React lint repairs approved after the baseline gate exposed
  them.
- `backend/app/services/ai_models.py` and `ai_runtime.py` - eligible-model rules,
  trusted runtime capabilities, provider payload enforcement, and stream
  lifecycle outcomes.
- `backend/app/api/v1/assistant.py`, `backend/app/core/audit.py`, and existing
  Assistant schemas - authenticated inference/tool audit boundaries and stable
  safe errors.
- `backend/tests/test_ai_runtime.py`, `test_assistant.py`, and relevant audit-log
  tests - capability, provider, authorization, lifecycle, and redaction proof.

## Data / contracts

- No migration or new persisted model is expected. Existing `AIModelConfig` and
  `AuditAction` records remain authoritative.
- An Assistant-eligible model is enabled, available, and streaming-capable.
  `supports_tools` controls only whether the runtime may expose tools; it no
  longer determines whether conversational streaming is allowed.
- Browser input may select only an internal model UUID or omit selection for the
  default. Capabilities, provider identity, external model ID, and credentials
  are resolved server-side and are never trusted from the browser.
- For `supports_tools=false`, the Next.js agent has no registered tools and the
  FastAPI provider adapter refuses supplied tool definitions or an operational
  tool choice before provider access.
- `assistant.inference` uses the authenticated actor, resource type `ai_model`,
  the resolved internal model identity (or a safe default-selection marker when
  resolution fails), and result `success`, `failed`, or `cancelled`. Safe context
  is limited to provider ID when resolved, tool mode, duration, and a normalized
  application error code.
- Existing `assistant.tool` records retain the validated tool name as resource
  identity and bounded cluster/duration/result metadata. Tool authorization and
  mutation audit records remain in FastAPI; the model cannot approve or execute
  a proposal.
- Audit serialization must remain compatible with the existing Settings audit
  log API and must not include raw prompts, messages, outputs, provider bodies,
  tool inputs/results, logs, secrets, cookies, or credentials.

## Testing

- Backend focused tests:
  `cd backend && .venv/bin/python3 -m pytest tests/test_ai_runtime.py tests/test_assistant.py tests/test_settings_audit_logs.py`
- Frontend Assistant regression test:
  `cd k8s-ui && yarn test:assistant`
- Lint: `cd k8s-ui && yarn lint`
- TypeScript: `cd k8s-ui && yarn tsc --noEmit`
- Final feature gate: `./scripts/verify-feature.sh`
- Verification evidence: the user-provided local `./scripts/verify-feature.sh`
  run completed successfully on 2026-09-17 with 68 focused backend tests, 13
  Assistant tests, successful Next.js compilation, TypeScript completion, page
  data collection, static generation, and production optimization. Full
  `yarn lint` completed with zero errors (13 existing warnings), and
  `yarn tsc --noEmit` passed. An earlier restricted agent environment could not
  bind Turbopack's worker port; the capable local run supersedes that limitation.

## Notes for the AI

- Keep FastAPI as the only Kubernetes/Helm execution boundary. Direct AI
  providers receive model conversation/tool schemas only, never cluster
  credentials or permission authority.
- Reuse the existing `/api/v1/assistant/models` contract and model capability
  schema instead of introducing browser-authored capability flags.
- Preserve all existing bounded request/stream sizes, provider URL validation,
  credential decryption, no-redirect behavior, session checks, proposal
  one-use semantics, and safe error normalization.
- Make stream audit finalization idempotent so normal completion, disconnect,
  exception handling, and response cleanup cannot create duplicate terminal
  events.
- Tool output remains untrusted model input. Do not record it in audit context
  or render it outside the existing sanitized UI path.
- Do not add feature 22 integrations or generalize this work into a new agent
  framework.
