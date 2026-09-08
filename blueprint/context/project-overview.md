# KubePilot - Project Overview

<!-- blueprint:source-hash 440847fc64891ae6c8c23192f618c8708f1a19344471b475f43771ddfbe774f8 -->

> A self-hosted, Kubernetes-native operations platform: a modern control plane for cluster health, workload visibility, and platform operations, with FastAPI as the only component that talks to the Kubernetes API.

## Problem

Kubernetes operations teams face operational overload: raw kubectl and fragmented dashboards force context-switching, obscuring cluster health, workload failures, and safe remediation. KubePilot gives a centralized, decision-oriented interface for understanding health, investigating failures, and managing workloads with less operational friction.

## Users

Primary: DevOps engineers, platform engineers, SREs who operate clusters and troubleshoot without living in kubectl.
Secondary: engineering managers and technical operators needing higher-level health visibility.

Auth tiers: anonymous (login only) → signed-in operator/viewer → admin (user management + role-aware UI).

## Features

MVP (build-plan order, shipped):

1. **Dashboard foundation** - polished operations UI shell, navigation, and resource layout.
2. **Cluster overview and mock data** - overview metrics, workload statuses, namespace controls, and resource tables.
3. **Authentication and protected app access** - local admin login, sessions, protected routes.
4. **FastAPI backend foundation** - API layer, project structure, PostgreSQL-backed service foundation.
5. **PostgreSQL application data model** - persistent users, sessions, cluster metadata, settings, audit records.
6. **Kubernetes connection and namespace discovery** - live cluster access and resource inventory through the backend.
7. **Core resource views** - pods, deployments, services, and nodes with status-driven data.
8. **Resource details and troubleshooting surfaces** - detail pages for status, YAML, logs, events.
9. **Run app on real k8s cluster (Minikube)** - containerized images (9a) deployed as workloads on Minikube (9b).
10. **Real-time refresh and health updates** - live refresh, alerting cues, operational status updates.
11. **Live resource metrics and observability** - CPU/memory/storage utilization with Metrics API (a-e) and metrics UI.
12. **Users, Authentication & RBAC** - three roles (admin/operator/viewer), admin provisioning, password policy, centralized enforcement, audit logging, role-aware UI.
13. **Multi-cluster support** - connect and compare multiple environments; backend cluster store + routing (a/b), header selector (c), admin cluster management page (d).
14. **AI Copilot for Kubernetes operations** *(next unstarted item before Marketplace)* - natural-language investigation and approved actions.
15. **shadcn/ui integration and table migration** - shadcn/ui components and reusable Data Tables.
16. **Header components and theme support** - shadcn header controls and light/dark theme switching.
17. **UI polish & design consistency** - unified light-palette pages, grouped sidebar (OVERVIEW / WORKLOADS / NETWORK / CONFIGURATION / STORAGE / CLUSTER / ADMINISTRATION), client-routed shell around a `clusterId` context.

Post-MVP, roadmap:

18. **KubePilot Marketplace** *(next)* - discover and install Kubernetes Helm packages from Artifact Hub.
    - 18a navigation & page → 18b package discovery → 18c search & filtering → 18d package details → 18e installation configuration dialog → 18f installation API → 18g job model + background worker → 18h status API → 18i progress UI → 18j installation history → 18k security & validation → 18l UI polish & responsive.

## Data model

All tables carry `id` (uuid pk) and `created_at`; cluster-scoped entities reference `cluster_connections.id`.

- **UserAccount** (`user_accounts`): email (unique), password_hash, role (default `operator`), is_active, updated_at, last_login_at, password_changed_at, password_expires_at, must_change_password. One-to-many Session, UserPreference; one-to-many AuditAction as actor.
- **Session**: user_id (FK, cascade), token_hash (unique), issued_at, expires_at, restricted (forced non-admin access for password/restricted sessions).
- **ClusterConnection** (`cluster_connections`): name (unique), endpoint, kubeconfig_ref, status. One-to-many Namespace, Workload, Pod, Deployment, Service, Node, Event, InstallationJob.
- **Namespace**: cluster_id + name (unique pair), status.
- **Workload**: cluster_id + namespace + kind + name (unique), status, labels (JSON), image.
- **Pod**: cluster_id + namespace + name (unique), status, ready, restarts, age.
- **Deployment**: cluster_id + namespace + name (unique), replicas, status, image.
- **Service**: cluster_id + namespace + name (unique), selector (JSON), ports (JSON), status.
- **Node**: cluster_id + name (unique), role, status, version.
- **Event**: cluster_id + namespace (nullable), kind, name, message.
- **AuditAction** (`audit_actions`): actor_id (FK, nullable), action, resource_type, resource_id, target_user_id (FK, nullable), result, context (nullable). Captures admin user-management actions; no UI surface yet.
- **UserPreference**: user_id (unique FK), default_namespace, view_settings (JSON).
- **InstallationJob** (`installation_jobs`, feature 18g): package_id, package_name, chart_name, chart_repository, chart_version, cluster_id (FK → ClusterConnection), namespace, release_name, status (queued/running/succeeded/failed/cancelled), error_message (nullable), started_at, completed_at.

> Lock the UserAccount/Session/RBAC shapes - Multi-cluster (13) and the audit-log surface build on them. InstallationJob is cluster-scoped via `cluster_connections.id` and surfaced by the Marketplace progress (18i) and history (18j) UIs.

## Tech stack

- **Next.js (TypeScript, Tailwind CSS, shadcn/ui)** - frontend UI; same-origin API proxy (`proxy.ts`) forwards `/api/*` to the backend.
- **FastAPI (Python)** - backend API, session validation, RBAC enforcement, Kubernetes integration, and (18f-18h) Marketplace install jobs + background Helm execution.
- **PostgreSQL** - users, sessions, audit records, settings, cluster metadata, and InstallationJob records.
- **Kubernetes Python client** - cluster API access through FastAPI only; frontend never connects to Kubernetes directly.
- **Artifact Hub search API** - read-only Helm package discovery (18b/18c); no API key for basic public search.
- **Helm (backend)** - chart repo add/update/install run inside FastAPI for installs (18g).
- **Shared signed HTTP-only session cookie** - auth boundary between Next.js and FastAPI, validated against PostgreSQL.
- **Alembic** - schema migrations (backward-compatible chain: `dd752e8644a9` → `570583371bec` → `a1b2c3d4e5f6`).

## Monetization

Self-hosted operations platform, likely commercial open-core or enterprise model (licensing, support/onboarding, premium multi-cluster/audit modules, managed hosting). v1 focuses on product value and reliability before aggressive monetization.

## UI/UX

Desktop-first operations dashboard. Consistent light slate palette (`bg-slate-100` surfaces, `cyan` accents, `red-50/amber-50` status colors) with semantic shade tokens and light/dark mode via next-themes.

- `/` - branded home page (light dashboard palette).
- `/login` - simple centered sign-in form only.
- `/dashboard?resource=<type>&namespace=<ns>` - shell with grouped sidebar + header (KubePilot brand, cluster selector, notifications, user menu); views for overview, workloads, pods, deployments, services, nodes, namespaces, cluster, cluster-roles, storage.
- `/dashboard/detail?resourceType=&name=&namespace=` - resource detail: Status, YAML, Logs, Events tabs.
- `/marketplace` - Marketplace (feature 18): discover and install Helm packages; package grid/cards, search, detail view, and install/progress/history surfaces reusing the shell, shadcn/ui, and existing cluster/namespace selectors.
- `/settings/clusters` - registered clusters + activate/deactivate (admin page).
- `/settings/users` - admin user management (feature 12).
- `/settings/password` - self-service / forced password change (simple centered form).
- `/api/auth/*`, `/api/users/*` - same-origin proxy routes to the backend.

Design direction (feature 17 + 18l): one design language across home, auth, and dashboard pages; structured sidebar navigation by resource group and namespace; low-noise layouts; status emphasis with actionable data; Marketplace looks native to KubePilot (reuse shadcn/ui, Tailwind theme/spacing/colors).

## Deployment

Self-hosted, Kubernetes-native:

- Frontend: Next.js standalone build, deployed as a pod (`hamzaelouham/kubepilot-ui`).
- Backend: FastAPI + uvicorn + Alembic upgrade on boot (pod `hamzaelouham/kubepilot-backend`); also runs OCI-backed background Helm install jobs for the Marketplace.
- Database: PostgreSQL stateful workload on the cluster.
- Kubernetes: FastAPI connects to the cluster in-cluster via ServiceAccount + RBAC (imagePullPolicy IfNotPresent for local Minikube workflow).
- Env vars: `KUBEPILOT_AUTH_SECRET` (≥32 chars), `KUBEPILOT_DATABASE_URL`, `KUBEPILOT_CLUSTER_NAME` (default `primary`), `KUBEPILOT_ADMIN_EMAIL`, `KUBEPILOT_ADMIN_PASSWORD`, `KUBEPILOT_BACKEND_URL` (frontend → backend, default `http://127.0.0.1:8000`, in-cluster `http://backend:8000`).
- Health endpoint: `GET /api/v1/health`.
- Topology: one cluster now; Multi-cluster (13) later - the UI shell already carries a `clusterId` context by design.

## Authentication boundary

- Next.js and FastAPI share the signing secret, cookie name (`kubepilot_session`), and session format.
- Cookie is signed and HTTP-only; browser JavaScript cannot mint or override identity.
- FastAPI validates signature/expiry, loads the user from PostgreSQL, and enforces roles before serving protected data.
- Kubernetes credentials remain exclusively in the backend runtime; never sent to the frontend, browser, or AI.

## Open questions

- **Project plan §3 lists "Basic resource actions such as scale and restart" as MVP, but the build plan has no such feature.** Add a build-plan item if those operations are wanted. (Plan §3 also still lists the MVP-era feature set rather than matching the shipped 1-17 checklist - reconciled in the overview from build-plan.md.)
- **Project plan §7 describes a "dark, polished control-plane aesthetic"; the shipped UI and the approved feature 17 direction use the light slate palette.** Project plan §7 should be updated to match.
- Audit logging is recorded per feature 12 but has no UI surface; ADMINISTRATION in feature 17's sidebar omits it until a dedicated audit-log feature exists.
- Exact ServiceAccount and Kubernetes RBAC policy bindings for the first cluster are still not pinned in the plans.
- Marketplace (18) open items to decide in their own specs: Artifact Hub package metadata contract (which fields count as "executable input" for 18k), install authorization policy (who may install per role), namespace/release-name validation rules, kube-system policy beyond "not allowed", Helm availability inside the backend image/container, and job restart behavior for a simple background worker.