# Current Feature

> **Generated file.** Holds the one feature, fix, or rollback being built right now. Run
> `/feature <number-or-name>` to spec a build-plan feature, or `/fix "<bug>"` for
> an ad-hoc fix. Use `/rollback <completed-feature>` to plan a safe reversal.
> Build one thing at a time; `/complete` archives it under
> `blueprint/history/` and resets this file.

_Nothing in progress. Run `/feature`, `/fix`, or `/rollback` to start._

## In scope

- Add the Kubernetes Python client and a backend cluster client boundary that uses in-cluster ServiceAccount configuration.
- Add one-cluster settings for the Kubernetes API endpoint/context and a safe cluster display name without introducing multi-cluster selection.
- Add a versioned backend endpoint for cluster connection status and namespace discovery.
- Add resource inventory discovery for the foundational cluster objects needed by the next UI features, including pods, deployments, services, nodes, and endpoints.
- Normalize Kubernetes client results into typed Pydantic responses with cluster and namespace context.
- Add clear handling for unavailable clusters, missing ServiceAccount configuration, Kubernetes RBAC forbidden responses, timeouts, and empty namespaces/resources.
- Add Kubernetes manifests or documented deployment configuration for a least-privilege ServiceAccount and read-only RBAC required by discovery.
- Keep credentials and raw Kubernetes API errors out of responses and logs.

## Out of scope

- Multiple clusters, cluster switching, remote kubeconfig uploads, or user-provided cluster credentials.
- Resource detail pages, logs, events, watch streams, real-time refresh, or cached snapshots; those belong to later features.
- Mutating Kubernetes operations such as scale, restart, delete, or exec.
- Frontend dashboard integration or replacing mock data; feature 7 owns the resource views and their UI wiring.
- Backend authentication bridge changes, application RBAC, user administration, or AI access beyond the shared FastAPI boundary.
- PostgreSQL persistence of discovered resources or cluster status history.

## Build loop

Continuous Mode is running with `workflow.stepReview: "feature"` and `workflow.checkpointCommits: "disabled"`; implementation proceeds through passing steps and local verification before the feature is archived and squash-merged. The final gate must include backend tests, Kubernetes client boundary checks, the existing frontend `yarn build`, and a clear report when no live cluster is available.

## Build steps

- [x] 1. **Add the Kubernetes client boundary** - add the Python Kubernetes client, typed cluster settings, and a lazy client factory that loads in-cluster ServiceAccount configuration only when a discovery request needs it.
	- Done when: importing the backend does not contact Kubernetes, the configured one-cluster client can be constructed through one shared boundary, missing in-cluster configuration becomes a classified availability error, and focused tests pass without a cluster.

- [x] 2. **Define least-privilege ServiceAccount access** - add deployment configuration for one backend ServiceAccount and a read-only RBAC policy covering only discovery resources.
	- Done when: the manifests bind the backend ServiceAccount to a namespaced/cluster-scoped read role with only required `get`, `list`, and `watch` verbs, no write or exec permissions exist, and manifest validation or structural tests pass.

- [x] 3. **Expose cluster and namespace discovery** - implement versioned endpoints for connection status and namespace listing using typed response schemas.
	- Done when: a successful client response returns the configured cluster identity and namespace statuses, an empty namespace result returns a valid empty list, and unavailable/forbidden/timeout client errors map to stable non-sensitive HTTP errors.

- [x] 4. **Expose foundational resource inventory** - add backend discovery methods for pods, deployments, services, nodes, and endpoints with explicit namespace and cluster scope.
	- Done when: each supported resource maps to a stable typed inventory shape, namespace-scoped calls cannot silently become cluster-wide calls, missing resources produce empty results rather than fabricated data, and forbidden or unexpected client failures retain their error classification.

- [x] 5. **Verify operational boundaries and document deployment** - add focused tests for client construction, response normalization, error mapping, and RBAC scope, then document the backend deployment prerequisites and checks.
	- Done when: the documented Python test command and compile check pass, the frontend `yarn build` passes, a live-cluster smoke path is documented without claiming it was run unless credentials are available, and the README states that all Kubernetes access flows through FastAPI.

## Files / areas

- `backend/requirements.txt` for the Kubernetes Python client
- `backend/app/core/config.py` for the one-cluster settings and ServiceAccount mode
- `backend/app/kubernetes/` for client construction, error classification, and discovery adapters
- `backend/app/api/v1/` for cluster status, namespaces, and inventory routes
- `backend/app/api/v1/schemas.py` for typed discovery responses and safe errors
- `backend/deploy/kubernetes/` for the backend ServiceAccount, read-only RBAC, and deployment configuration
- `backend/tests/` for client, normalization, error, and manifest checks
- `backend/README.md` and `AGENTS.md` for prerequisites, verification, and deployment notes

The existing `k8s-ui/` remains unchanged in this feature. Feature 7 will consume these APIs from the dashboard.

## Data / contracts

- The service supports exactly one configured cluster in this feature. The backend cluster client is the only trusted path to the Kubernetes API. The frontend, browser, and AI integrations never receive Kubernetes credentials or connect to the cluster directly.
- Authentication uses the pod’s Kubernetes ServiceAccount and the permissions granted by Kubernetes RBAC. No remote kubeconfig upload or request-supplied bearer token is accepted. The application’s local admin session remains a separate boundary and is required before protected discovery routes are exposed.
- Discovery routes use `/api/v1/cluster/status`, `/api/v1/cluster/namespaces`, and `/api/v1/cluster/resources/{resource_type}`. `resource_type` is limited to `pods`, `deployments`, `services`, `nodes`, and `endpoints`; namespace is an optional query parameter only for namespaced resource types and is rejected for cluster-scoped nodes.
- Status response: `{ "status": "connected" | "unavailable" | "forbidden", "cluster": string }`. It never includes API URLs, ServiceAccount names, token material, kubeconfig data, or raw client exceptions.
- Namespace response items contain `name` and `status`; the response always includes a list, including when the cluster has no namespaces. Resource inventory items contain `cluster`, optional `namespace`, `kind`, `name`, and `status`, with only safe summary fields needed by feature 7.
- Kubernetes `ApiException` status 403 maps to `403` with code `cluster_forbidden`; connection, configuration, and timeout failures map to `503` with code `cluster_unavailable`; unexpected client failures map to `502` with code `cluster_error`. Messages are concise and do not include server response bodies.
- Namespace scope is repository-first: a namespaced request passes the validated namespace directly to the corresponding namespaced Kubernetes API; a missing namespace means all namespaces only for explicitly supported list operations. Cluster-scoped nodes and endpoints behavior is defined by the adapter, not by arbitrary URL input.
- The ServiceAccount RBAC policy grants read-only access only to the discovery API groups/resources required by these endpoints. It grants no create, update, patch, delete, exec, proxy, or port-forward permission. The exact namespace scope for the policy must match the deployment’s one-cluster discovery requirement and remain explicit in manifests.
- Kubernetes remains the source of truth. This feature returns live summaries and stores no discovered resource records in PostgreSQL.

## Testing

The repository now has a Python pytest command from feature 5. Add focused tests using fake Kubernetes client interfaces and deterministic response fixtures; no test may require a real cluster, ServiceAccount token, network access, or PostgreSQL. Cover lazy client construction, missing in-cluster configuration, 403/timeout/unavailable classification, empty results, namespace forwarding, typed normalization, and manifest verbs/resources. Run the live-cluster smoke command only when a user-provided deployment environment is available and report it separately from automated tests. The final regression checks are `cd backend && python3 -m pytest` and `cd k8s-ui && yarn build`.

## Notes for the AI

- Use the official Kubernetes Python client and keep it behind a small adapter interface so route code is testable without Kubernetes.
- Treat ServiceAccount configuration and RBAC as security boundaries. Never add a broad `cluster-admin` binding or accept credentials from query/body data.
- Keep Kubernetes client objects out of API schemas; normalize them into stable Pydantic response models.
- Make client creation lazy and request-safe; importing or health-checking the app must not contact the cluster unless the contract explicitly requires it.
- Preserve unavailable, forbidden, empty, and unexpected-error states. Do not turn missing permissions or an empty cluster into a successful fabricated response.

## Open questions

- The deployment target is now frontend + FastAPI + PostgreSQL, but the exact namespace in which the backend ServiceAccount and read-only role binding will be installed is not specified. The implementation should use a clearly documented configurable deployment namespace rather than inventing a production namespace.
