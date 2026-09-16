# KubePilot - Project Overview

<!-- blueprint:source-hash 49a46d7f253fe983813de0b166b6c398f78be40027b9e34335c0ae24a92be40c -->

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
20. **Centralized KubePilot Settings** - administrator-controlled runtime settings, appearance, providers/models, credentials, and audit logs. Items 20a-20f are shipped.
21. **Direct AI provider architecture** - Settings-backed OpenAI, OpenRouter, and Ollama/local model architecture without the AI Gateway. Items 21a-21b are shipped; 21c remains.
22. **Integrations and AI agent automation** - deferred Slack, Gmail, Microsoft Outlook, and configurable Kubernetes AI agent workflows after provider capability and audit visibility work.

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

- Provider/integration identity, encrypted secret material, update actor metadata, and timestamps.
- Encryption uses a Kubernetes-managed master key; normal APIs are write-only for secret values.

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
- `/settings` - protected administrator Settings shell; General, Appearance, Providers, Models, Integrations, Credentials, Audit Logs, and AI Agents sections.
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

- The project plan still describes the AI integration as AI Gateway-backed with credentials exclusively in FastAPI, while build-plan items 21a-21b replace Gateway usage with direct Settings-backed providers and a server-side Next.js resolver. Align the authored plans with the shipped boundary before the remaining 21c work.
- The project plan describes a dark control-plane aesthetic, while completed UI work establishes a light palette with optional light/dark themes. Confirm the long-term default direction.
- The project plan's initial-release text still says single-cluster and multi-cluster-later, while item 13 is shipped. Update the product narrative to reflect current multi-cluster support.
- The project plan lists basic scale/restart actions, but the build plan's management scope explicitly covers validated create/delete and Helm workflows; decide whether scale/restart needs a separately planned item.
- Confirm whether the commercial offering is self-hosted only, managed, or both.
- Carry the exact ServiceAccount/RBAC and protected-system-namespace policy into future operation specs.
- Items 21c and 22 remain planned; their detailed specs must define tool capability behavior, regression coverage, integration credential boundaries, and future agent automation scope.
