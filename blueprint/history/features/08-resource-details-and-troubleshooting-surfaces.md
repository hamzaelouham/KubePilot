# Resource details and troubleshooting surfaces

**Status:** verified
**Branch:** feature/resource-details-and-troubleshooting-surfaces

## Goal

Add protected resource detail views for a selected Kubernetes workload or resource so operators can inspect current status, safe YAML, recent logs, and recent events through FastAPI without using kubectl. The browser continues to call the Next.js same-origin boundary, while FastAPI remains the only component with Kubernetes credentials and access.

## In scope

- Add typed FastAPI detail, YAML, logs, and events endpoints for a selected supported resource, using the existing shared signed session authentication and Kubernetes ServiceAccount boundary.
- Add backend adapters that retrieve a resource by validated cluster, namespace, kind, and name without accepting arbitrary Kubernetes API paths.
- Normalize status, metadata, YAML, log lines, and event records into stable Pydantic response shapes with bounded output.
- Add same-origin Next.js detail routes and a dashboard detail surface reachable from core resource rows.
- Provide readable loading, empty, not-found, forbidden, unavailable, malformed-input, and unexpected-error states.
- Redact sensitive fields from YAML and logs, and prevent raw Kubernetes exception bodies or credentials from reaching the browser.
- Preserve namespace and one-cluster boundaries from feature 6 and the shared cookie/authentication contract from feature 7.

## Out of scope

- Resource mutation such as scale, restart, delete, exec, port-forward, or apply; those belong to feature 9.
- Watch streams, polling, automatic refresh, alerting, or WebSocket behavior; those belong to feature 10.
- Multiple clusters, kubeconfig uploads, frontend Kubernetes clients, or browser access to ServiceAccount credentials.
- Arbitrary resource kinds, arbitrary API paths, cluster-admin permissions, or user-controlled query fragments.
- Persistent log/event snapshots, analytics, full audit workflows, or AI-generated explanations.

## Build loop

The configured workflow uses `workflow.stepReview: "feature"` and `workflow.checkpointCommits: "disabled"`. Implementation proceeds in small passing steps and ends with a verified feature archive and work commit. The final automated checks are `cd backend && python3 -m pytest`, `cd backend && python3 -m compileall -q app`, and `cd k8s-ui && yarn build`; browser evidence is required when the local services can run together but must not be claimed without direct observation.

## Build steps

- [x] 1. **Define safe detail contracts** - add validated resource identity inputs and typed response schemas for status, YAML, logs, and events.
	- Done when: supported resource kinds and namespaced/cluster-scoped rules are explicit, response fields and limits are stable, malformed identities are rejected before Kubernetes access, and backend schema tests pass.

- [x] 2. **Add backend detail adapters** - retrieve selected resources, serialize safe YAML, fetch bounded recent logs, and list recent events through the Kubernetes client boundary.
	- Done when: successful, empty, not-found, forbidden, unavailable, timeout, and unexpected client outcomes map to documented non-sensitive responses; no arbitrary API path or mutation method is exposed; focused fake-client tests pass.

- [x] 3. **Add protected same-origin detail routes** - forward the signed session cookie from Next.js to FastAPI for detail requests and preserve backend-only Kubernetes access.
	- Done when: unauthenticated requests redirect or return the existing `401` envelope, authenticated requests preserve the selected resource identity and namespace, and frontend source contains no Kubernetes client or credential access.

- [x] 4. **Build the operator detail surface** - add row links and a detail view with tabs or equivalent views for status, YAML, logs, and events.
	- Done when: an operator can open a selected resource detail view, switch between the four panels, see loading/empty/error states, return to the resource list, and distinguish live data from unavailable data without layout overflow.

- [x] 5. **Verify redaction and troubleshooting behavior** - test sensitive-field filtering, bounded output, route navigation, and regression behavior.
	- Done when: `cd backend && python3 -m pytest`, `cd backend && python3 -m compileall -q app`, and `cd k8s-ui && yarn build` pass; direct browser checks cover detail navigation when services are available; and a live-cluster try path is documented without claiming it was run absent a configured cluster.

## Files / areas

- `backend/app/kubernetes/` for detail retrieval, YAML/log/event normalization, bounds, redaction, and error mapping
- `backend/app/api/v1/` for protected detail routes and Pydantic response schemas
- `backend/app/core/` for existing authentication and trusted resource-scope dependencies
- `backend/tests/` for schema, adapter, redaction, error, and authorization-boundary tests
- `k8s-ui/app/api/` for same-origin proxy routes
- `k8s-ui/app/dashboard/page.tsx`, `k8s-ui/components/core-resource-view.tsx`, and new detail components/routes for navigation and presentation
- `k8s-ui/components/` for status, YAML, logs, events, loading, and error surfaces
- `backend/README.md` and `AGENTS.md` for detail endpoint and verification documentation

## Data / contracts

- Detail identity is structured as `cluster` (the configured one-cluster identity), `resource_type`, `name`, and optional `namespace`. `resource_type` is an allowlist of the supported resources from feature 7; the server derives Kubernetes API calls from that allowlist.
- Proposed protected routes are `/api/v1/cluster/resources/{resource_type}/{name}`, `/yaml`, `/logs`, and `/events`, with namespace as a validated query parameter only for namespaced resources. Nodes remain cluster-scoped. The frontend proxy uses same-origin `/api/cluster/details` routes and forwards only the session cookie.
- Status response includes resource identity, kind, namespace, current status, labels/annotations filtered to safe metadata, and a live-source marker. It never includes ServiceAccount data, raw API URLs, tokens, kubeconfigs, or full unfiltered object metadata.
- YAML response is a UTF-8 string generated from the selected object with secrets, token-like values, credential-bearing annotations, and configured sensitive fields redacted to `[REDACTED]`. It is displayed as escaped text, never injected as HTML. YAML output is bounded and truncation is explicit in the response.
- Logs response contains an ordered list of bounded log lines, an optional container identifier selected from server-known object data, and a `truncated` flag. It does not accept arbitrary shell commands, follow mode, or client-provided log paths.
- Events response contains bounded records with `type`, `reason`, `message`, `source`, and `created_at`; empty event history is a valid response with an empty list. Event messages are rendered as text.
- Authentication and Kubernetes errors preserve existing envelopes: missing/invalid session is `401`/`authentication_required`, RBAC denial is `403`/`cluster_forbidden`, unavailable or timeout is `503`/`cluster_unavailable`, not-found is `404`/`resource_not_found`, malformed identity is `422`/`invalid_resource_identity`, and unexpected adapter failure is `502`/`cluster_error`. Raw exception bodies are never returned.
- Access is repository-first: the authenticated user is resolved from the shared signed cookie and PostgreSQL session, then the backend validates the one configured cluster and namespace scope before calling Kubernetes. The browser cannot override actor, cluster, or tenant identity.
- This feature reads live Kubernetes data and does not persist YAML, logs, events, or detail snapshots in PostgreSQL. Later refresh behavior must be explicit and belongs to feature 10.

## Testing

Use the configured Python pytest runner with fake Kubernetes clients and isolated fixtures. Cover allowlisted resource kinds, namespace forwarding, cluster-scoped nodes, not-found/forbidden/unavailable/timeout mapping, YAML redaction and escaping, log/event bounds and empty results, authentication rejection, and unexpected-error handling. Frontend behavior uses the existing build and direct browser checks when both services can run; no new browser test harness is added here.

## Notes for the AI

- Treat YAML and logs as untrusted operational text. Escape them in the UI, redact sensitive values server-side, and enforce output limits before serialization.
- Keep resource lookup explicit and allowlisted. Never interpolate arbitrary user input into Kubernetes client method names or URLs.
- Keep detail reads read-only. Do not add mutation methods, watch loops, or background workers in this feature.
- Preserve all meaningful states: loading, ready, empty, not found, forbidden, unavailable, malformed request, and unexpected failure.

## Open questions

- The exact YAML sensitive-field redaction policy needs to be finalized during implementation against the Kubernetes object shapes in use. The required invariant is that credentials, tokens, secret data, and kubeconfig material are never returned; any uncertain field must be redacted rather than exposed.
- The initial supported detail resource set should align with feature 7’s pods, deployments, services, and nodes. If workload details need a different composite identity, that is a product/API decision before implementation.
