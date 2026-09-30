# In-chat model and agent mode switching

**Type:** Feature 22d7
**Status:** completed
**Branch:** `feature/in-chat-model-and-agent-mode-switching`

## Goal

Make the Assistant’s two existing execution modes discoverable from one chat
surface. Operators can choose either a direct eligible model or an enabled
configured AI agent without navigating to `/assistant/agents` first.

## Delivered

- Added explicit `Direct chat` and `Agent chat` selection to the shared Assistant surface.
- Preserved the eligible-model selector and added enabled-agent selection with safe identity/status metadata.
- Added URL state for mode and selected model/agent, including legacy `?agent=<id>` deep-link compatibility.
- Confirmed before clearing a non-empty in-memory conversation when changing mode, model, or agent.
- Kept direct requests exclusive to `modelId` and agent requests exclusive to `agentId`; server-side resolution and authorization remain authoritative.
- Preserved loading, empty, denied/disabled, error, retry, cancellation, cluster context, and responsive header behavior.
- Added focused contract tests for selection parsing, URL replacement, and identity exclusivity without adding persistence or backend model changes.

## Scope boundaries

No conversation persistence, agent configuration changes, provider changes, permission changes, or backend data-model changes were introduced. Agent instructions, tools, permissions, model configuration, approvals, and audit boundaries continue to resolve on the server.

## Verification

- `./scripts/verify-feature.sh` passed: 31 Assistant/agent tests and the Next.js production build.
- TypeScript and targeted ESLint checks passed for the changed Assistant files.
- `graphify update .` completed after the implementation changes.

## Manual review path

Open `/assistant`, switch Direct chat to Agent chat, select an enabled agent, send a read-only prompt, switch back, confirm the reset warning, and verify direct model selection returns.
