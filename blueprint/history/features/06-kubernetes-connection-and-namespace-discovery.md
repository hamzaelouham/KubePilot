# Kubernetes connection and namespace discovery

**Branch:** feature/kubernetes-connection-and-namespace-discovery

**Status:** verified

## Goal

Connect the FastAPI service to one Kubernetes cluster through its runtime ServiceAccount and Kubernetes RBAC, then expose the first live cluster inventory contract for namespaces and basic resource discovery. The browser and Next.js frontend must continue to communicate only with FastAPI; no frontend code or AI path may connect directly to Kubernetes.

## In scope

- Add the Kubernetes Python client and a backend cluster client boundary that uses in-cluster ServiceAccount configuration.
- Add one-cluster settings for the Kubernetes API endpoint/context and a safe cluster display name without introducing multi-cluster selection.
- Add a versioned backend endpoint for cluster connection status and namespace discovery.
- Add resource inventory discovery for pods, deployments, services, nodes, and endpoints.
- Normalize Kubernetes client results into typed Pydantic responses with cluster and namespace context.
- Add clear handling for unavailable clusters, missing ServiceAccount configuration, Kubernetes RBAC forbidden responses, timeouts, and empty namespaces/resources.
- Add deployment configuration for a least-privilege ServiceAccount and read-only RBAC required by discovery.
- Keep credentials and raw Kubernetes API errors out of responses and logs.

## Out of scope

- Multiple clusters, cluster switching, remote kubeconfig uploads, or user-provided cluster credentials.
- Resource detail pages, logs, events, watch streams, real-time refresh, or cached snapshots.
- Mutating Kubernetes operations such as scale, restart, delete, or exec.
- Frontend dashboard integration or replacing mock data.
- Backend authentication bridge changes, application RBAC, user administration, or AI access beyond the shared FastAPI boundary.
- PostgreSQL persistence of discovered resources or cluster status history.

## Build loop

Continuous Mode used `workflow.stepReview: "feature"` and `workflow.checkpointCommits: "disabled"`; implementation proceeded through passing steps and local verification before archival and squash merge. No remote action was authorized.

## Build steps

- [x] 1. **Add the Kubernetes client boundary** - add the Python Kubernetes client, typed cluster settings, and a lazy client factory that loads in-cluster ServiceAccount configuration only when a discovery request needs it.
- [x] 2. **Define least-privilege ServiceAccount access** - add deployment configuration for one backend ServiceAccount and a read-only RBAC policy covering only discovery resources.
- [x] 3. **Expose cluster and namespace discovery** - implement versioned endpoints for connection status and namespace listing using typed response schemas.
- [x] 4. **Expose foundational resource inventory** - add backend discovery methods for pods, deployments, services, nodes, and endpoints with explicit namespace and cluster scope.
- [x] 5. **Verify operational boundaries and document deployment** - add focused tests for client construction, response normalization, error mapping, and RBAC scope, then document backend deployment prerequisites and checks.

## Files / areas

- `backend/requirements.txt` for the Kubernetes Python client
- `backend/app/core/config.py` for one-cluster settings and ServiceAccount mode
- `backend/app/kubernetes/` for client construction, error classification, and discovery adapters
- `backend/app/api/v1/` for cluster status, namespaces, and inventory routes
- `backend/app/api/v1/discovery_schemas.py` for typed discovery responses
- `backend/deploy/kubernetes/` for the backend ServiceAccount and read-only RBAC
- `backend/tests/` for client, normalization, error, and manifest checks
- `backend/README.md` and `AGENTS.md` for prerequisites, verification, and deployment notes

## Data / contracts

- Exactly one configured cluster is supported. FastAPI is the only trusted path to Kubernetes; the frontend, browser, and AI integrations never receive Kubernetes credentials or connect directly.
- Authentication uses the pod’s Kubernetes ServiceAccount and Kubernetes RBAC. No remote kubeconfig upload or request-supplied bearer token is accepted. The application local admin session remains a separate boundary for protected discovery routes.
- Discovery routes are `/api/v1/cluster/status`, `/api/v1/cluster/namespaces`, and `/api/v1/cluster/resources/{resource_type}`. Resource types are limited to `pods`, `deployments`, `services`, `nodes`, and `endpoints`; namespace is optional only for namespaced types and rejected for nodes.
- Status responses use `connected`, `unavailable`, or `forbidden` and never include API URLs, ServiceAccount names, token material, kubeconfig data, or raw exceptions.
- Namespace responses always contain an items list. Resource items contain cluster, optional namespace, kind, name, and status.
- Kubernetes 403 maps to HTTP 403/code `cluster_forbidden`; connection, configuration, and timeout failures map to HTTP 503/code `cluster_unavailable`; unexpected client failures map to HTTP 502/code `cluster_error`.
- The ServiceAccount policy grants only `get`, `list`, and `watch` over namespaces, pods, services, endpoints, nodes, and deployments. It grants no write, exec, proxy, or port-forward permission.
- Kubernetes remains the source of truth; this feature stores no discovered resource records in PostgreSQL.

## Testing

The Python pytest command covers lazy client construction, missing in-cluster configuration, 403 classification, namespace forwarding, typed route responses, empty behavior, and RBAC verbs using fake clients and deterministic fixtures. No live cluster or external credentials were required. The live-cluster smoke path is documented but was not run. Final checks were `cd backend && python3 -m pytest` and `cd k8s-ui && yarn build`.

## Notes for the AI

- Keep the official Kubernetes Python client behind the adapter interface.
- Treat ServiceAccount and RBAC as security boundaries; never use `cluster-admin` or request-provided credentials.
- Keep Kubernetes objects out of API schemas and preserve unavailable, forbidden, empty, and unexpected-error states.

## Open questions

- The deployment namespace is currently represented by the `kubepilot` manifest namespace and should be parameterized when deployment packaging is formalized.
