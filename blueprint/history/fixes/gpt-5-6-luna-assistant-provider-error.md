# Fix: GPT-5.6 Luna assistant provider error

**Type:** Fix

**Status:** verified

**Branch:** `fix/gpt-5-6-luna-assistant-provider-error`

## The problem

When the Assistant uses `gpt-5.6-luna`, a normal conversation fails with the generic UI error:

> The AI provider could not complete the response. Check model availability or try a new conversation. No proposed action was approved by this error.

The same Assistant flow works with `gpt-4.1-mini`, so the likely failure is not the general Assistant UI, session, or cluster tool path. The suspected cause is a model/provider capability mismatch around reasoning-capable model behavior, request parameters, tool attachment, streaming support, or OpenAI-compatible provider compatibility.

The current behavior is too generic for administrators and users. It does not explain whether the model is unavailable, misconfigured, does not support the active Assistant request shape, or needs different capability handling.

## The fix

Investigate the direct provider runtime path for Settings-selected models and make the Assistant handle `gpt-5.6-luna` safely:

- Resolve the exact failing provider request path and error boundary for `gpt-5.6-luna`.
- Send only provider/model-supported options for the selected model, especially around reasoning, streaming, and tool capability.
- Keep unsupported models conversational when safe, or return an actionable model capability/configuration error when they cannot run the Assistant request.
- Preserve the existing safety rule: provider errors must never approve, retry, or execute a proposed Kubernetes/Helm action.
- Keep `gpt-4.1-mini` and other working configured models on the existing successful path.
- Do not expose provider credentials, raw upstream error bodies, prompts, tool payloads, or internal stack traces to the browser, logs, audit records, or tests.

## Build steps

1. [x] **Reproduce and isolate the failing model path.**

   Trace the selected-model resolver, provider adapter, request payload, streaming path, and normalized error handling for `gpt-5.6-luna` versus `gpt-4.1-mini`.

   **Done when:** there is focused evidence, preferably a backend/runtime test or fixture, showing which request field, capability assumption, or provider response causes the generic Assistant failure.

2. [x] **Gate provider request options by model capability.**

   Patch the Assistant runtime/provider adapter so reasoning, streaming, and tool-related request fields are included only when supported by the selected provider/model contract. If `gpt-5.6-luna` is usable for normal chat, it should complete a normal Assistant response. If it is not usable, it should fail before the upstream call or at the provider boundary with a clear actionable configuration/capability message.

   **Done when:** `gpt-5.6-luna` no longer produces the generic provider failure for the same normal chat scenario, or the UI receives a precise safe error explaining the required configuration/capability change.

3. [x] **Lock the regression coverage and user-facing error behavior.**

   Add or update focused tests for the failed model shape, the existing `gpt-4.1-mini` working path, and the “provider error does not approve actions” invariant.

   **Done when:** tests cover both the newly fixed path and the safety boundary, and the final Verify command passes.

## Verify

- In Settings, select or keep enabled the `gpt-5.6-luna` model and send a basic Assistant chat message.
- Confirm the Assistant either streams a response or shows a specific actionable model availability/capability/configuration error.
- Confirm no proposed action is approved or executed when a provider/model error occurs.
- Repeat the same basic chat with `gpt-4.1-mini` and confirm it still works.
- Run the focused affected tests, including Assistant/runtime tests changed by the fix.
- Run `./scripts/verify-feature.sh`.
