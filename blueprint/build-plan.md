# Build Plan

## MVP

* [x] 1. **Dashboard foundation** - establish the polished Kubernetes operations UI shell, navigation, and resource layout for cluster operations.
* [x] 2. **Cluster overview and mock data** - present overview metrics, workload statuses, namespace controls, and resource tables using realistic placeholder data.
* [x] 3. **Authentication and protected app access** - add local admin login, sessions, and protected routes for the operational application.
* [x] 4. **FastAPI backend foundation** - create the API layer, project structure, and database-backed service foundation for future cluster integration.
* [x] 5. **PostgreSQL application data model** - configure persistent storage for users, sessions, cluster metadata, settings, and operational records.
* [x] 6. **Kubernetes connection and namespace discovery** - connect to a cluster and surface namespaces, endpoints, and resource inventory through the backend.
* [x] 7. **Core resource views** - implement pods, deployments, services, and node listings with status-driven data and real cluster context.
* [x] 8. **Resource details and troubleshooting surfaces** - add detail pages for status, YAML, logs, and recent events for a selected workload or resource.
* [x] 9. **Run app on top of a real Kubernetes cluster (local Minikube)** - deploy the Kubernetes management platform into a real Kubernetes cluster running locally with Minikube.

  * [x] 9a. **Containerize the services** - add reproducible container images and a local Compose runtime for the Next.js frontend, FastAPI backend, and PostgreSQL database.
  * [x] 9b. **Deploy onto Minikube** - add Kubernetes manifests, in-cluster configuration, and RBAC so all three services run as workloads on a local Minikube cluster and the UI operates against the live Kubernetes API.

## Post-MVP

* [x] 10. **Real-time refresh and health updates** - add live refresh behavior, alerting cues, and operational status updates.

* [x] 11. **Live resource metrics and observability** - add real-time CPU, memory, storage, and resource utilization information for nodes and workloads.

  * [x] 11a. **Node metrics** - display live CPU and memory utilization, allocatable capacity, and storage usage for each node.
  * [x] 11b. **Workload metrics** - display CPU and memory usage for Pods and workload resources, with namespace-level utilization summaries.
  * [x] 11c. **Storage metrics** - display node filesystem usage and available storage, with PersistentVolume and PersistentVolumeClaim capacity and utilization where supported.
  * [x] 11d. **Metrics API integration** - integrate the Kubernetes Metrics API and, where needed, Prometheus for historical metrics and advanced observability.
  * [x] 11e. **Metrics UI** - add charts, utilization indicators, time ranges, and resource-level metrics to the dashboard and detail pages.

* [x] 12. **Users, Authentication & RBAC** - database-backed multi-user authentication with exactly three roles (admin/operator/viewer), admin-managed user provisioning (create, role assignment, activate/deactivate, password reset/force change), 15-day password expiration, forced password change, self-service password change, centralized backend permission enforcement, audit logging, and a role-aware admin UI. The previous 12a/12b/12c attempts were rolled back 2026-09-06 and re-speced as this single item (`blueprint/context/current-feature.md`; rollback archives in `blueprint/history/rollbacks/`).

* [x] 13. **Multi-cluster support** - connect and compare multiple Kubernetes environments from one interface.
  * [x] 13a. **Backend cluster store and management API** - seed the default cluster on startup, add list and register cluster endpoints (admin-only create), store kubeconfig references, and lay the database foundation for cluster routing.
  * [x] 13b. **Backend cluster routing** - modify all `/api/v1/cluster/*` routes to accept a `cluster` query param, resolve to the correct `ClusterConnection`, load the appropriate kubeconfig, and return 404/422 for unknown or unreachable clusters.
  * [x] 13c. **Frontend cluster selector** - add a cluster selector dropdown to the header, persist selection to localStorage, and pass the cluster ID on every backend API call.
  * [x] 13d. **Admin cluster management page** - add `/settings/clusters` with a table of registered clusters, a form to register new clusters, and an activate/deactivate toggle (admin-only).

* [ ] 14. **AI Copilot for Kubernetes operations** - add natural-language investigation support to explain issues and help apply approved actions.

* [x] 15. **shadcn/ui integration and table migration** - integrate shadcn/ui into the Next.js app and migrate the existing resource tables to reusable shadcn/ui Data Table components while preserving the current visual design.

* [x] 16. **Header components and theme support** - remove the non-functional header search, migrate the header controls (notification, logout) to shadcn/ui components, and add light/dark theme support with a theme switcher while preserving the existing design.

* [x] 17. **UI polish & design consistency** - unify the home, login, and change-password pages onto the dashboard's light palette with simple centered forms, restructure the sidebar into grouped sections (OVERVIEW / WORKLOADS / NETWORK / CONFIGURATION / STORAGE / CLUSTER / ADMINISTRATION) that show only existing resources, rework the header with the KubePilot brand, cluster selector, notifications, and user menu, and design the shell around a `clusterId` context so the future Multi-cluster feature (13) slots in without a redesign.

* [ ] 18. **KubePilot Marketplace** - discover and install Kubernetes Helm packages from Artifact Hub.

  * [x] 18a. **Marketplace navigation & page** - add `/marketplace` route, a main sidebar entry, and a page header (Marketplace - "Discover and install Kubernetes applications") that reuses the existing application shell and preserves current navigation.
  * [x] 18b. **Package discovery** - integrate the Artifact Hub package search API (Helm charts only, kind=0) with pagination/Load More, a reusable PackageCard (logo, name, description, publisher/repository, latest version, Install button), loading skeletons, empty state, and API error state.
  * [ ] 18c. **Package search & filtering** - search input connected to the Artifact Hub API with debounce, optional sorting if useful, and correct pagination with loading/empty/error handling.
  * [ ] 18d. **Package details** - a lightweight drawer/modal/dedicated view for a package showing name, logo, description, publisher, repository, version, Helm install info, and an Install button.
  * [ ] 18e. **Installation configuration dialog** - a reusable dialog collecting package/version/cluster/namespace/release name with validation, reusing the existing cluster and namespace selectors; no Helm command is executed by the frontend.
  * [ ] 18f. **Installation API** - POST `/api/marketplace/install` (package_id, version, cluster_id, namespace, release_name) validates request/authorization/cluster/namespace, resolves package/chart metadata, creates an installation job, and returns `{job_id, status: "queued"}` without waiting for Helm.
  * [ ] 18g. **Installation job model & background worker** - an InstallationJob model (queued/running/succeeded/failed/cancelled) and a background Helm worker (repo add/repo update/helm install, capture result, update job); do not introduce Celery/RQ unless the existing FastAPI architecture already needs it.
  * [ ] 18h. **Installation status API** - GET `/api/marketplace/installations/{job_id}` returning status, package name, cluster, namespace, release name, error_message, and useful timestamps.
  * [ ] 18i. **Installation progress UI** - immediate feedback while Helm runs (queued -> running -> succeeded/failed); Close only closes the UI and never cancels the installation.
  * [ ] 18j. **Installation history** - a table of recent installations (package, cluster, namespace, status badge, date) with basic status filtering only if easy; no release management/upgrade/rollback/uninstall yet.
  * [ ] 18k. **Security & validation** - authenticated user and install-permission checks, cluster/namespace/release-name/package/version validation, never execute arbitrary commands from user input, never trust Artifact Hub metadata as executable input, kube-system protected unless explicitly allowed by policy, safely constructed Helm commands.
  * [ ] 18l. **Marketplace UI polish & responsive** - reuse shadcn/ui components and the Tailwind theme/spacing/colors, responsive package grid, skeleton/empty/error states, dialog animations if already used, mobile/tablet support.
