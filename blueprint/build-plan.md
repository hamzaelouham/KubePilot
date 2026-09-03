# Build Plan

## MVP

- [x] 1. **Dashboard foundation** - establish the polished Kubernetes operations UI shell, navigation, and resource layout for cluster operations.
- [x] 2. **Cluster overview and mock data** - present overview metrics, workload statuses, namespace controls, and resource tables using realistic placeholder data.
- [x] 3. **Authentication and protected app access** - add local admin login, sessions, and protected routes for the operational application.
- [x] 4. **FastAPI backend foundation** - create the API layer, project structure, and database-backed service foundation for future cluster integration.
- [x] 5. **PostgreSQL application data model** - configure persistent storage for users, sessions, cluster metadata, settings, and operational records.
- [x] 6. **Kubernetes connection and namespace discovery** - connect to a cluster and surface namespaces, endpoints, and resource inventory through the backend.
- [x] 7. **Core resource views** - implement pods, deployments, services, and node listings with status-driven data and real cluster context.
- [x] 8. **Resource details and troubleshooting surfaces** - add detail pages for status, YAML, logs, and recent events for a selected workload or resource.
- [ ] 9. **Run app on top of real k8s cluster (local minikube)** - Deploy the Kubernetes management platform into a real Kubernetes cluster running locally with Minikube The application must be able to run as a set of Kubernetes workloads, communicate with the Kubernetes API, and provide a functional UI for managing the cluster. This milestone validates that the platform is not only a frontend mockup or a local development application, but a real Kubernetes-native application.
  - [x] 9a. **Containerize the services** - add reproducible container images and a local compose runtime for the Next.js frontend, FastAPI backend, and PostgreSQL database.
  - [ ] 9b. **Deploy onto Minikube** - add Kubernetes manifests, in-cluster configuration, and RBAC so all three services run as workloads on a local Minikube cluster and the UI operates against the live Kubernetes API.

## Post-MVP

- [ ] 10. **Real-time refresh and health updates** - add live refresh behavior, alerting cues, and operational status updates.
- [ ] 11. **RBAC and multi-user controls** - support role-based access and more granular permissions across cluster operations.
- [ ] 12. **Multi-cluster support** - connect and compare multiple Kubernetes environments from one interface.
- [ ] 13. **Observability enhancements** - expand resource insights, metrics summaries, and health trends across workloads and clusters.
- [ ] 14. **AI Copilot for Kubernetes operations** - add natural-language investigation support to explain issues and help apply approved actions.

> Notes: The current shipped UI is treated as scored work already completed. The next major value is linking the interface to real Kubernetes data and securing the operational workflow with local auth and a proper backend foundation.
