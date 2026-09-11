# KubePilot - Project Overview

<!-- blueprint:source-hash f43d2e6f8c1c2be38a803fe0f439b897920db8bd9b009ff93f945244ed843d2b -->

> A self-hosted Kubernetes operations platform for cluster visibility, troubleshooting, and resource management, with FastAPI as the only application component that talks to Kubernetes.

## Problem

Kubernetes operations teams need to understand cluster health, investigate workload failures, and manage resources without constantly switching between terminals and fragmented dashboards. KubePilot brings these tasks into one interface while keeping Kubernetes as the operational source of truth.

## Users

- DevOps engineers, platform engineers, and SREs operating clusters and investigating failures.
- Engineering managers and technical operators needing higher-level health visibility.
- Anonymous users can access login only. Signed-in users have exactly one role: admin, operator, or viewer. Admins manage users; admins and operators manage resources and Helm releases; viewers remain read-only.

## Features

Features are listed in build-plan order. MVP covers 1–9; later items are post-MVP. Checked build-plan items are completed; pending items remain explicitly identified here.

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
14. **AI Copilot for Kubernetes operations** — pending natural-language investigation and approved actions; first unchecked item in numeric build order.
15. **shadcn/ui integration and table migration** — completed reusable resource Data Tables while preserving the existing design.
16. **Header components and theme support** — completed header controls and light/dark themes.
17. **UI polish & design consistency** — completed light-palette pages, grouped sidebar, header, and cluster-aware shell.
18. **KubePilot Marketplace** — mostly completed; 18l responsive UI polish remains pending. Completed scope includes navigation, Artifact Hub discovery/search/details, install configuration/API/jobs/status/progress/history, validation, and rollback/uninstall actions (18a–k, 18m–n). Current release management is limited to releases installed through KubePilot, with previous-revision rollback and no upgrade or revision picker.
19. **Manage resources** — approved, pending sidebar section for resource and Helm management in the selected cluster, delivered in order:

    - **19a — Kubernetes resource management:** `/manage-resources` and Kubernetes resources tab; list, create through validated YAML, and delete pods, deployments, namespaces, services, and other explicitly supported common types.
    - **19b — Installed Helm release management:** Helm releases tab; discover releases directly from the selected cluster across namespaces, including installations outside KubePilot; show status and revision history; support confirmed rollback/uninstall using the existing job, progress, and audit pipeline.
    - **19c — Helm repositories and upgrades:** list/add/update/remove KubePilot-managed chart repository connections and upgrade installed releases using an explicitly resolved chart source and version, with review and background job progress.

Feature 19 reuses cluster selection, namespace controls, application layout, and backend permissions. Admins/operators receive management controls; viewers remain read-only. Destructive actions require confirmation and audit records. Cluster changes refresh the displayed scope and prevent actions from using a stale target. Repository connections are Helm client configuration, not resources automatically discoverable from a cluster.

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
- **UserPreference**: user_id (unique foreign key), default_namespace, view_settings (JSON).
- **InstallationJob** (`installation_jobs`): package/chart metadata, cluster_id (foreign key), namespace, release_name, action (`install`/`rollback`/`uninstall`), revision where applicable, status (`queued`/`running`/`succeeded`/`failed`/`cancelled`), error_message (nullable), started_at, completed_at. Feature 19b must support release actions without requiring a Marketplace install record; 19c adds upgrade job metadata and behavior through a compatible extension.
- **Helm repository configuration** (planned, 19c): repository name and URL managed by KubePilot. Storage scope, credential support, and release-to-chart-source associations must be specified before implementation.

Kubernetes remains the source of truth for live resources and Helm releases. Marketplace job history is not a complete inventory of installed releases. Feature 19 persists application configuration, action/job metadata, and audit records needed for management and progress reporting; it reads current inventory from the selected cluster.

## Tech stack

- **Next.js, TypeScript, Tailwind CSS, shadcn/ui** — UI, reusable components, and same-origin API routes to FastAPI.
- **FastAPI (Python)** — authentication, permissions, application APIs, Kubernetes operations, and backend Helm integration.
- **PostgreSQL** — users, sessions, settings, cluster configuration, audit records, and operational jobs.
- **Kubernetes Python client** — live cluster discovery and planned resource creation/deletion through FastAPI only.
- **Artifact Hub search API** — public Helm package discovery; no API key for basic public search.
- **Helm in the backend** — repository setup and installs, rollback/uninstall, and planned release discovery/history, repository management, and upgrades. Use validated argument lists, never arbitrary user-provided commands.
- **Existing background job mechanism** — installation and release mutation progress; no new Celery/RQ requirement.
- **Signed HTTP-only session cookie** — shared Next.js/FastAPI authentication contract.
- **Alembic** — compatible PostgreSQL schema migrations when persisted job/configuration contracts change.

## Monetization

Self-hosted operations software with potential licensing, support/onboarding, premium multi-cluster/audit modules, or managed hosting. Initial delivery focuses on product reliability and useful operations workflows before monetization expansion.

## UI/UX

Desktop-first operations interface with readable tables, status emphasis, namespace/resource navigation, and low-noise layouts. Feature 17 establishes the light palette and shared design language; feature 16 provides light/dark theme support. The project plan still describes an older dark-first direction; see Open questions.

- `/` and `/login` — branded home and local sign-in.
- `/dashboard?resource=<type>&namespace=<ns>` — resource navigation, grouped sidebar, header cluster selector, notifications, and user menu.
- `/dashboard/detail?resourceType=&name=&namespace=` — resource status, YAML, logs, and events.
- `/marketplace` — Artifact Hub package discovery, install configuration, job progress/history, and existing rollback/uninstall controls.
- `/manage-resources` (planned, 19) — sidebar label **Manage resources**, Kubernetes resources and Helm releases tabs, and repository configuration within the same section. Reuse the application shell and selected cluster/namespace controls.
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
- Runtime configuration includes `KUBEPILOT_AUTH_SECRET`, `KUBEPILOT_DATABASE_URL`, `KUBEPILOT_CLUSTER_NAME`, `KUBEPILOT_ADMIN_EMAIL`, `KUBEPILOT_ADMIN_PASSWORD`, and `KUBEPILOT_BACKEND_URL`.
- Health endpoint: `GET /api/v1/health`.
- Deployment needs secure secret handling, worker execution, health checks, and logs. Repository configuration persistence/credentials for feature 19c must be specified before implementation.

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
- **Helm contracts for 19b/19c:** define rollback targeting, repository storage scope and credential support, chart-source association for external releases, and upgrade values handling. Do not infer repository connections from live release inventory.
- **Scale/restart gap:** project-plan §3 lists basic scale/restart actions, but the build plan has no dedicated item. Feature 19 approves create/delete, Helm management, and upgrades; it does not silently add scale/restart.
- **UI direction mismatch:** project-plan §7 describes a dark-first aesthetic, while completed feature 17 establishes a light palette and shared shell. Preserve the existing UI for feature 19.
- **Outdated milestone text:** project-plan §8 and its assumptions still describe single-cluster operation and backend integration as future work; completed build-plan items record multi-cluster/backend delivery. Earlier MVP feature summaries also omit later shipped items.
- Exact ServiceAccount/RBAC policy and system namespace protections for new management operations must be carried into the implementation specs. Marketplace 18k already requires kube-system protection unless explicitly allowed by policy.
- Audit recording is planned/implemented across features, but a dedicated audit-log UI is not a build-plan item.
- The final self-hosted/managed-service offering remains a product decision.
