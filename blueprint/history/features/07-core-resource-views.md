# Core resource views

**Branch:** feature/core-resource-views

**Status:** verified

## Goal

Replace the dashboard’s core mock resource tables with live, status-driven views for pods, deployments, services, and nodes loaded through the protected FastAPI API. Establish the approved shared signed HTTP-only session-cookie bridge so FastAPI validates the session with the shared secret and retrieves the authenticated user from PostgreSQL before returning Kubernetes data.

## In scope

- Replace the current unsigned frontend session payload with a shared signed cookie format containing only the minimum identity/expiry claims needed for verification.
- Add FastAPI cookie validation and PostgreSQL user/session lookup for protected API requests; reject missing, expired, malformed, tampered, or unknown sessions without revealing authentication details.
- Add a same-origin Next.js server-side API path that forwards the session cookie to FastAPI while keeping Kubernetes credentials and client libraries backend-only.
- Fetch and render live pods, deployments, services, and nodes using feature 6’s typed discovery contract, including namespace selection and loading, empty, unavailable, forbidden, and unexpected-error states.
- Preserve the existing operational dashboard hierarchy while making the data source and connection state clear to operators.

## Out of scope

- Resource detail pages, YAML, logs, events, watch streams, or real-time refresh; these belong to later features.
- Scale, restart, delete, exec, or any other Kubernetes mutation.
- Multiple clusters, kubeconfig uploads, frontend Kubernetes client code, or exposing cluster credentials.
- New user registration, password reset, RBAC administration, or changing the local admin account model beyond session lookup.
- Persisting live resource snapshots or replacing Kubernetes as the source of truth.
- AI implementation; future AI requests must use the same protected FastAPI API.

## Build loop

The configured workflow uses `workflow.stepReview: "feature"` and `workflow.checkpointCommits: "disabled"`. Continuous Mode may progress through the steps without interactive pauses, then archive and locally squash-merge the feature without pushing. The final automated checks are the documented backend pytest command and frontend `yarn build`; live-cluster and browser evidence must be reported separately from deterministic tests.

## Build steps

- [x] 1. **Implement the shared signed session contract** - sign the Next.js session cookie with the shared secret and add FastAPI validation plus PostgreSQL user/session lookup.
	- Done when: valid shared-cookie requests resolve the stored user, missing/expired/tampered/unknown sessions return the stable `401` authentication error, the cookie remains HTTP-only and secure in production, and focused auth tests pass without a live database.

- [x] 2. **Add the same-origin protected API path** - connect the dashboard’s server/client boundary to FastAPI without exposing Kubernetes credentials or trusting browser identity fields.
	- Done when: browser-origin requests forward the session cookie to FastAPI, protected requests cannot be forged with email/role query or body fields, and no frontend module imports the Kubernetes client or receives ServiceAccount data; focused proxy tests or build checks pass.

- [x] 3. **Render live core resource views** - load pods, deployments, services, and nodes from the protected discovery API and map them into the existing dashboard tables.
	- Done when: each supported view displays typed data for the selected namespace, nodes remain cluster-scoped, loading/empty/error states are readable, and mock fixtures are not presented as live data; direct browser verification is required when the frontend and backend can run together.

- [x] 4. **Verify status-driven dashboard behavior** - cover navigation, namespace switching, source/error states, and regression behavior with focused checks.
	- Done when: `cd backend && python3 -m pytest`, `cd backend && python3 -m compileall -q app`, and `cd k8s-ui && yarn build` pass; a live-cluster smoke path is documented without claiming it was run unless a configured cluster is available.

## Files / areas

- `k8s-ui/lib/auth.ts`, `k8s-ui/middleware.ts`, and `k8s-ui/app/login/actions.ts` for the shared cookie signing and route guard contract
- `backend/app/core/` for cookie parsing, HMAC verification, and authenticated-user dependencies
- `backend/app/db/` and `backend/app/models/entities.py` for read-only session/user lookup
- `backend/app/api/v1/` for protected discovery responses and auth errors
- `k8s-ui/app/api/` or another server-side Next.js data boundary for same-origin forwarding
- `k8s-ui/app/dashboard/page.tsx` and `k8s-ui/components/dashboard-shell.tsx` for live resource views and state presentation
- `backend/tests/` and `k8s-ui/` checks for auth, proxy, and resource contracts
- `backend/README.md` and `AGENTS.md` for shared-secret and local verification instructions

The existing Kubernetes adapter and ServiceAccount policy remain the backend-only access boundary established by feature 6.

## Data / contracts

- Cookie name remains `kubepilot_session`; its value is a documented base64url payload plus HMAC-SHA256 signature. The payload contains a normalized email and Unix expiry only; no password, database URL, Kubernetes token, kubeconfig, or raw secret is included.
- Next.js signs the cookie with `KUBEPILOT_AUTH_SECRET`; FastAPI uses the same secret and constant-time signature comparison, then checks expiry and loads the matching `UserAccount` and active `Session` record from PostgreSQL. Legacy unsigned JSON cookies are invalid.
- The cookie is HTTP-only, `SameSite=Lax`, path `/`, secure when `NODE_ENV=production`, and expires at the session lifetime. The shared secret is server-only and never sent to browser JavaScript, API responses, or logs.
- Authentication failures return HTTP `401` with `{ "code": "authentication_required", "message": "Authentication is required" }` regardless of whether the cookie is missing, malformed, expired, tampered, or unknown.
- The same-origin frontend path forwards the browser cookie server-side to the FastAPI routes from feature 6. It does not accept actor identity from query parameters, request JSON, or client-controlled headers.
- Protected resource calls use `/api/v1/cluster/resources/{resource_type}` with resource types `pods`, `deployments`, `services`, and `nodes`. The selected namespace is passed only for namespaced resources; nodes remain cluster-scoped.
- The frontend distinguishes `loading`, `ready`, `empty`, `unauthenticated`, `forbidden`, `unavailable`, and unexpected error states. It never labels mock data as live data after a live request has been attempted.
- FastAPI remains the only component with Kubernetes credentials. PostgreSQL stores application users/sessions, while Kubernetes remains the source of truth for live resources.

## Testing

The repository has a Python pytest runner. Add deterministic tests for cookie signing vectors, expiry/tamper rejection, user/session lookup, protected route errors, namespace forwarding, and typed resource normalization. Use fake database/Kubernetes adapters; no test requires PostgreSQL, Kubernetes, network access, or external credentials. Use the existing frontend build for TypeScript regression and direct browser checks only when both services can run. Do not claim live-cluster evidence without a configured ServiceAccount environment.

## Notes for the AI

- Use HMAC-SHA256 with constant-time verification and minimal claims. Do not retain or trust the current unsigned JSON cookie.
- Keep the auth bridge and Kubernetes adapter separate: FastAPI authenticates the application user, then accesses Kubernetes through its ServiceAccount and RBAC.
- Do not add mutation endpoints, detail/log/event surfaces, multi-cluster behavior, or AI code in this feature.
- Keep user-facing errors concise and actionable while preserving the same non-sensitive backend error envelope.

## Open questions

- The existing local login action validates credentials in Next.js, while the approved contract requires a PostgreSQL-backed session record. Implementation chose the compatible server-side login handoff that creates the database session without exposing credentials to the browser.
