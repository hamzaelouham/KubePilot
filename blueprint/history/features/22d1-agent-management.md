# Feature 22d1 — Agent management

**Type:** Feature
**Build-plan item:** 22d1 (first of the approved 22d1–22d5 slices)
**Branch:** feature/agent-management
**Status:** Verified. All four build steps implemented and passing the focused
Verify gate. Live runtime and visual checks against the references were not
performed; they remain open for `/check` or a manual `/try` pass.

## Goal

Give KubePilot admins a persistent, usable AI Agents management page under AI
Assistant. Create, inspect, edit, enable/disable, and explicitly delete shared
agent definitions, including instructions and a Settings-managed model. This
slice configures agents; executing them is feature 22d3.

## Design reference

- [Agent list and detail](../reference/settings-ai-agents.png): searchable list,
  selected-card treatment, model identity, status, and adjacent detail editor.
- [Guided creation](../reference/settings-ai-agents-create.png): clear step
  indicator, labeled form, live preview, restrained surfaces, and review action.
- [Capabilities and templates](../reference/settings-ai-agents-capabilities-templates.png):
  visual continuity for 22d2 only; do not build those screens in this slice.

Adapt the references to **AI Assistant → AI Agents**, not Settings. Preserve the
existing dashboard shell, typography, semantic colors, theme support, and
cluster/namespace navigation. Use shadcn/ui components and installed AI Elements
where their semantics fit the agent preview; do not introduce a second design
system. No prototypes directory was found during planning.

Use a desktop list/detail layout that stacks into a navigable single column on
narrow screens. Guided creation covers Basic information, Model, and Review;
do not reproduce the screenshot's later-feature Permissions/Advanced controls.
Only display real total/enabled/disabled counts. Omit usage, success-rate,
latency, default-agent badges, template counts, and example agents. No inert
documentation buttons or future-feature tabs. Use a consistent installed icon
for agents; icon uploads, category/tag taxonomies, and agent-type modes are not
required for this first slice.

## In scope

- `/assistant/agents`, reachable as an AI Assistant child navigation item, and
  `/assistant/agents/new` for guided creation.
- Shared installation-wide agent definitions with name, description,
  instructions, internal model reference, enabled state, and audit metadata.
- Admin creation, editing, enable/disable, and confirmed deletion. Signed-in
  unrestricted operators/viewers may inspect shared definitions read-only.
- Search by name/description, selected-agent detail, real configuration counts,
  and model configuration/availability feedback.
- Backend persistence, migration, authorization, safe audit records, same-origin
  frontend API bridges, and focused tests.
- Loading, empty, no-match, invalid, denied, missing/deleted, unavailable-model,
  backend-error, saving, and deletion-feedback states.

## Out of scope

- Skills, assignable capabilities, templates, and permissions editors (22d2).
- Running agents, changing the current chat, streaming new runs, or creating
  action proposals from these definitions (22d3).
- Agent integration destinations or new connector authentication (22d4).
- Schedules, events, designated run owners, run history, and unattended execution
  (22d5). Enabling an agent does not schedule or execute anything.
- Provider/model creation, credential entry, arbitrary code/tools, shell access,
  uploaded instruction files, default-agent selection, and synthetic statistics.

## Build loop

Use feature-level review (`stepReview: feature`): implement and verify each
small step, then present one review packet. Checkpoint commits are disabled.
Do not commit from implementation; `/complete` handles the final feature commit.
All regular audit, independent-review, check, and try-guide gates are manual.
Preserve the approved, currently uncommitted plan/overview changes.

## Build steps

- [x] **1. Persist and authorize shared agent definitions.** Add the model,
  Alembic migration, typed schemas, service, router registration, and safe audit
  events. Implement list/detail/create/update/delete with server-derived actor,
  read-only non-admin access, name uniqueness, and model-reference handling.
  Verify the migration head and existing audit-category mapping before editing.
  **Done when:** focused backend tests demonstrate CRUD across independent DB
  sessions, denial for unauthorized writes, blank/duplicate/invalid-model
  rejection, atomic audit+mutation behavior, and preserved agents after model
  removal; Alembic upgrade SQL compiles without changing existing tables' data.

- [x] **2. Connect the AI Agents page and read experience.** Add protected
  page routes, authenticated API bridges, typed client contracts, Assistant
  child navigation, searchable list, real counts, and selected detail. Reuse
  shared shell and auth helpers without changing the existing chat route.
  **Done when:** the page is reachable from AI Assistant; reload reads persisted
  definitions; operators/viewers see no mutation controls and direct requests
  still fail; loading/empty/no-match/denied/backend-error/missing-agent states
  are distinguishable. Bridge tests prove cookie-only identity forwarding,
  no caching, and same-origin mutation enforcement.

- [x] **3. Build guided creation and editing.** Implement Basic information →
  Model → Review with live preview, explicit enabled selection, and persisted
  save; add editing and confirmed deletion in the detail panel. Fetch actual
  model metadata without credentials and retain invalid drafts on failures.
  **Done when:** an admin can create, reload, edit, toggle, cancel deletion, and
  confirm deletion of the named agent; failed operations do not show success.
  Validation is associated with controls, announced, and focuses the first
  invalid field. Keyboard navigation, dialog focus restoration, and prevention
  of duplicate submits work. Focused client tests cover wizard state, payload
  validation, denied/error responses, and model-change cases.

- [x] **4. Verify the integrated management experience.** Run the focused Verify
  command with the new backend test file, migration SQL check, and available
  live UI checks against the references. Read the installed Next.js guides and
  relevant shadcn component documentation before writing frontend code.
  **Done when:** Verify passes; existing Assistant tests remain green; the
  management flow works with a real backend; desktop/narrow-screen and
  light/dark states are compared with the references when browser tooling is
  available. Record actual evidence and any remaining manual visual checks.
  No execution, notifications, or cluster mutations occur from agent CRUD.

## Files / areas

Existing integration points confirmed during planning:

- `backend/app/models/entities.py`, `backend/app/models/base.py`, and
  `backend/alembic/versions/` for repository-native UUIDs and persistence.
- `backend/app/main.py` for router registration and safe error envelopes.
- `backend/app/core/rbac.py`, `backend/app/core/dependencies.py`, and
  `backend/app/core/audit.py` for actor, role, and audit boundaries.
- `backend/app/services/ai_models.py` and
  `backend/app/api/v1/settings_schemas.py` for model metadata conventions.
- `backend/tests/test_ai_models.py` and `backend/tests/test_assistant.py` for
  service/API test patterns and regression coverage.
- `k8s-ui/components/dashboard-shell.tsx`, `k8s-ui/app/assistant/page.tsx`,
  `k8s-ui/components/assistant/view.tsx`, and `k8s-ui/lib/assistant/backend.ts`
  for navigation, auth, origin/body checks, and error handling.
- `k8s-ui/app/api/settings/models/` and `k8s-ui/lib/backend.ts` as bridge patterns;
  do not inherit missing mutation-origin checks from unrelated existing routes.
- `k8s-ui/components/ui/`, `k8s-ui/components/ai-elements/agent.tsx`, and
  `k8s-ui/app/globals.css` for existing visual primitives and theme tokens.

New proposed areas: backend `api/v1/agents.py`, `api/v1/agent_schemas.py`,
`services/agents.py`, and `tests/test_agents.py`; frontend
`app/assistant/agents/`, `app/api/assistant/agents/`,
`components/assistant/agents/`, and a typed agent client under `lib/assistant/`.
Register any new client tests in the existing test command rather than adding
a new runner. Do not modify AI SDK orchestration in this slice.

## Data / contracts

The following narrow contracts define this proposed implementation; later
slices extend them through reviewed migrations rather than placeholder fields.

### Definition and lifecycle

- Server-generated UUID primary key using the repository's `PrimaryKey` type.
- Required name, description, and instructions from the creation form. Trim
  outer whitespace; reject blank values. Preserve instruction line breaks as
  UTF-8 text. Reuse the model registry's 128-character friendly-name bound for
  the agent name and the existing Assistant 256,000-byte request-body ceiling.
  Do not invent additional per-field quotas during implementation.
- Names identify agents in this shared catalog: enforce uniqueness on the
  trimmed stored name with a database constraint, not a preflight query alone.
  Equality is exact and case-sensitive; return a conflict rather than silently
  renaming. UUID remains the stable identity across renames.
- `model_id` references an existing internal `AIModelConfig` UUID. New saves
  selecting a model must validate it server-side; never accept external model
  names as IDs. Expose availability/capabilities from current model metadata,
  not copied provider secrets. Model outages must not prevent reading or
  deleting saved agents.
- Follow existing nullable-reference conventions on model deletion: clear the
  relationship rather than cascade-delete the agent. Display “Model missing”
  and require an explicit replacement before re-enabling. Never silently select
  the global default or another model. Unchanged unavailable selections may be
  retained while editing instructions or disabling an existing definition.
- Require explicit `enabled` in create/update requests; the creation form starts
  disabled following the existing model-registry configuration pattern.
  Enabled describes configuration intent, not running state or model health.
- `created_by_id`/`updated_by_id` are server-derived nullable user references,
  with repository-native timezone-aware creation/update timestamps serialized
  as ISO 8601. Deleted users do not remove shared definitions.
- Explicit deletion removes only the definition in this slice; its audit record
  remains. Cancel has no persistence effect. No soft-delete or execution cleanup
  subsystem is introduced before runs exist.

### API and authorization

- Backend collection `/api/v1/assistant/agents`: GET returns `{agents: [...]}`;
  POST returns the created item with HTTP 201.
- Item `/api/v1/assistant/agents/{agent_id}`: GET/PUT return one item; DELETE
  returns the deleted identity `{id}` after successful transaction. Missing
  items return 404; repeated delete cannot remove another item.
- Browser bridges mirror these at `/api/assistant/agents` and `/{agentId}`.
  Validate UUID paths and typed payloads, reject extra fields, forward only the
  signed session cookie, use `no-store`, and enforce same-origin mutations.
- Create/update inputs contain only name, description, instructions, model_id,
  and enabled. Server-controlled identity, actor, timestamps, credentials,
  permissions, tool definitions, and tenant claims cannot be submitted.
- List/detail include definition fields plus safe current model summary and
  server metadata. Deterministic ordering uses name then UUID. Search is local
  over the complete returned collection for this slice; counts describe the
  collection and the UI distinguishes no agents from no search matches.
- Read uses the existing unrestricted authenticated Assistant read boundary
  (`resources:read`). Mutations use the existing admin-only `settings:write`
  authorization mechanism without placing the UI under Settings. Password-change
  restrictions still apply. No new roles or user-supplied execution identities.
- Scope is the KubePilot installation, not selected cluster or a new tenant.
  Cluster selection must not duplicate, filter ownership, or alter definitions.
- Reuse `{code, message}` error envelopes: authentication/permission errors,
  404 `agent_not_found`, 409 `agent_conflict`, 422 `validation_error` for invalid
  payload/reference, and safe service-unavailable responses. No raw DB/provider
  errors or reflected instruction text in error messages.
- Commit mutation and audit atomically, roll back on failure, and enforce
  uniqueness under concurrent creation. Do not automatically retry mutations on
  ambiguous transport failure; refresh stored state before the user retries.
  Prevent duplicate submission in the UI. Existing full-replacement PUT
  semantics apply; do not claim optimistic conflict detection that is absent.
- Audit create/update/delete with actor, agent UUID, outcome, and safe change
  metadata; never store name/description/instruction payloads or credentials in
  audit context. Ensure events are visible through the existing audit view.

### UI trust and interaction

- Render user-authored fields as escaped text; preview never renders raw HTML,
  remote images, executable Markdown, or arbitrary URLs. Instructions are stored
  configuration, not permission grants or replacements for platform policy.
- Show pending states and disable duplicate actions. On save failure retain the
  draft; on toggle failure keep the authoritative prior state. Confirm deletion
  with the exact agent name; restore focus after cancel and move selection
  sensibly after success. Do not discard a dirty form when switching agent or
  leaving the wizard without a discard confirmation.
- Label fields, associate helper/errors, announce asynchronous failures, and
  focus invalid fields. Clear obsolete field errors when corrected. No models
  produces an actionable admin link to `/settings/models`, not invented choices.
- Recheck backend authorization for every mutation; hidden buttons alone are
  not authorization. Losing access stops mutation and displays the denial.

## Testing

Baseline evidence, 2026-09-29:

- The agent-run `./scripts/verify-feature.sh` passed all 13 Assistant tests but
  failed in Turbopack on local port binding (`Operation not permitted`).
- The user subsequently supplied complete successful output of the exact same
  command from the repository: all 13 tests passed, production compilation and
  TypeScript passed, and 45/45 static pages generated. This is user-provided
  baseline evidence, not an agent-observed build. It clears the planning blocker;
  no application repair or weaker Verify command is required.
- Backend pytest was correctly skipped because no backend files changed. No
  live UI, migration, model-provider, or database behavior was tested here.

Implementation verification:

- Add/update `backend/tests/test_agents.py` so `./scripts/verify-feature.sh`
  selects meaningful backend coverage. Cover persisted CRUD, role matrix,
  restricted/expired sessions, forged actors, invalid IDs, duplicate names,
  model lifecycle, no sensitive audit content, and transaction rollback.
- Extend the existing frontend Assistant test infrastructure for agent bridges
  and form state; preserve existing streaming/proposal tests.
- Run `cd backend && PYTHONPATH=. alembic upgrade head --sql` and the exact Verify
  gate. Use the appropriate documented Python environment if dependencies are
  in the repository venv; do not install or alter dependencies merely to spec.
- Available runtime proof should exercise admin CRUD and operator/viewer denial,
  refresh persistence, missing models, errors, keyboard use, themes, and narrow
  layouts. No Browser tests command exists; do not add a harness in this feature.

## Recorded verification evidence

- `./scripts/verify-feature.sh` (the configured Verify gate): selected
  `tests/test_agents.py`, 16 passed. Frontend `test:assistant` ran the existing
  Assistant suite plus the new agent tests, 20 passed, 0 failed. `yarn verify`
  compiled successfully, TypeScript passed, and 48/48 static pages generated
  including `/assistant/agents`, `/assistant/agents/new`,
  `/api/assistant/agents`, and `/api/assistant/agents/[agentId]`.
- `yarn lint` reported 0 errors (13 pre-existing warnings in unrelated files,
  none in the agent files). `npx tsc --noEmit` reported no errors.
- `cd backend && PYTHONPATH=. .venv/bin/python -m alembic upgrade head --sql`
  compiled the new `ai_agents` table and its index/constraints offline; it adds
  only the new table and does not alter existing tables.
- Full backend suite: 629 passed. `tests/test_models.py` had been failing on
  this branch before this slice because the `integration_*` tables were never
  added to its expected-table registry; `ai_agents` was added alongside them.
- `python3 -m compileall -q app` passed.
- Not verified here: no live UI, model-provider, cluster, or database run. The
  done-when clause that the management flow works against a real backend, and
  the desktop/narrow and light/dark comparison with the references, require a
  running stack and remain open for `/check` or a manual `/try` pass.

## Notes for the AI

- Use the installed AI SDK documentation and SDK skill if touching AI APIs;
  retain Vercel AI SDK and AI Elements without Gateway or another framework.
  This management slice does not need inference or provider network calls.
- Use the shadcn skill and actual installed component APIs during implementation.
  Read relevant installed Next.js guides before coding. Avoid broad upgrades,
  restyling unrelated pages, or adding screenshot-only product features.
- Future execution must intersect agent capabilities, model support, and current
  caller permissions. Future automation rechecks a designated owner's rights,
  runs investigation/notifications only, and hands mutations to authenticated
  human approval. Preserve these approved boundaries without implementing them.
- Keep user-approved plan changes intact, record evidence honestly, and stop at
  the feature review handoff. Planning creates no branch, commit, or deployment.
