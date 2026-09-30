# KubePilot - Project Overview

<!-- blueprint:source-hash 02066d2690beda7a31f5fc24e38fedbfc1056ae7ef362ad5de9562d63ce888b4 -->

> A self-hosted Kubernetes operations platform for cluster visibility, troubleshooting, and safe resource management.

## Problem

Kubernetes operations teams need cluster health, failure investigation, and
resource management without switching constantly between terminals and
fragmented dashboards. KubePilot keeps Kubernetes as the operational source of
truth while presenting scoped, decision-oriented workflows in one interface.

## Users

- DevOps, platform, and SRE engineers operating clusters and investigating workload failures.
- Engineering managers and technical operators who need higher-level health visibility.
- Signed-in users operate through local RBAC: admins manage users and application configuration, operators perform allowed operational actions, and viewers remain read-only.

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
9. **Minikube deployment** - containerized services, manifests, in-cluster configuration, and RBAC.
10. **Real-time refresh and health updates** - refreshable data and alerting cues.
11. **Live metrics and observability** - node, workload, storage, Metrics API, and utilization views.
12. **Users, authentication, and RBAC** - three roles, lifecycle controls, password policy, permissions, and audit logging.
13. **Multi-cluster support** - registered cluster management, routing, selection, and scoped API calls.
14. **AI-Powered SRE/DevOps Assistant** - streaming investigations and human-approved operations through typed tools; FastAPI remains the only Kubernetes/Helm integration layer.
15. **shadcn/ui and table migration** - reusable Data Table components within the visual system.
16. **Header and theme support** - shadcn header controls and light/dark themes.
17. **UI polish and design consistency** - light operational palette, grouped navigation, shared shell, and cluster context.
18. **KubePilot Marketplace** - Artifact Hub discovery, installation jobs, progress/history, and release actions.
19. **Manage resources** - validated Kubernetes resource operations plus Helm release, repository, and upgrade workflows.
20. **Centralized KubePilot Settings** - administrator-controlled provider/model configuration, credentials, preferences, and audit logs.
21. **Direct AI provider architecture** - Settings-backed OpenAI, OpenRouter, and Ollama/local models without the AI Gateway, with capability enforcement and safe audit outcomes.
22. **Integrations and AI agent automation** - parent milestone remains open while AI agent automation is completed.
   - **22a. Secrets and API key management** - shipped admin-only metadata and write-only management of registered credentials.
   - **22b. Integrations catalog UI foundation** - shipped catalog, filters, search, status groupings, and preview actions for supported and future connectors.
   - **22c. Integration connections and delivery** - shipped backend-authoritative Slack, Gmail, and Outlook connection lifecycle and delivery/status foundations.
     - **22c1. Integration connection lifecycle** - shipped encrypted token references, OAuth/manual connection flows, scoped permissions, tests, safe status, and audit; Teams, GitHub, and Webhooks remain catalog-only.
     - **22c2. Integration delivery and status** - shipped queued delivery, idempotency, bounded retries, safe errors, history, and audit visibility.
   - **22d. AI agent workflows in Assistant** - parent slice remains open; shared admin-managed agents and caller-scoped manual execution are shipped through 22d3.
     - **22d1. Agent management** - shipped shared agent CRUD, enable/disable, instructions, identity, and Settings-managed model selection at `/assistant/agents`.
     - **22d2. Skills, capabilities, and templates** - shipped reusable instruction skills, supported tool assignments, effective permissions, and template creation.
     - **22d3. Agent execution** - shipped manual ToolLoopAgent execution with AI Elements streaming, scoped tools, and human approvals.
     - **22d4. Agent integrations** - shipped explicit Slack/Gmail/Outlook notification destinations, encrypted targets, admin test delivery, status refresh, safe delivery metadata, and audited results.
     - **22d5. Schedules and events** - next: configure/pause triggers and inspect runs while rechecking designated-owner permissions per run; unattended actions remain limited to investigation and configured notifications.

## Data model

Kubernetes is the source of truth for live cluster objects. PostgreSQL stores
application identity, configuration, durable job metadata, and bounded audit or
workflow state.

### UserAccount and Session

- `UserAccount`: `id` (UUID), unique `email`, password state/hash, `role` (`admin`, `operator`, `viewer`), active state, and password-expiration metadata.
- `Session`: `id`, user relationship, signed-session token hash, expiry, and revocation state.
- The browser receives only the signed HTTP-only session cookie; FastAPI resolves identity from PostgreSQL.

### ClusterConnection and UserPreference

- `ClusterConnection`: `id`, name, kubeconfig reference or in-cluster configuration, active/status metadata, and cluster-scoped connection details.
- Namespaces, live resources, events, metrics, Helm releases, jobs, and Assistant scopes resolve through the selected cluster.
- `UserPreference`: unique `user_id`, default namespace, and supported view/theme settings JSON.

### Runtime settings and credentials

- Runtime settings store typed application preferences, default cluster/namespace behavior, AI defaults, feature toggles, and global appearance/provider configuration. Kubernetes bootstrap variables remain outside this store.
- `EncryptedCredential`: registered credential key, encrypted secret material, creator/updater metadata, and timestamps. Values are write-only through normal APIs and encrypted with the Kubernetes-managed master key.
- `AIProviderConfig`: allowlisted provider kind, validated endpoint/configuration, enabled state, and credential reference.
- `AIModelConfig`: provider ownership, external model ID, friendly name, enabled/default state, capability flags such as `tools` and `streaming`, and availability status.

### Integrations and delivery

- `IntegrationConnection`: unique provider ID, connection status, encrypted access/refresh token references, granted scopes, external account metadata, error/test timestamps, and actor/timestamp metadata.
- `IntegrationDeliveryJob`: provider, event type, encrypted bounded payload, safe destination hint, idempotency key, status (`queued`, `running`, `succeeded`, `failed`, `outcome_unknown`), attempt counters/timestamps, safe error code, actor, and optional agent/destination source IDs.
- `AIAgentNotificationDestination`: agent foreign key, provider ID, label, encrypted normalized target, destination digest, safe hint, enabled state, actor IDs, and timestamps. It is unique per agent/provider/normalized destination; raw targets never return to the browser.

### AI agents and operations

- `AIAgent`: shared installation-level identity, description/instructions, internal model reference, enabled state, creator/updater references, and timestamps.
- Agent skills contain bounded instructions; assignment rows connect agents to skills and supported tools. Templates provide safe draft values and cannot grant permissions or executable code.
- Future 22d5 state adds trigger configuration, designated owner, and bounded run history. Exact trigger types, schedule semantics, retention, and background approval handoff remain open until that spec.
- `AuditAction`: actor, action, target identity, result, and safe context; never raw prompts, credentials, notification bodies, or raw tool payloads.
- `AssistantProposal`: UUID, actor/session, immutable validated action arguments and cluster, expiry, one-use decision state, and sanitized result. Conversations remain in the active browser view.
- `InstallationJob` and Helm repository records support package/release actions with target cluster, namespace, release/action metadata, status, errors, timestamps, and public URL-only repository configuration.

## Tech stack

- **Next.js 16, TypeScript, Tailwind CSS, shadcn/ui** - UI, application shell, and same-origin API routes.
- **FastAPI** - authentication, RBAC, application APIs, Kubernetes/Helm access, and background job boundaries.
- **PostgreSQL and Alembic** - durable metadata, sessions, settings, audit records, and jobs.
- **Kubernetes Python client** - all live cluster access through FastAPI and registered cluster scope.
- **Vercel AI SDK and AI Elements** - Assistant streaming and ToolLoopAgent integration.
- **Direct provider adapters** - server-side OpenAI, OpenRouter, and Ollama-compatible model access; credentials stay server-side.
- **Artifact Hub and Helm** - public package discovery and validated backend release operations.

## Monetization

KubePilot is a self-hosted operations product with potential open-core or
enterprise licensing, paid support/onboarding, premium operational modules,
managed hosting, or turnkey deployment. V1 prioritizes operational value and
reliability.

## UI/UX

The shipped direction is a calm, readable, light operational interface with
strong status emphasis, responsive desktop-first layouts, accessible loading,
empty, denied, and error states, and light/dark theme selection.

- `/` and `/login` - branded entry and local sign-in.
- `/dashboard` and `/dashboard/detail` - scoped cluster health, resources, status, YAML, logs, and events.
- `/marketplace` - Artifact Hub search, package details, install configuration, progress, and history.
- `/manage-resources` - Kubernetes resources, Helm releases, repository configuration, and upgrades.
- `/assistant` - authenticated streaming investigation, scoped tool results, proposals, and confirmations.
- `/assistant/agents` - searchable shared agent list/detail, guided creation, skills, capabilities, templates, execution, and notification destinations; 22d5 adds automation.
- `/settings` - protected administrator Settings for Providers, Models, Integrations, Credentials, and Audit Logs.
- `/settings/integrations` - catalog plus Slack/Gmail/Outlook connection and delivery management; catalog-only entries do not imply supported connectors.
- `/settings/credentials` - admin-only metadata and write-only management of registered secrets.
- `/api/*` - same-origin Next.js bridges that forward only the signed session cookie where backend access is needed.

## Deployment

The target is self-hosted deployment on-premise, in a private cloud, or in
customer-managed Kubernetes. The topology is a Next.js frontend, FastAPI
backend, PostgreSQL database, and background worker for Helm/delivery jobs;
Minikube manifests provide the local deployment path.

- Bootstrap configuration includes cluster/admin settings, database connection details, shared session signing/session settings, backend URL, and the Kubernetes-managed encryption key.
- Mutable provider/model settings and provider credentials use PostgreSQL-backed encrypted storage.
- FastAPI is the only application component that reaches Kubernetes or executes Helm. Kubernetes credentials never reach the browser or AI providers.
- Development/build/start commands and the concrete health-check endpoint are not specified in the plans: > TODO: add canonical commands and health path to `project-plan.md`.
- Domain and hosting remain private or enterprise-ready, likely behind internal access controls.

## Open questions

- Confirm whether the commercial offering is self-hosted only, managed, or both.
- Carry exact ServiceAccount/RBAC and protected-system-namespace policies into future operation specs.
- Specify 22d5 trigger types, schedule semantics, run retention, and authenticated background approval handoff before implementation.
- Add canonical development/build/start commands and the concrete health-check path to `project-plan.md`.
