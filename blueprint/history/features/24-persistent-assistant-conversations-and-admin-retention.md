# Current Feature

> **Generated file.** Holds the one feature, fix, or rollback being built right now. Run
> `/feature <number-or-name>` to spec a build-plan feature, or `/fix "<bug>"` for
> an ad-hoc fix. Use `/rollback <completed-feature>` to plan a safe reversal.
> Build one thing at a time; `/complete` archives it under `blueprint/history/`
> and resets this file.

**Branch:** `feature/persistent-assistant-conversations-and-admin-retention`

**Status:** verified

## Goal

Build account-backed, ChatGPT-style Assistant conversations that survive refreshes and are available to the authenticated user across devices. A conversation must restore its selected direct model or configured agent, cluster/namespace context, title, and ordered sanitized transcript. Administrators must have full, audited control over conversation records and retention. Persisting a conversation must not change the existing per-action human approval boundary.

## In scope

- Add durable conversation and message/part persistence owned by a user account, with stable IDs, title, timestamps, selected mode/model/agent, and cluster/namespace context.
- Add authenticated conversation APIs and Next.js same-origin bridges for creating, listing, opening, renaming, and deleting a user's conversations.
- Add a ChatGPT-style Assistant history flow: recent conversations, a stable conversation route/selection, New conversation, resume after refresh or sign-in on another device, title editing, and delete confirmation.
- Save ordered user, assistant, and tool-visible parts only after applying the existing transcript/tool sanitization rules. Store proposal references and safe proposal status/result summaries without storing credentials, kubeconfig material, Kubernetes Secret/ConfigMap values, raw provider payloads, or hidden reasoning.
- Attach the active conversation ID to direct-model and configured-agent turns, restore the saved selection/context when opening a conversation, and handle deleted/unavailable models or agents without silently changing the saved record.
- Preserve the existing actor/session-bound proposal rules. Loading a transcript or proposal reference is never approval, and a restored conversation must not replay or execute a prior tool call. A decision remains valid only through the existing authenticated, one-use proposal decision path.
- Give administrators an audited management surface and API to search, inspect, rename, delete, and purge any user's conversations, including safe owner metadata. User-level listing and mutation remain owner-scoped.
- Add an administrator-only conversation retention setting with a 30-day default and validated values from 1 through 365 days. Enforce expiration through the existing background/retention execution path and provide an explicit admin purge operation; audit setting changes, administrative reads/management, and purge results without recording message content.
- Add focused backend and frontend tests for ownership, admin access, retention, sanitization, cross-device restore, deletion, and the unchanged approval boundary.

## Out of scope

- Replacing the existing AI SDK streaming, model resolver, agent runtime, proposal, or Kubernetes tool contracts.
- Automatic approval, replay, retry, or execution of any action represented in a saved conversation.
- Browser-only persistence as the source of truth, anonymous conversations, sharing links, cross-user conversation access for non-admins, or user-configurable retention.
- Full-text indexing of unsanitized prompts/tool output, provider-side conversation storage, export/import, attachments, file uploads, or hidden chain-of-thought/reasoning persistence.
- Changing admin RBAC semantics beyond using the existing administrator permissions and adding auditable conversation-management actions.

## Build loop

Implement one step at a time on the current feature branch. After each step, run the smallest relevant backend/frontend tests and inspect the resulting diff. Before handoff, run `./scripts/verify-feature.sh`; backend application changes require corresponding backend tests, and the existing Assistant tests plus production build remain part of the local gate. Do not commit, merge, push, deploy, or approve a proposal as part of this feature.

## Build steps

1. [x] **Persistence and contracts**
   - Add the Alembic migration and SQLAlchemy entities for account-owned conversations and ordered sanitized message parts, including cascade behavior, owner/time/sequence indexes, nullable stale model/agent references, and the 30-day retention setting contract.
   - Add Pydantic request/response schemas and a service layer that enforces owner scope, administrator scope, title/context validation, bounded transcript size, deterministic ordering, and safe serialization. Reuse the existing sanitizer and make the persistence boundary reject unsupported/system/file/approval-instruction parts rather than trusting client history.
2. [x] **Backend conversation and retention API**
   - Add authenticated `/api/v1/assistant/conversations` routes for user CRUD and administrator search/inspection/management, with explicit permission checks and no raw sensitive content in list/audit responses.
   - Add typed administrator retention read/update and explicit purge operations, using the existing application-setting and audit patterns. Make expired conversation deletion transactional and idempotent, record counts/cutoffs rather than message bodies, and ensure user deletion/cluster deletion cannot leave orphaned records.
   - Extend audit event definitions and tests for owner denial, administrator access, setting changes, deletes, and purge outcomes.
3. [x] **Persist Assistant turns without weakening approvals**
   - Extend the Next.js Assistant bridge and backend/runtime integration to accept a validated conversation ID, verify ownership/admin scope, persist a sanitized user turn, and finalize the assistant/tool-visible parts on stream completion or safe failure.
   - Persist proposal references/status summaries only after they are returned by the existing proposal flow. Keep proposal actor/session checks and the immutable decision endpoint authoritative; opening a saved card must never call the decision endpoint.
   - Add server tests proving forged conversation IDs, forged transcript parts, cross-user access, stale selection IDs, and restored pending proposals cannot bypass authorization or approval.
4. [x] **ChatGPT-style frontend history and resume flow**
   - Add typed client schemas/bridges and an Assistant history/sidebar experience with loading, empty, denied, stale, delete, and error states. Use a stable conversation URL/ID and keep selected mode/model/agent/context in the server-backed record rather than only React state or query parameters.
   - Update `AssistantView`/`AssistantConversation` and the current `useChat` transport to load a selected conversation, autosave each completed turn, keep New conversation distinct from delete, and preserve a usable selection when a referenced model/agent is disabled or removed.
   - Add the administrator conversation-management view under the existing protected settings/Assistant navigation, including search, owner identity, retention control, inspect, rename, delete, and purge confirmation/results. Do not expose admin controls to non-admin users.
5. [ ] **Regression and verification**
   - Add backend tests for migration/service/API behavior, retention boundaries and cleanup, sanitized persistence, audit coverage, and the human-in-the-loop contract.
   - Extend `k8s-ui/tests/assistant.test.mjs` and any new focused UI tests for URL/history selection, restore/delete/new-conversation behavior, admin-only controls, and safe handling of unavailable selections.
   - Run `./scripts/verify-feature.sh`, record the observed result, and manually inspect the generated API/UI diff for secret leakage, owner-scope gaps, and approval regressions.

## Files/areas

- `backend/alembic/versions/` - conversation/message tables, indexes, foreign-key cleanup, and setting migration.
- `backend/app/models/entities.py`, `backend/app/models/__init__.py` - conversation and message entities/relationships.
- `backend/app/api/v1/assistant.py`, new conversation route/schema modules, `backend/app/api/v1/settings.py` or the existing admin-settings seam - authenticated conversation, retention, and purge contracts.
- `backend/app/services/` - conversation persistence/sanitization, retention cleanup, and admin management helpers.
- `backend/app/core/audit.py`, `backend/app/core/rbac.py`, and backend tests - auditable access and existing permission boundaries.
- `k8s-ui/app/api/assistant/`, `k8s-ui/lib/assistant/` - same-origin conversation bridges and validated client schemas.
- `k8s-ui/app/assistant/page.tsx`, `k8s-ui/components/assistant/view.tsx`, `k8s-ui/components/assistant/conversation.tsx`, and Assistant navigation/settings components - history, stable selection, resume, and admin management UI.
- `k8s-ui/tests/assistant.test.mjs` and backend Assistant tests - focused regression coverage.

## Data/contracts

- `AssistantConversation`: UUID, owner user ID, title, `direct`/`agent` mode, nullable selected model/agent IDs, cluster ID, optional namespace/resource context, created/updated timestamps, and retention-relevant activity timestamp. Model/agent references must tolerate later disable/delete so history remains inspectable and the UI can show an unavailable selection.
- `AssistantConversationPart`: UUID, conversation ID, monotonic sequence, allowed visible role/part type, sanitized JSON/text payload, optional proposal ID and safe proposal status/result summary, and created timestamp. The API returns ordered parts and bounded metadata; it never returns hidden reasoning, credentials, raw tool payloads, or unsanitized client history.
- User API: owner-scoped list/create/open/rename/delete; opening a conversation returns its metadata and ordered safe parts. Admin scope adds search, any-owner inspection, rename/delete, and purge, with every administrative read or mutation audited.
- Retention API: administrator-only read/update of `assistant.conversation_retention_days`; default `30`, integer range `1..365`. Purge uses the configured cutoff, returns only counts/cutoff/status, and is safe to repeat.
- Chat transport: every persisted turn carries a validated conversation ID plus the existing mode/model/agent and cluster context. The server is authoritative for ownership, selected runtime, message validation, sanitization, proposal references, and final persistence; the browser never supplies approval authority.

## Testing

- Backend: migration SQL, entity/service tests, owner/admin authorization, admin audit records, retention default/range/cutoff/purge, deletion cascades, bounded payloads, sanitizer rejection/redaction, and proposal restore/decision isolation.
- Frontend: Assistant history URL and selection helpers, loading/resume/new/delete states, autosave error handling, unavailable model/agent display, admin-only controls, and no approval call when opening a saved proposal.
- Verification command: `./scripts/verify-feature.sh`.
- Planning baseline observed before implementation: 32 focused Assistant/agent tests passed; the frontend production build was blocked by the environment with a Turbopack worker-port `Operation not permitted` error while processing `app/globals.css`.

## Notes

- The existing Assistant currently keeps `useChat` messages in React state and sends model/agent context through the `/api/assistant` transport; this feature makes the server-backed conversation ID the durable source of truth while preserving the current same-origin bridge and FastAPI authorization.
- The existing agent-run retention setting already validates 1–365 days. This feature uses the same range but a separate conversation setting and a 30-day default so administrators can control each retention domain independently.
- Administrative visibility is intentionally broad because the product decision is full admin control, but audit records must contain actor, target conversation/owner, action, result, and safe metadata—not message contents.
