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

* [ ] 12. **RBAC and multi-user controls** - support role-based access and more granular permissions across cluster operations.

  * [x] 12a. **Multi-user authentication** - authenticate any provisioned app user against database-backed accounts, seed the environment-configured admin on first login, and keep per-user sessions.
  * [x] 12b. **User management** - add admin-only user provisioning: create and list users, assign admin/operator/viewer roles, and deactivate accounts through backend endpoints and an admin UI.
  * [ ] 12c. **Role-based access enforcement** - enforce admin/operator/viewer permissions on cluster operations in the backend and make the frontend navigation and surfaces role-aware. Rolled back 2026-09-06 (`blueprint/history/rollbacks/2026-09-06-12c-role-based-access-enforcement.md`).

* [ ] 13. **Multi-cluster support** - connect and compare multiple Kubernetes environments from one interface.

* [ ] 14. **AI Copilot for Kubernetes operations** - add natural-language investigation support to explain issues and help apply approved actions.

* [x] 15. **shadcn/ui integration and table migration** - integrate shadcn/ui into the Next.js app and migrate the existing resource tables to reusable shadcn/ui Data Table components while preserving the current visual design.

* [x] 16. **Header components and theme support** - remove the non-functional header search, migrate the header controls (notification, logout) to shadcn/ui components, and add light/dark theme support with a theme switcher while preserving the existing design.
