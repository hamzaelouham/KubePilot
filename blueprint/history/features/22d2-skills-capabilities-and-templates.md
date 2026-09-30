# Feature 22d2 — Skills, capabilities, and templates

**Type:** Feature

**Build-plan item:** 22d2

**Branch:** `feature/skills-capabilities-and-templates`

**Status:** Verified.

## Goal

Extend the shipped `/assistant/agents` catalog with reusable instruction skills,
safe assignments of existing Assistant backend tools, effective-capability
visibility, and template-based agent creation. Configuration remains shared at
the KubePilot installation level. This feature does not execute agents, send
notifications, schedule work, or create permissions.

## Design reference

- [Capabilities and templates reference](../reference/settings-ai-agents-capabilities-templates.png) — adapt the reference to **AI Assistant → AI Agents**, using the existing shell, shadcn/ui theme, and accessible list/detail patterns.
- Keep the existing `/assistant/agents` list, detail editor, and guided creation flow from 22d1. Do not add an AI Agents entry or configuration surface under Settings.

## In scope

- A shared installation-level skill catalog with admin CRUD and authenticated read access. A skill has a name, description, instruction text, server metadata, and reusable assignment links; it is configuration text, not executable code.
- Assigning existing, allowlisted Assistant backend tool IDs to an agent. The assignment is configuration only and cannot grant a role, permission, cluster access, shell access, or a new tool.
- A server-computed capability view for the current authenticated user. It distinguishes configured tools from tools that are supported by the selected model and permitted by the existing Assistant/RBAC checks. The result is derived at read time and is never stored as a permission grant.
- Extending agent create/update/detail contracts with selected skill IDs and tool IDs while preserving 22d1 fields and backward-compatible reads.
- A read-only server-owned template catalog. Selecting a template fills a new-agent draft with safe identity/instruction defaults and allowlisted tool selections; saving remains the existing explicit admin mutation. Editing the draft never changes the template.
- Skills, assignments, and template selection in the existing AI Agents experience, with loading, empty, no-match, invalid, denied, unavailable, and unexpected-error states.
- Server-side validation, atomic persistence, safe audit records, cookie-only same-origin bridges, and focused backend/frontend tests.

## Out of scope

- Running an agent, changing the current Assistant conversation, streaming a run, or creating action proposals; those belong to 22d3.
- Slack, Gmail, Outlook notification destinations; those belong to 22d4.
- Schedules, events, designated owners, unattended execution, or run history; those belong to 22d5.
- New roles, permission names, Kubernetes/Helm access paths, cluster or namespace ownership, provider configuration, credential entry, shell access, arbitrary code, uploads, or user-supplied executable tools.
- A template editor or persisted template-management UI. Templates in this slice are server-owned presets exposed through a typed catalog; later work may add reviewed template authoring if the product plan requires it.
- A second design system, a new sidebar item, or a separate Settings route.

## Build loop

Use feature-level review: `workflow.stepReview` is `feature` and checkpoint
commits are disabled. Each step must leave the application in a coherent,
testable state. `/complete` creates the feature commit; this spec does not
authorize committing, merging, pushing, or deploying.

## Build steps

- [x] **1. Add persisted skills and safe skill lifecycle APIs.** Add the repository-native skill model, migration, typed schemas, service, and routes; reuse 22d1 installation scope, authenticated read access, admin-only mutation authorization, trimming/blank/length validation, exact case-sensitive uniqueness, server-derived actors, and atomic mutation-plus-audit behavior. Deleting an assigned skill must return a conflict until assignments are removed rather than silently changing an agent. Exclude instruction text and credentials from audit context.
  **Done when:** backend tests prove persisted CRUD across independent sessions, read-only operator/viewer behavior, denied writes, duplicate/invalid/oversized/forged input rejection, assigned-skill deletion protection, and audit rollback/redaction. `cd backend && PYTHONPATH=. alembic upgrade head --sql` compiles the migration.

- [x] **2. Add agent skill/tool assignments and effective capability resolution.** Extend the existing agent service and PUT/detail contracts with ordered skill links and allowlisted internal tool IDs. Resolve the tool catalog from the existing Assistant backend/tool boundaries; reject unknown or client-defined IDs. Return configured skills/tools plus non-persisted effective status derived from current model availability, the model's declared tool capability, and the current actor's existing Assistant/RBAC authorization. Never treat an assignment as authorization and never execute a tool in this feature.
  **Done when:** backend tests prove atomic replacement of assignments, duplicate/missing/unknown ID rejection, deterministic ordering, model/tool-capability mismatch reporting, caller permission filtering, preserved assignments when a model becomes unavailable, and no new permission or audit payload containing instructions. Existing 22d1 CRUD behavior remains green.

- [x] **3. Add the typed template catalog and draft application flow.** Expose a server-owned, deterministic template catalog containing only safe agent fields and allowlisted tool IDs. Add a bridge/client contract that validates the catalog and applies a selected template to a new-agent draft without auto-saving, changing an existing agent, or accepting arbitrary template/tool identifiers from the browser. Keep model selection explicit through the existing Settings-managed model picker and preserve the 22d1 validation rules.
  **Done when:** backend/client tests prove authenticated reads, schema validation, stable template IDs, no credential or executable payloads, draft-only application, and graceful behavior for unavailable model/tool selections. A failed save leaves the draft intact and never reports a template as persisted.

- [x] **4. Integrate skills, capabilities, and templates into the AI Agents UI.** Extend the existing `/assistant/agents` list/detail/editor with a skills management surface, capability table, effective-status explanations, and template cards based on the supplied reference. Admins can create/edit/delete skills, assign and reorder skills/tools, and start a new agent from a template; authenticated non-admins can inspect the catalog without mutation controls. Render user-authored text as escaped text, associate validation with fields, announce async errors, prevent duplicate submissions, preserve dirty drafts, and restore focus after dialogs.
  **Done when:** the focused frontend tests cover catalog loading, search/empty/no-match states, admin/read-only role presentation, template-to-draft behavior, capability reason states, denied/missing/backend errors, draft retention, and mutation status handling. No UI path invokes agent execution or changes an existing Assistant run.

- [x] **5. Verify the integrated management experience.** Run the exact project Verify command, including focused backend tests selected by changed files, `k8s-ui` Assistant/agent tests, and the production build. Run the migration SQL check when backend migrations changed. Record actual results; do not claim browser or live-provider evidence unless it is available. Preserve any external font/network limitation as a verification risk rather than weakening the gate.
  **Done when:** focused logic tests and migration SQL pass, the production build passes in an environment able to resolve the repository's existing font dependencies, and the final review packet lists changed files, commands, evidence, skipped browser/runtime checks, and remaining risks.

## Files / areas

- `backend/app/models/entities.py`, `backend/alembic/versions/`, and existing model base types for skills and assignment relationships.
- `backend/app/api/v1/agents.py`, `backend/app/api/v1/agent_schemas.py`, `backend/app/services/agents.py`, and router registration for skill/assignment contracts and authorization.
- `backend/app/core/rbac.py`, `backend/app/core/dependencies.py`, `backend/app/core/audit.py`, and the existing Assistant adapter/tool boundary for server-derived actors, permissions, tool allowlisting, and safe audit metadata.
- `backend/app/services/ai_models.py` for the existing enabled/available model and capability contract.
- `k8s-ui/lib/assistant/agents.ts`, `k8s-ui/lib/assistant/agents-proxy.ts`, `k8s-ui/app/api/assistant/agents/`, and the existing Assistant API bridge patterns for typed requests, cookie-only forwarding, origin checks, and `no-store` responses.
- `k8s-ui/components/assistant/agents/view.tsx`, `editor.tsx`, `k8s-ui/app/assistant/agents/`, and existing shadcn/ui primitives for the catalog, editor, capability table, template cards, and interaction states.
- `k8s-ui/lib/assistant/tools.ts`, `model-resolver.ts`, and `models.ts` for the existing tool/model metadata; do not create a parallel execution registry.
- `backend/tests/test_agents.py`, a focused backend test module for the new skill/assignment contracts, and `k8s-ui/tests/agents.test.mjs` for bridge, schema, draft, and UI-helper coverage.
- `blueprint/reference/settings-ai-agents-capabilities-templates.png` for the visual direction only; preserve current product navigation and theme tokens.

## Data / contracts

### Agent skill

- `id` (UUID, server-generated), `name` (trimmed string, unique and case-sensitive), `description` (string), `instructions` (UTF-8 text), `created_by_id`/`updated_by_id` (nullable server-derived user references), and timezone-aware `created_at`/`updated_at`.
- Reuse the 22d1 validation conventions for names, descriptions, instructions, request-body size, blank values, NUL rejection, and typed extra-field rejection. Do not invent a second quota system.
- Skills are installation-wide and independent of cluster, namespace, tenant, provider, and model. Instructions are displayed as escaped text and never interpreted as permissions or executable content.

### Agent assignments

- Agent-to-skill links use server-validated UUIDs, a unique `(agent_id, skill_id)` pair, and an explicit position for deterministic composition/order. Agent deletion removes only its links; skill deletion is blocked while assigned.
- Agent-to-tool links use a unique `(agent_id, tool_id)` pair. `tool_id` is an internal identifier from the existing allowlisted Assistant tool catalog, never a URL, command, provider tool definition, or arbitrary client string.
- Existing agent reads include selected skills and configured tool metadata. Effective capability fields are computed per request and are not persisted: configured, model-supported, actor-permitted, and a safe reason/status for unavailable or denied tools.
- PUT assignment updates replace the complete submitted assignment set atomically with the agent mutation and its safe audit event. A failed validation or audit write leaves the prior agent and assignment state unchanged.

### Template catalog

- Template response fields are limited to a stable internal `id`, display `name`, `description`, safe draft `instructions`, and allowlisted suggested tool IDs. Templates never contain credentials, provider URLs, raw tool definitions, permission grants, cluster data, or executable code.
- Template selection is a draft transformation only. The selected Settings-managed model remains an explicit user choice, and the final agent save goes through the existing admin authorization and validation path.
- The server is authoritative for template contents and availability. The browser may submit only a known template ID and ordinary agent fields; it cannot submit template contents or capability definitions as authority.

### Authorization and API boundaries

- Reuse 22d1's authenticated Assistant read boundary and admin-only mutation boundary; do not add roles or let hidden UI controls stand in for FastAPI authorization.
- Browser bridges forward only the signed HTTP-only session cookie, enforce same-origin mutations, use `no-store`, validate UUID/template/tool identifiers, and redact upstream failure details. FastAPI derives actor, role, model state, and effective permissions from the session/database and existing authorization helpers.
- Audit create/update/delete and assignment changes with actor, skill/agent IDs, outcome, and safe counts. Never record skill instructions, agent instructions, credentials, prompts, raw tool output, or permission-bearing client payloads.
- This feature configures future execution only. 22d3 must re-resolve model support and caller permissions at run time; no configuration response is an approval or execution result.

## Testing

- Backend: skill CRUD and assignment transactions, independent DB sessions, role matrix, session restrictions, duplicate/blank/oversized/forged values, unknown tool/template IDs, deterministic ordering, assigned-skill deletion conflict, model availability/tool capability states, audit redaction, and rollback on audit failure.
- Frontend: bridge cookie/origin/cache behavior, response/error schemas, template draft application, skill/tool validation, effective-status rendering helpers, admin versus read-only controls, loading/empty/no-match/denied/missing/error states, dirty-draft retention, and duplicate-submit prevention.
- Run `./scripts/verify-feature.sh` as the final automated gate. The baseline run before this spec passed both Assistant test files (2 suites, 2 tests) and skipped backend tests because no backend files had changed; `next build` then failed while fetching the existing Geist and Geist Mono Google Fonts because `fonts.googleapis.com` was unavailable. This is observed environment evidence, not a reason to weaken verification.
- No Browser tests command is configured, so do not add a browser harness in this feature. Any live UI, database, provider, or visual-reference proof must be labeled separately if performed through `/check` or `/try`.

## Notes for the AI

- Keep all work on `feature/skills-capabilities-and-templates`; do not implement 22d3, 22d4, or 22d5 early.
- Preserve the installation-wide scope from 22d1. Cluster selection must not filter, duplicate, or authorize agent/skill definitions.
- Do not modify the existing ToolLoopAgent execution path, proposal approval routes, integration delivery, or Settings navigation except where a typed read-only contract is required to expose current capability metadata.
- Prefer the existing 22d1 service, schema, bridge, shadcn, audit, and test patterns. Any new tool metadata must be an allowlist extension reviewed against the existing backend authorization boundary, never a client-defined registry.
- The current Verify build has an external Google Fonts fetch prerequisite. If it remains unavailable at implementation time, report the exact failure and stop before `/complete`; do not replace the gate with a weaker command.
