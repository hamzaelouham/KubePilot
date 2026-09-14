# KubePilot - Project Overview

<!-- blueprint:source-hash e6bcf64a9d31c8fd592483c6b40d2039a8af2ff53012b110923adcb4255aba1d -->

> A self-hosted Kubernetes operations platform for cluster visibility, troubleshooting, and resource management, with FastAPI as the only application component that talks to Kubernetes.

## Problem

Kubernetes operations teams need to understand cluster health, investigate workload failures, and manage resources without constantly switching between terminals and fragmented dashboards. KubePilot brings these tasks into one interface while keeping Kubernetes as the operational source of truth.

## Users

- DevOps engineers, platform engineers, and SREs operating clusters and investigating failures.
- Engineering managers and technical operators needing higher-level health visibility.
- Anonymous users can access login only. Signed-in users have exactly one role: admin, operator, or viewer. Admins manage users; admins and operators manage resources and Helm releases; viewers remain read-only.

## Features

Features are listed in build-plan order. MVP covers 1–9; later items are post-MVP. Checked build-plan items are completed; pending leaves are 18l, 20c–20g, and 21a–21d.

1. **Dashboard foundation** — completed application shell, navigation, and resource layout.
2. **Cluster overview and mock data** — completed overview metrics, workload statuses, namespace controls, and resource tables.
3. **Authentication and protected app access** — completed local login, sessions, and protected routes.
4. **FastAPI backend foundation** — completed API and database-backed service foundation.
5. **PostgreSQL application data model** — completed persistence for users, sessions, settings, cluster metadata, and operational records.
6. **Kubernetes connection and namespace discovery** — completed cluster connection and live namespace/resource discovery.
7. **Core resource views** — completed pods, deployments, services, and node listings.
8. **Resource details and troubleshooting** — completed status, YAML, logs, and events views.
9. **Run on Minikube** — completed containerization (9a) and in-cluster deployment/RBAC (9b).
10. **Real-time refresh and health updates** — completed live refresh, alerting cues, and status updates.
11. **Live resource metrics and observability** — completed node, workload, and storage metrics (11a–c), Metrics API integration (11d), and metrics UI (11e).
12. **Users, Authentication & RBAC** — completed admin/operator/viewer roles, admin provisioning, activation, password reset/forced change, 15-day password expiration, centralized permissions, audit logging, and role-aware UI.
13. **Multi-cluster support** — completed cluster store/registration (13a), backend routing (13b), header selector (13c), and admin cluster management (13d).
14. **AI-Powered SRE/DevOps Assistant** *(headline capability)* — completed streaming assistant foundation, sanitized read-only Kubernetes investigation, evidence-based troubleshooting, human-approved resource writes, Helm lifecycle workflows, auditability, and UX (14a–14f).
15. **shadcn/ui integration and table migration** — completed reusable resource Data Tables while preserving the existing design.
16. **Header components and theme support** — completed header controls and light/dark themes.
17. **UI polish & design consistency** — completed light-palette pages, grouped sidebar, header, and cluster-aware shell.
18. **KubePilot Marketplace** — mostly completed; 18l responsive UI polish remains pending. Completed scope includes navigation, Artifact Hub discovery/search/details, install configuration/API/jobs/status/progress/history, validation, and rollback/uninstall actions (18a–k, 18m–n). Current release management is limited to releases installed through KubePilot, with previous-revision rollback and no upgrade or revision picker.
19. **Manage resources** — completed sidebar section for resource and Helm management in the selected cluster, delivered in order:

    - **19a — Kubernetes resource management:** `/manage-resources` and Kubernetes resources tab; list, create through validated YAML, and delete pods, deployments, namespaces, services, and other explicitly supported common types.
    - **19b — Installed Helm release management:** Helm releases tab; discover releases directly from the selected cluster across namespaces, including installations outside KubePilot; show status and revision history; support confirmed rollback/uninstall using the existing job, progress, and audit pipeline.
    - **19c — Helm repository configuration:** list/add/update/remove global KubePilot-managed public URL-only chart repository connections.
    - **19d — Helm release upgrades:** upgrade installed releases using an explicitly selected repository, chart, and version, with review and background job progress; do not infer or persist release source associations.

Feature 19 reuses cluster selection, namespace controls, application layout, and backend permissions. Admins/operators receive management controls; viewers remain read-only. Destructive actions require confirmation and audit records. Cluster changes refresh the displayed scope and prevent actions from using a stale target. Repository connections are Helm client configuration, not resources automatically discoverable from a cluster.

20. **Centralized KubePilot Settings** — in progress. 20a completed the administrator-controlled shell and authorization; 20b completed persisted per-user General and Appearance preferences using the existing `UserPreference` record and `next-themes`. Remaining 20c–g deliver global settings, credentials, providers/models, integrations, audit logs, and the AI Agents V2 placeholder. Bootstrap infrastructure configuration remains Kubernetes-managed.
21. **Direct AI provider architecture** — pending refactor of the existing Vercel AI SDK integration away from Vercel AI Gateway. Settings-managed configuration will resolve allowlisted OpenAI direct, OpenRouter, and Ollama/local models while preserving AI Elements, streaming, tool calling, FastAPI authorization, approval, and audit boundaries.

## Data model

Existing application records use UUID identifiers and creation timestamps; cluster-scoped records reference `cluster_connections.id`. Preserve existing authentication and cluster identity contracts when implementing feature 19.

- **UserAccount** (`user_accounts`): email (unique string), password_hash, role (admin/operator/viewer), is_active (boolean), updated_at, last_login_at, password_changed_at, password_expires_at, must_change_password. One-to-many sessions and audit actions.
- **Session**: user_id (foreign key), token_hash (unique), issued_at, expires_at, restricted (boolean for password-change restrictions).
- **ClusterConnection** (`cluster_connections`): name (unique), endpoint, kubeconfig reference/configuration, status. Associated namespaces, resources, events, and Helm jobs share its identity; credentials remain backend-only.
- **Namespace**: cluster_id + name (unique pair), status.
- **Workload**: cluster_id + namespace + kind + name (unique), status, labels (JSON), image.
- **Pod**: cluster_id + namespace + name (unique), status, ready, restarts, age.
- **Deployment**: cluster_id + namespace + name (unique), replicas, status, image.
- **Service**: cluster_id + namespace + name (unique), selector (JSON), ports (JSON), status.
- **Node**: cluster_id + name (unique), role, status, version.
- **Event**: cluster_id, namespace (nullable), kind, name, message.
- **AuditAction** (`audit_actions`): actor_id (nullable foreign key), action, resource_type, resource_id, target_user_id (nullable foreign key), result, context (nullable). Feature 19 records resource and Helm management actions with their target scope.
- **UserPreference**: user_id (unique foreign key), default_namespace, view_settings (JSON; feature 20b stores the supported theme preference here while preserving future keys).
- **InstallationJob** (`installation_jobs`): package/chart metadata, cluster_id (foreign key), namespace, release_name, action (`install`/`rollback`/`uninstall`), revision where applicable, status (`queued`/`running`/`succeeded`/`failed`/`cancelled`), error_message (nullable), started_at, completed_at. Feature 19b supports release actions without requiring a Marketplace install record; 19d adds upgrade job metadata and behavior through a compatible extension.
- **Helm repository configuration** (`helm_repositories`): global public URL-only repository name and URL, created/updated actor metadata, and timestamps; no credential fields.
- **Runtime application settings** (planned 20c–g): persisted typed application preferences such as name, default cluster/namespace behavior, operational preferences, AI defaults, feature toggles, and global appearance/provider configuration. Feature 20b currently persists only repository-confirmed user-scoped namespace and theme preferences. Bootstrap infrastructure variables remain outside this store; future global keys and serialization are to be fixed in their feature specs.
- **Encrypted credential** (planned 20c): provider/integration identity, encrypted secret material, update metadata, and timestamps. The encryption/master key is Kubernetes-managed and never stored in PostgreSQL or returned by normal GET APIs.
- **AIProviderConfig / AIModelConfig** (planned 20d–20e): extensible provider identity/configuration and model identity, provider ownership, external model ID, enabled/default state, friendly name, capabilities (`tools`, `streaming`, optional reasoning/vision/large-context), and availability status. Credentials are referenced through the encrypted credential store.
- **IntegrationDefinition** (planned 20f): typed integration ID, name, description, category, enabled flag, and status; OAuth/API credentials remain in the encrypted credential store and integration workflows are not part of Phase 1.

Kubernetes remains the source of truth for live resources and Helm releases. Marketplace job history is not a complete inventory of installed releases. Feature 19 persists application configuration, action/job metadata, and audit records needed for management and progress reporting; it reads current inventory from the selected cluster.

## Tech stack

- **Next.js, TypeScript, Tailwind CSS, shadcn/ui** — UI, reusable components, and same-origin API routes to FastAPI.
- **FastAPI (Python)** — authentication, permissions, application APIs, Kubernetes operations, and backend Helm integration.
- **PostgreSQL** — users, sessions, settings, cluster configuration, audit records, and operational jobs.
- **Kubernetes Python client** — live cluster discovery and validated resource creation/deletion through FastAPI only.
- **Vercel AI SDK and AI Elements** — bounded streaming assistant and typed, server-configured tools; Phase 2 replaces the current AI Gateway path with direct OpenAI, OpenRouter, and Ollama adapters; no additional agent framework.
- **Artifact Hub search API** — public Helm package discovery; no API key for basic public search.
- **Helm in the backend** — repository setup and installs, release discovery/history, rollback/uninstall, repository management, and upgrades. Use validated argument lists, never arbitrary user-provided commands; 19d resolves an explicitly selected chart source and version.
- **Existing background job mechanism** — installation and release mutation progress; no new Celery/RQ requirement.
- **Signed HTTP-only session cookie** — shared Next.js/FastAPI authentication contract.
- **Alembic** — compatible PostgreSQL schema migrations when persisted job/configuration contracts change.
- **Server-side credential encryption** — encrypted-at-rest provider/integration secrets using a Kubernetes-managed master key; never expose secret values to clients or logs.

## Monetization

Self-hosted operations software with potential licensing, support/onboarding, premium multi-cluster/audit modules, or managed hosting. Initial delivery focuses on product reliability and useful operations workflows before monetization expansion.

## UI/UX

Desktop-first operations interface with readable tables, status emphasis, namespace/resource navigation, and low-noise layouts. Feature 17 establishes the light palette and shared design language; feature 16 provides light/dark theme support. The project plan still describes an older dark-first direction; see Open questions.

- `/` and `/login` — branded home and local sign-in.
- `/dashboard?resource=<type>&namespace=<ns>` — resource navigation, grouped sidebar, header cluster selector, notifications, and user menu.
- `/dashboard/detail?resourceType=&name=&namespace=` — resource status, YAML, logs, and events.
- `/marketplace` — Artifact Hub package discovery, install configuration, job progress/history, and existing rollback/uninstall controls.
- `/manage-resources` — sidebar label **Manage resources**, Kubernetes resources and Helm releases tabs, repository configuration, and release upgrades within the same section. Reuse the application shell and selected cluster/namespace controls.
- `/settings` — admin-only Settings shell with secondary navigation for General, Appearance, AI Providers, Models, Integrations, Secrets & Credentials, Audit Logs, and AI Agents (V2/Coming Soon).
- `/settings/general` and `/settings/appearance` — completed 20b preference pages using the existing shell; `/settings/providers`, `/settings/models`, `/settings/integrations`, `/settings/credentials`, and `/settings/audit-logs` remain planned Settings subsections.
- `/settings/clusters` — registered cluster management.
- `/settings/users` — admin user management.
- `/settings/password` — self-service and forced password change.
- `/api/auth/*`, `/api/users/*`, and operational API routes — same-origin bridge to FastAPI.

Manage resources must show loading, empty, denied, invalid-input, and unexpected-error states, clear create/delete results, release progress, and destructive-target confirmation. Kubernetes credentials stay out of the browser. Preserve Marketplace behavior while extending live release management under feature 19.

## Deployment

Self-hosted Next.js frontend, FastAPI backend, and PostgreSQL, with completed containerization and Minikube deployment from feature 9. The customer may operate the platform on-premise, in a private cloud, or in managed Kubernetes.

- Frontend: standalone Next.js runtime; development `yarn dev`, build `yarn build`, production `yarn start`.
- Backend: FastAPI/uvicorn, database migrations on boot, and the existing Helm background worker.
- PostgreSQL: durable application data, sessions, configuration, audit records, and jobs.
- Kubernetes: backend ServiceAccount/RBAC for in-cluster access and registered cluster connections for multi-cluster routing. API credentials remain exclusively in the backend.
- Runtime/bootstrap configuration includes `KUBEPILOT_AUTH_SECRET`, `KUBEPILOT_DATABASE_URL`, `KUBEPILOT_CLUSTER_NAME`, `KUBEPILOT_ADMIN_EMAIL`, `KUBEPILOT_ADMIN_PASSWORD`, `KUBEPILOT_BACKEND_URL`, and the Kubernetes-managed encryption key required by feature 20c. Mutable provider credentials and runtime settings belong in persistent application storage, not arbitrary environment-variable editing.
- Health endpoint: `GET /api/v1/health`.
- Deployment needs secure secret handling, worker execution, health checks, and logs. Feature 19c stores only global public repository configuration; repository credentials are out of scope.

The project plan's topology text still describes multi-cluster support as future work; the completed feature 13 checklist defines the current delivery state.

## Authentication boundary

- Next.js and FastAPI share the signing secret, session cookie name, and format.
- The cookie is signed and HTTP-only; browser JavaScript and request payloads cannot mint or override identity.
- FastAPI validates signature/expiry, loads the authenticated user from PostgreSQL, and enforces permissions before protected reads or mutations.
- Each feature 19 resource/release operation must resolve its selected registered cluster and applicable namespace on the backend.
- Kubernetes credentials remain in the backend runtime, never the frontend, browser, or AI integration.
- Destructive management actions require target confirmation, backend authorization, and audit logging.

## Open questions

- **Resource scope for 19a:** the exact additional common resource types, YAML validation contract, and protected-resource/namespace policy must be defined in its spec. Pods, deployments, namespaces, and services are explicit requirements.
- **Helm contracts for 19b/19d:** define rollback targeting and upgrade values handling. 19c uses global public URL-only repositories; 19d requires explicit repository/chart/version selection and does not infer repository connections from live release inventory.
- **Scale/restart gap:** project-plan §3 lists basic scale/restart actions, but the build plan has no dedicated item. Feature 19 approves create/delete, Helm management, and upgrades; it does not silently add scale/restart.
- **UI direction mismatch:** project-plan §7 describes a dark-first aesthetic, while completed feature 17 establishes a light palette and shared shell. Preserve the existing UI for feature 19.
- **Outdated milestone text:** project-plan §8 and its assumptions still describe single-cluster operation and backend integration as future work; completed build-plan items record multi-cluster/backend delivery. Earlier MVP feature summaries also omit later shipped items.
- **Plan alignment:** the newly approved Settings (20) and direct-provider (21) scope is currently present in `build-plan.md` but not yet described in `project-plan.md`; update the authored project plan before treating the overview as a final product-direction baseline.
- **AI migration contract:** project-plan §5 still names AI Gateway as the current integration, while build-plan 21 removes it. Define migration/bootstrap precedence, key rotation, and provider/model availability contracts in the 20/21 specs.
- Exact ServiceAccount/RBAC policy and system namespace protections for new management operations must be carried into the implementation specs. Marketplace 18k already requires kube-system protection unless explicitly allowed by policy.
- Audit recording is planned/implemented across features, but a dedicated audit-log UI is not a build-plan item.
- The final self-hosted/managed-service offering remains a product decision.
