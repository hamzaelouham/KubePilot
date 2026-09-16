# Fix: OpenAI reasoning models cannot use Assistant tools

**Type:** Fix
**Status:** verified
**Branch:** `fix/openai-reasoning-model-tool-requests`

## The problem

OpenAI reasoning-class models such as `gpt-5.6-luna` and `gpt-5.6-terra` reject
Assistant requests with `400 invalid_request_error`:

> Function tools with reasoning_effort are not supported for gpt-5.6-luna in
> /v1/chat/completions. To use function tools, use /v1/responses or set
> reasoning_effort to 'none'.

KubePilot's Assistant always sends tools (`ToolLoopAgent`), so every request to
a configured reasoning model fails before any reply. The runtime maps the `400`
to a generic "model rejected the request" error that hides the real cause.

Commit `6bbf3db` already normalizes reasoning-model request options
(`max_completion_tokens`, dropped `temperature`/penalties) and maps `400/422`
to a readable message, but nothing sends `reasoning_effort`, so the provider
still rejects the tool call.

## The fix

In the OpenAI-compatible chat runtime, when the resolved model is an OpenAI
provider model, declares reasoning capability, and the request carries tools,
set `reasoning_effort` to `"none"` unless the client already supplied a value.
Add `reasoning_effort` as an explicit passthrough field on
`ChatCompletionsRequest` (the schema is `extra="forbid"`), so an explicit
client value (`none`/`low`/`medium`/`high`) is honored and forwarded.

Scope the injection to OpenAI + reasoning + tools only. Ollama, OpenRouter, and
non-reasoning OpenAI models such as `gpt-4.1-mini` keep their current payloads.

## Build steps

### 1. [ ] Add `reasoning_effort` passthrough and inject `"none"` for OpenAI reasoning tool calls

- `backend/app/assistant/schemas.py`: add
  `reasoning_effort: Literal["none", "low", "medium", "high"] | None = None`
  to `ChatCompletionsRequest`.
- `backend/app/services/ai_runtime.py`: in `_provider_payload`, for the OpenAI
  provider when `supports_reasoning` and tools are present, set
  `outbound.setdefault("reasoning_effort", "none")`.
- `backend/tests/test_ai_runtime.py`: cover injection, absent for
  non-reasoning/OpenRouter, and explicit-value passthrough.

Done when:

- An OpenAI reasoning model with tools gets `reasoning_effort: "none"` in the
  outbound request and streams a reply (verified against `gpt-5.6-luna`).
- Non-reasoning OpenAI (`gpt-4.1-mini`) and OpenRouter requests carry no
  `reasoning_effort`.
- An explicit client-sent `reasoning_effort` value is forwarded unchanged.
- Existing runtime behavior and tests remain unchanged.

## Verify

- `cd backend && python3 -m pytest`.
- `cd backend && PYTHONPATH=. alembic upgrade head --sql` (schema-only).
- `./scripts/verify-feature.sh`.
- Rebuild and roll the backend image, then chat against `gpt-5.6-luna` through
  `minikube service kubepilot-ui -n kubepilot` until a real request streams
  and a tool call (e.g. pod inspect) runs.

## Verification status

- Focused runtime tests:
  `cd backend && .venv/bin/python3 -m pytest tests/test_ai_runtime.py -q` -> `22 passed`.
- Full backend suite: `cd backend && .venv/bin/python3 -m pytest -q` -> `576 passed`.
- Verify gate: `./scripts/verify-feature.sh` -> exit 0 (backend focused test,
  Assistant test, production build all pass).
- Done-when 1 evidence: during diagnosis an OpenAI call with tools and
  `reasoning_effort: "none"` streamed `200` for both `gpt-5.6-luna` and
  `gpt-5.6-terra`; the code injection is covered by the focused unit tests.
  Live re-deploy of the backend image on minikube to exercise the new build
  end-to-end is pending (deploy action, outside this commit).