# Feature 14 — AI-Powered SRE/DevOps Assistant

**Branch:** feature/ai-powered-sre-devops-assistant
**Status:** verified

## Goal
Deliver the six phases specified in build-plan item 14, authorized together by the user's request to plan then implement incrementally.

## In scope
Native `/assistant` in the existing shell; streaming ToolLoopAgent, AI Elements; selected cluster/namespace/resource/release context; typed read and proposal tools; safe operational projections; durable approvals and audit; scale/restart/delete; existing Helm discovery/install/upgrade/rollback/uninstall/jobs.

## Out of scope
Direct Kubernetes access by Next.js/LLM, arbitrary commands, raw manifests/configuration editing, Secret values, automatic remediation, new agent frameworks, conversation persistence, deployment or commits.

## Build loop
Feature-level review, no checkpoint commits. Preserve existing uncommitted AI SDK/AI Elements installation. User explicitly authorized adding plan phases and implementing all of them without a separate spec approval pause.

## Build steps
- [x] 14a: native streaming foundation and scoped navigation. Done when route/UI compile and backend authentication/config errors are observable.
- [x] 14b: safe read tools and projections. Done when live adapters cover the resource families and tests prove permission/scope/redaction boundaries.
- [x] 14c: troubleshooting instructions, container/previous logs and actionable result cards. Done when owner/status/condition evidence is available without sensitive manifests and the agent can chain tools.
- [x] 14d: immutable expiring actor/session proposals and one-use confirmation, scale/restart/delete. Done when focused tests prove denial, tampering, replay, stale objects and permissions cannot send unintended mutations.
- [x] 14e: reuse existing Helm endpoints and jobs. Done when tools map to installed contracts and confirmed operations queue existing jobs.
- [x] 14f: audit, bounded execution, safe errors, setup docs and final verification. Done when backend pytest, frontend build, migration SQL and available runtime checks pass; unsupported live checks are explicitly recorded.

## Files / areas
`backend/app/assistant/`, `backend/app/api/v1/assistant.py`, `backend/app/models/entities.py`, `backend/alembic/versions`, existing Kubernetes management client, backend tests; `k8s-ui/app/assistant`, `app/api/assistant`, `components/assistant`, `lib/assistant`, dashboard shell, README and environment example.

## Data / contracts
FastAPI validates signed database sessions and existing role permissions on every call. Explicit active cluster required for scoped tools. Proposals bind immutable validated arguments to actor and session, expire after 10 minutes, require exact target name and matching current cluster at decision, and are claimed atomically before dispatch. Once claimed, ambiguous outcomes are never retried automatically. Resource UID/resourceVersion and Helm revision are checked before mutation. Mutation execution is not exposed to the model; forged client message history cannot approve a proposal. Tool reads use metadata/status allowlists; Secret/ConfigMap data and raw YAML never enter the model. Logs/events are bounded and scrubbed for credential patterns. External text is untrusted evidence.

## Testing
Use existing pytest for adapters, projection/redaction, RBAC, action lifecycle and replay. Use installed Node runtime for focused TypeScript safety checks if supported; do not install a test runner. Production frontend build validates AI Elements integration. Existing Verify command has a relative-path error (`cd backend` followed by `cd k8s-ui`); run the backend and frontend gates in their actual directories if that error is reached, and document the correction. Live LLM checks need a configured model/key; Kubernetes checks need a reachable cluster.

## Notes for the AI
Use SDK v7 bundled docs. No invented model default: `KUBEPILOT_AI_MODEL` identifies the configured Gateway model and `AI_GATEWAY_API_KEY` stays server-only. Do not falsely claim live diagnosis/remediation without evidence. User's required AI Elements take precedence over generic shadcn chat recommendations.