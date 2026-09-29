# KubePilot - Project Overview

<!-- blueprint:source-hash daa7226c1e2d3321d7b97be6ec01eb5fb42117d640591272c8fa03b41adc877d -->

> A self-hosted Kubernetes operations platform for cluster visibility, troubleshooting, and safe resource management.

## Problem

Kubernetes operations teams need cluster health, failure investigation, and
resource management without constantly switching between terminals and
fragmented dashboards. KubePilot keeps Kubernetes as the operational source of
truth while presenting scoped, decision-oriented workflows in one interface.

## Users

- DevOps, platform, and SRE engineers operating clusters and investigating
  workload failures.
- Engineering managers and technical operators who need higher-level health
  visibility.
- Signed-in users operate through local authentication and role-based access;
  admins manage users and application configuration, operators perform allowed
  operational actions, and viewers remain read-only.

## Features

Features are ordered as tracked in `build-plan.md`; checked items are shipped.

1. **Dashboard foundation** - application shell, navigation, and resource layout.
2. **Cluster overview and mock data** - health signals, workloads, namespaces, and tables.
3. **Authentication and protected app access** - local login, sessions, and route protection.
4. **FastAPI backend foundation** - database-backed API service foundation.
5. **PostgreSQL application data model** - persistent users, sessions, clusters, settings, and operations.
6. **Kubernetes connection and namespace discovery** - live cluster access and namespace inventory.
7. **Core resource views** - pods, deployments, services, and nodes with real cluster context.
8. **Resource details and troubleshooting** - status, YAML, logs, and events.
9. **Minikube deployment** - containerized services and Kubernetes manifests/RBAC for local operation.
10. **Real-time refresh and health updates** - refreshable data and alerting cues.
11. **Live metrics and observability** - node, workload, storage, Metrics API, and UI utilization views.
12. **Users, authentication, and RBAC** - three roles, lifecycle controls, password policy, permissions, and audit logging.
13. **Multi-cluster support** - registered cluster management, routing, selection, and scoped API calls.
14. **AI-Powered SRE/DevOps Assistant** - native streaming investigation and human-approved operations through typed tools; FastAPI remains the only Kubernetes/Helm integration layer.
15. **shadcn/ui and table migration** - reusable Data Table components while preserving the visual system.
16. **Header and theme support** - shadcn header controls and light/dark themes.
17. **UI polish and design consistency** - light operational palette, grouped navigation, shared shell, and cluster context.
18. **KubePilot Marketplace** - Artifact Hub discovery, installation jobs, progress/history, and release actions.
19. **Manage resources** - validated Kubernetes resource operations plus Helm release, repository, and upgrade workflows.
20. **Centralized KubePilot Settings** - shipped administrator-controlled provider/model configuration, credentials, and audit logs.
21. **Direct AI provider architecture** - shipped Settings-backed OpenAI, OpenRouter, and Ollama/local model architecture without the AI Gateway, including capability enforcement and safe audit outcomes.
22. **Integrations and AI agent automation** - integration foundations are shipped; AI Agents under Assistant remain planned. The parent remains unchecked until all slices are complete.
   - **22a. Secrets and API key management** - shipped admin-only CRUD-style management of KubePilot-registered provider and integration credentials using metadata-only reads, write-only create/replace, and confirmed deletion.
   - **22b. Integrations catalog UI foundation** - shipped frontend-only catalog, filters, search, status groupings, and local preview actions for Slack, Teams, Gmail, Outlook, GitHub, and Webhooks.
   - **22c. Integration connections and delivery** - shipped backend-authoritative connector lifecycle and delivery/status.
     - **22c1. Integration connection lifecycle** - shipped Slack, Gmail, and Microsoft Outlook registry, OAuth, encrypted tokens, permission checks, connection tests, status, and audit; Teams, GitHub, and Webhooks remain catalog-only.
     - **22c2. Integration delivery and status** - shipped queued delivery, idempotency, bounded retries, safe errors, history, and audit visibility.
   - **22d. AI agent workflows in Assistant** - approved five-slice delivery; shared admin-managed agents, caller-scoped manual runs, and designated-owner automation.
     - **22d1. Agent management** - next: create, edit, delete, enable/disable, identity, instructions, and Settings-managed model selection at `/assistant/agents`.
     - **22d2. Skills, capabilities, and templates** - reusable instruction skills, supported tool assignments, effective permissions, and template-based creation.
     - **22d3. Agent execution** - Vercel AI SDK ToolLoopAgent execution with AI Elements streaming, scoped tools, and human approvals.
     - **22d4. Agent integrations** - explicit notification destinations through existing Slack/Gmail/Outlook connections and delivery status.
     - **22d5. Schedules and events** - configure/pause triggers and inspect runs; recheck designated-owner permissions per run. Unattended actions are investigation and configured notifications only; resource changes require authenticated human approval.

## Data model

Kubernetes is the source of truth for live cluster objects. PostgreSQL stores
application identity, configuration, and bounded operational history.

### UserAccount

- `id` (UUID) - local user identity.
- `email` (string, unique) - login identity.
- `role` (enum: `admin`, `operator`, `viewer`) - application permissions.
- `is_active` (boolean), password hash/state, and expiration metadata.
- owns sessions, preferences, audit actor records, and assistant proposals.

### Session

- `id` (UUID), user relationship, signed-session state, expiration, and revocation metadata.
- The browser receives only the signed HTTP-only session cookie; Kubernetes credentials never cross the backend boundary.

### ClusterConnection

- `id` (UUID), `name` (string), `kubeconfig reference/configuration`, and active/status metadata.
- Namespaces, live resources, events, metrics, Helm releases, jobs, and assistant scopes resolve through this identity.

### UserPreference

- `user_id` (unique foreign key), `default_namespace` (nullable string), and `view_settings` (JSON).
- Stores supported user preferences such as theme without becoming a bootstrap configuration store.

### Runtime application settings

- Typed persisted preferences for application name, default cluster/namespace behavior, operational preferences, AI defaults, feature toggles, and global appearance/provider configuration.
- Kubernetes-managed bootstrap variables remain outside this store.

### EncryptedCredential

- Server-registered provider/integration credential key, encrypted secret material, creator/updater metadata, and timestamps.
- Encryption uses a Kubernetes-managed master key; normal APIs are write-only for secret values.
- Admins may list safe configured/updated metadata, create a missing value, rotate or replace it, and delete it; APIs never reveal stored plaintext and reject arbitrary credential identifiers.

### AIProviderConfig and AIModelConfig

- Provider identity, allowlisted provider kind, validated endpoint/configuration, enabled status, and credential reference.
- Model identity, provider ownership, external model ID, enabled/default state, friendly name, capabilities (`tools`, `streaming`, optional reasoning/vision/large-context), and availability status.
- The Assistant resolves only internal administrator-enabled models and never exposes provider credentials.

### Operational and Kubernetes records

- `AuditAction` - actor, action, resource/target identity, result, and safe context; never raw prompts or credentials.
- `InstallationJob` - package/chart metadata, cluster, namespace, release, action, revision, status, errors, and timestamps; supports Marketplace and externally discovered Helm release actions.
- Helm repository configuration - global public URL-only repository name/URL and actor/timestamps; no repository credentials in 19c.
- Assistant proposal - UUID, actor/session, validated immutable action arguments and cluster, expiry, one-use decision state, and sanitized result. Conversations and raw tool data are not persisted in audit records.
- Live Kubernetes entities include namespaces, workloads, pods, deployments, services, nodes, events, logs, and metrics; cached projections remain bounded and sanitized.

### AI Agents (planned)

- Shared installation-level agent definition: identity, instruction text, internal model reference, enabled state, creator/updater references, and timestamps. Admins manage these records.
- Later slices add reusable instruction skills, supported tool assignments, templates, explicit notification destinations, schedules/event triggers, designated owner, and bounded run history. Exact persisted schemas are defined in each slice's spec.
- Skills contain instructions, not executable code. Instructions and capability assignments cannot grant permissions. Manual runs intersect configured tools with model support and the caller's current backend permissions.
- Scheduled/event runs recheck the designated owner's permissions. Existing session-bound proposals cannot be treated as background approval; 22d5 must specify the authenticated handoff.
- Persisted agent configuration is distinct from conversation history. Audit records exclude instructions, prompts, credentials, and raw tool payloads.

## Tech stack

- **Next.js 16, TypeScript, Tailwind CSS, shadcn/ui** - UI, app shell, and same-origin API routes.
- **FastAPI** - authentication, authorization, application APIs, Kubernetes, Helm, and background job boundaries.
- **PostgreSQL and Alembic** - durable application metadata, sessions, settings, audit records, and jobs.
- **Kubernetes Python client** - all live cluster access through FastAPI and scoped registered clusters.
- **Vercel AI SDK and AI Elements** - streaming Assistant UI and ToolLoopAgent integration.
- **Direct provider adapters** - server-side OpenAI, OpenRouter, and Ollama-compatible streaming; provider URLs are validated and credentials stay server-side.
- **Artifact Hub and Helm** - public package discovery and validated backend release operations.

## Monetization

KubePilot is a self-hosted operations product with potential open-core or
enterprise licensing, paid support/onboarding, premium operational modules,
managed hosting, or turnkey deployment. V1 prioritizes operational value and
reliability.

## UI/UX

The shipped direction is a calm, readable, light operational interface with
strong status emphasis, responsive desktop-first layouts, and consistent shell
controls. The existing theme system also supports light/dark selection.

- `/` and `/login` - branded entry and local sign-in.
- `/dashboard?resource=<type>&namespace=<name>` - health overview, navigation, cluster and namespace context.
- `/dashboard/detail` - resource status, YAML, logs, and events.
- `/marketplace` - Artifact Hub search, package details, install configuration, progress, and history.
- `/manage-resources` - Kubernetes resources and Helm releases tabs, repository configuration, and upgrades.
- `/assistant` - authenticated streaming investigation, scoped tool results, proposals, and confirmations.
- `/assistant/agents` (planned) - AI Agents child page under AI Assistant, with searchable list/detail layout and guided creation. Later slices add capabilities, templates, runs, integrations, and automation. Use the three supplied `blueprint/reference/settings-ai-agents*.png` references, adapting navigation to Assistant and reusing shadcn/ui themes and AI Elements. Show only real counts/statistics and ship responsive, accessible loading/empty/denied/error states.
- `/settings` - protected administrator Settings shell for Providers, Models, Integrations catalog, Credentials, and Audit Logs.
- `/settings/integrations` - catalog plus shipped Slack/Gmail/Outlook connection and delivery management; other catalog entries do not imply supported connectors.
- `/settings/credentials` - admin-only inventory and CRUD-style management for KubePilot-registered provider and integration secrets without reveal/copy behavior.
- `/api/*` - same-origin Next.js bridges that forward only the signed session cookie where backend access is needed.

## Deployment

The target is a self-hosted deployment on-premise, in a private cloud, or in
customer-managed Kubernetes. The local topology is a standalone Next.js
frontend, FastAPI backend, and PostgreSQL database deployed to Minikube with
backend ServiceAccount/RBAC and a background worker for Helm jobs.

- Development: `yarn dev` at `http://localhost:3000`.
- Build: `yarn build`; production server: `yarn start`.
- Backend: `cd backend && PYTHONPATH=. uvicorn app.main:app --host 127.0.0.1 --port 8000`.
- Container/deployment: published Docker images, Kubernetes manifests under `backend/deploy/kubernetes/`, and `./deploy.sh` or the documented Minikube wrapper commands.
- Required bootstrap configuration includes `KUBEPILOT_AUTH_SECRET`, database URL, cluster/admin settings, `KUBEPILOT_BACKEND_URL`, and the Kubernetes-managed encryption key. Mutable settings and provider credentials use PostgreSQL/encrypted storage.
- Health path: `GET /api/v1/health`.
- The browser talks to Next.js; FastAPI is the only application component that talks to Kubernetes or executes Helm. Kubernetes credentials never reach the browser or AI provider adapters.

## Open questions

- Confirm whether the commercial offering is self-hosted only, managed, or both.
- Carry the exact ServiceAccount/RBAC and protected-system-namespace policy into future operation specs.
- Specify exact trigger types, schedule semantics, run retention, and background approval handoff in 22d5 before implementation; no arbitrary or Kubernetes secret management is introduced.
