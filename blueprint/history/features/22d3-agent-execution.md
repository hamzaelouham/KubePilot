# Feature 22d3 - Agent execution

**Type:** Feature
**Build plan:** 22d3
**Branch:** `feature/agent-execution`
**Status:** Verified

## Goal

Let an authenticated Assistant user select a shared admin-managed agent and run
it through the existing Vercel AI SDK `ToolLoopAgent` and AI Elements streaming
surface. The agent's persisted model, assigned skills, and assigned tools are
resolved server-side; the effective operational tool set is the intersection of
those assignments, the model's declared capabilities, and the caller's current
FastAPI permissions. Existing cluster scope, sanitized reads, proposal-only
writes, and explicit human approval remain authoritative.

## In scope

- Launch a selected agent from `/assistant/agents` into the existing Assistant
  conversation experience, preserving the selected registered cluster and
  namespace context.
- Support manual, foreground runs only: prompt the agent, stream text and tool
  states, stop/cancel a run, start a new conversation, and follow up in the same
  session.
- Resolve the agent's persisted Settings-managed model and compose its stored
  instructions with its assigned reusable skill instructions and the existing
  Assistant safety instructions.
- Compute an effective tool allowlist from the persisted assignments, model
  support, and the authenticated caller's permissions. A model without tool
  support may still provide conversational output, but receives no operational
  tools.
- Reuse the existing typed Kubernetes/Helm tools, sanitized FastAPI routes,
  proposal records, confirmation UI, audit behavior, and direct provider/model
  resolver.
- Provide clear loading, empty/no-effective-tools, unavailable-model, denied,
  invalid-scope, cancellation, streaming, tool, approval-waiting, success, and
  unexpected-error states.

## Out of scope

- Slack, Gmail, or Outlook notifications; these belong to 22d4.
- Schedules, event triggers, designated-owner execution, run history, or
  unattended/background execution; these belong to 22d5.
- New agent, skill, tool, run-history, or conversation persistence.
- New Settings navigation or an AI Agents configuration surface in Settings.
- New Kubernetes/Helm tools, arbitrary code execution, shell access, raw
  manifests, credentials, Secret/ConfigMap contents, or permission grants from
  agent instructions or skills.
- Automatic approval or execution of a proposed change. Proposal tools may only
  create the existing expiring review record; the separate authenticated
  confirmation path remains the only execution boundary.

## Build loop

- Follow `workflow.stepReview: "feature"`: implement the small steps, then
  present one feature-level review packet.
- `checkpointCommits` is disabled; no checkpoint commit is offered.
- Work is local on `feature/agent-execution`. `/complete` owns the final feature
  commit and merge approval.

## Build steps

- [x] **1. Add a server-authoritative agent runtime projection.** Extend the
  existing agent service/API seam so an Assistant execution request can resolve
  one shared agent for the authenticated caller without widening admin-only
  create/edit/delete permissions. Return only the runtime data needed by the
  Next.js server: agent identity/description, persisted model reference and
  capability state, ordered skill instructions, and the effective capability
  projection. Do not accept client-supplied instructions, model IDs, tool IDs,
  roles, cluster scope, or permissions.

  **Done when:** a valid agent ID resolves through the existing session and
  Assistant authorization boundary; a missing, disabled, deleted, unavailable,
  or non-streaming model produces a safe actionable error; effective tools are
  `assigned ∩ model_support ∩ actor_permission`; and backend tests cover admin,
  operator, and viewer permission intersections without changing the existing
  agent-management authorization.

- [x] **2. Build the agent-aware ToolLoopAgent path.** Extend the existing
  `k8s-ui/lib/assistant/agent.ts`, `tools.ts`, `instructions.ts`, and schemas as
  needed to create a run from the resolved projection. Keep the fixed Assistant
  safety instructions authoritative, add agent and skill text as bounded
  configuration, filter the tool registry to the server-computed allowlist, and
  preserve the existing ten-step/3,000-token/no-retry runtime limits unless a
  focused test demonstrates that the current limits cannot support this feature.

  **Done when:** the constructed agent exposes only effective assigned tools;
  no `execute` or `approve` tool exists; proposal tools still create review
  cards rather than mutations; tool calls retain the selected cluster and
  explicit namespace scope; conversational-only and zero-effective-tool runs
  stream safely; and unit tests prove agent instructions cannot add tools,
  permissions, credentials, or approval authority.

- [x] **3. Wire agent selection into the existing streaming route and UI.** Add
  an agent-mode request to the existing `/api/assistant` transport (or the
  narrowest repository-native streaming bridge), with an `agentId` UUID as the
  only new client selector. The server must resolve the agent and its model from
  FastAPI/Settings, ignore or reject client model/tool/instruction overrides, and
  return the existing AI SDK UI stream and error envelope. Add a `Run in
  Assistant` entry from `/assistant/agents`, an agent context indicator, and
  reset behavior when the agent, cluster, or namespace changes. Reuse AI Elements
  conversation, tool, confirmation, loading, stop, and error components.

  **Done when:** a signed-in Assistant user can launch an enabled agent, submit a
  prompt, see streamed text and tool states, stop it, start a new conversation,
  and continue a scoped follow-up; switching agent or scope starts a fresh
  conversation; unavailable/denied/missing agents and models show actionable
  feedback; and no raw agent instructions, credentials, or untrusted tool data
  are rendered as executable markup or sent to the browser unnecessarily.

- [x] **4. Add regression coverage and complete the feature gate.** Extend the
  existing backend agent/Assistant tests and frontend `test:assistant` or agent
  tests for runtime resolution, capability intersection, authoritative model
  selection, scoped tool calls, conversational-only fallback, proposal-only
  writes, cancellation/error states, forged client overrides, and safe upstream
  errors. Run the declared `./scripts/verify-feature.sh`, recording the focused
  tests, build result, and any environment limitation without weakening the
  gate.

  **Done when:** focused backend and frontend tests pass, the production build
  passes, the feature's manual review path is documented in the implementation
  handoff, and the final Verify command has no unwaived failure.

## Files / areas

- `k8s-ui/app/api/assistant/route.ts` and the existing Assistant page/transport
  for the server-side agent selector and UI stream.
- `k8s-ui/app/assistant/page.tsx`,
  `k8s-ui/components/assistant/conversation.tsx`,
  `k8s-ui/components/assistant/agents/{catalog,view}.tsx` for launch, scope,
  state, and follow-up behavior.
- `k8s-ui/lib/assistant/{agent,agents,agents-proxy,instructions,models,schemas,tools}.ts`
  for typed runtime resolution, instruction composition, and allowlisted tools.
- `backend/app/services/agents.py`, `backend/app/api/v1/agents.py`,
  `backend/app/api/v1/agent_schemas.py`, and the existing Assistant/catalog
  authorization seams for the server-authoritative runtime projection.
- `backend/tests/test_agents.py`, `backend/tests/test_assistant.py`,
  `k8s-ui/tests/agents.test.mjs`, and `k8s-ui/tests/assistant.test.mjs` for
  focused security and streaming regression coverage.
- Existing `AIAgent`, skill, assignment, `AIModelConfig`, and proposal tables
  are reused; this feature should not add a migration.

## Data / contracts

- Agent-mode requests extend the existing Assistant request with
  `agentId: UUID` plus the existing strict `context` and validated UI message
  protocol. The client does not send authoritative instructions, skills,
  `toolIds`, role, permissions, cluster credentials, or a replacement model.
- The persisted agent `model_id` is authoritative in agent mode. The server
  resolves an enabled, available, streaming-capable internal model through the
  existing Settings/direct-provider resolver. A client `modelId` cannot select
  another provider model for the agent.
- The runtime projection contains only the agent's safe identity/description,
  persisted instruction text, ordered assigned skill instructions, model
  capability metadata, and effective tool IDs/statuses. Provider credentials,
  raw prompts, raw tool payloads, and Kubernetes secrets never enter the
  browser or audit context.
- Effective operational tools are calculated server-side as:
  `assigned tool IDs ∩ model supports tools ∩ caller currently has permission
  for`. FastAPI still rechecks authorization and scope on every tool request;
  the Next.js filter is defense in depth, not the permission boundary.
- The stream uses the existing AI SDK UI protocol. Read tools return the
  existing sanitized observations. Mutation tools create existing expiring,
  one-use proposals and surface the existing confirmation card; they never
  execute or approve a Kubernetes/Helm change.
- Use the existing safe error envelope and preserve status distinctions for
  unauthenticated/denied access, invalid UUID or context, missing agent,
  unavailable model, provider/stream failure, cancellation, and unknown
  operation outcomes. Never retry a proposal or hide an unknown result.

## Testing

- Backend: extend `backend/tests/test_agents.py` and `backend/tests/test_assistant.py`
  for runtime projections, role/permission intersections, model availability,
  selected-cluster/namespace binding, and proposal-only behavior.
- Frontend: extend `k8s-ui/tests/agents.test.mjs` and
  `k8s-ui/tests/assistant.test.mjs` for the agent launch/stream contract,
  client-override rejection, allowlisted tools, conversational fallback,
  cancellation, and safe error handling.
- Final gate: `./scripts/verify-feature.sh`.
- No repository Browser tests command is configured, so browser claims require
  direct manual evidence during `/check` or `/try`; do not claim browser proof
  from unit tests or a production build.
- Final `./scripts/verify-feature.sh` passed: backend checks were skipped because
  this feature changed no backend files, the focused frontend suite passed all
  25 tests, and the Turbopack production build completed successfully with
  TypeScript, page generation, and route optimization.

## Notes for the AI

- Preserve the existing `/assistant` authentication, same-origin checks, signed
  cookie forwarding, bounded request validation, direct provider resolver, and
  AI Elements components.
- Treat agent and skill text as configuration data, not executable code or an
  authorization source. Fixed safety instructions and backend permission checks
  outrank configured instructions and user text.
- Keep the selected registered cluster and namespace from the current Assistant
  scope. Never let an agent, prompt, tool result, or client payload switch the
  target implicitly.
- Keep admin management boundaries intact. This feature adds execution for
  shared agents; it does not make agent definitions editable by operators or
  viewers and does not add an AI Agents item to Settings.
- Keep all execution foreground and session-bound. Do not introduce schedules,
  delivery destinations, background workers, run history, or approval handoffs
  that belong to 22d4/22d5.
