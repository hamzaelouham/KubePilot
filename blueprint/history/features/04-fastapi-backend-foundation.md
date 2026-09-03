# FastAPI backend foundation

**Branch:** feature/fastapi-backend-foundation

**Status:** verified

## Goal

Create the first runnable FastAPI service for KubePilot. It will establish a typed, versioned API boundary for the Next.js frontend, centralize backend configuration and authentication context, provide a health endpoint for local and self-hosted operations, and expose a database dependency seam for the next persistence feature without implementing application tables or live Kubernetes access yet.

## In scope

- Add an adjacent `backend/` Python service with a FastAPI application entry point.
- Add a versioned API namespace and a health endpoint that reports service readiness without exposing secrets or connection strings.
- Add typed environment-backed settings for the API runtime, auth secret/configuration, and PostgreSQL connection configuration.
- Add shared request/response schemas and error handling for the foundation endpoints.
- Add an application dependency boundary for the authenticated actor and database session so later routes use one server-side path.
- Add backend startup and local development documentation with the exact commands and required environment names.
- Keep frontend authentication as the current route/session enforcement boundary until the backend auth integration is explicitly implemented.

## Out of scope

- PostgreSQL tables, migrations, repositories, or durable users and sessions; those belong to feature 5.
- Kubernetes client initialization, kubeconfig handling, cluster discovery, namespace discovery, or resource endpoints; those belong to feature 6.
- Replacing the existing Next.js login flow or moving session issuance into FastAPI.
- RBAC, multi-user administration, cluster-level authorization, or operational mutations.
- Frontend dashboard data wiring, proxy routes, real-time updates, or deployment-provider configuration.

## Build loop

This feature follows the configured workflow: `workflow.stepReview: "feature"` provides one feature-level review packet, and `workflow.checkpointCommits: "disabled"` keeps intermediate commits optional. The feature is complete only when the backend starts locally, its health contract is observable, invalid configuration fails clearly, and the existing frontend build remains passing.

## Build steps

- [x] 1. **Create the FastAPI service skeleton** - add the backend package, application factory/entry point, dependency manifest, and local run documentation.
	- Done when: starting the documented backend command imports the FastAPI app and serves the versioned API namespace without importing frontend code; a Python syntax/import check and the documented frontend `yarn build` both pass.

- [x] 2. **Add typed settings and safe error boundaries** - load required runtime configuration from environment variables, validate it at startup, and return structured API errors without leaking secrets.
	- Done when: valid configuration starts the service, missing or malformed required configuration produces a clear startup failure, and an API error response contains a stable non-sensitive error shape; verify with the backend’s documented smoke commands.

- [x] 3. **Expose the foundation health contract** - implement the versioned health/readiness route and shared response schema, with database readiness represented through the dependency boundary rather than an implicit live connection.
	- Done when: `GET /api/v1/health` returns the documented success shape when the service is configured, service failure returns an appropriate non-2xx response with the same error envelope, and no credential, URL, or secret value appears in responses or logs; verify with a running local service and HTTP requests.

- [x] 4. **Establish auth and database dependency seams** - add request-scoped interfaces/dependencies for the current authenticated actor and database session without creating persistence or changing the frontend session contract.
	- Done when: a protected backend route can require the shared actor dependency and reject a missing/invalid auth context, a database-dependent route can receive the shared session dependency, and focused Python checks cover the dependency outcomes without requiring a live PostgreSQL or Kubernetes cluster.

## Files / areas

- `backend/pyproject.toml` or the repository-native Python dependency manifest
- `backend/app/main.py` and the FastAPI application package
- `backend/app/api/v1/` for versioned routes, including the health route
- `backend/app/core/` for settings, error handling, and auth context dependencies
- `backend/app/db/` for the database configuration/session dependency seam only
- `backend/README.md` or the repository root setup documentation for backend commands and environment names
- `AGENTS.md` for the documented backend verification command once it exists

The existing frontend remains under `k8s-ui/`; no current frontend route needs to be changed to make this foundation reachable.

## Data / contracts

- Service process: FastAPI served by Uvicorn from the backend package; the exact supported Python version and dependency lock format must be recorded from the repository’s selected environment during implementation.
- API prefix: `/api/v1` is the stable namespace for this service. Unknown routes use the framework’s normal not-found behavior; known application errors use one JSON envelope with a machine-readable `code` and concise `message`.
- Health endpoint: `GET /api/v1/health` returns JSON with `status` (`ok` or `degraded`) and a service identifier. It never returns credentials, raw connection strings, auth secrets, or exception tracebacks.
- Configuration: settings are read from environment variables at process startup. Required values and safe defaults must be explicit in documentation; missing required values stop startup rather than silently selecting insecure credentials or endpoints.
- Database boundary: the database dependency owns creation and cleanup of a request-scoped session when enabled, but this feature creates no tables and does not claim database health unless a real connection check is implemented and configured.
- Actor boundary: backend authorization receives a server-derived authenticated actor/context, not an email, role, or user id trusted from request JSON or query parameters. Missing or invalid context is rejected with a non-sensitive authorization error.
- Client/server responsibilities: the Next.js app continues to own browser login, its session cookie, and frontend route protection. FastAPI owns API validation, backend dependencies, response errors, and future server-side authorization integration.

## Testing

The repository has no configured test runner today. This feature must not invent a test gate solely to complete the setup. Add focused Python tests only if a backend-native runner is introduced as part of the service skeleton, and document the exact command in `AGENTS.md`. At minimum, verification must use the real backend process or import path for startup, health success/failure, configuration validation, and dependency rejection, plus the existing `cd k8s-ui && yarn build` command for regression coverage.

## Notes for the AI

- Keep the backend independently runnable from `backend/`; do not couple its import path to Next.js or Node tooling.
- Use typed Pydantic models for request and response contracts and keep error messages actionable but non-sensitive.
- Keep secrets in environment-backed configuration and avoid logging their values.
- Do not add PostgreSQL schema design, Kubernetes clients, or frontend API calls early; those are later planned features with their own contracts.
- Preserve the current local frontend auth behavior while creating the backend boundary needed for a later integration.

## Open questions

- The first production topology remains unresolved in the project overview (self-hosted Kubernetes, Docker Compose, internal VM, or another private deployment). This does not block a locally runnable service, but deployment-specific files should wait for that decision.
- The exact backend authentication bridge to the existing Next.js session cookie is intentionally deferred; before FastAPI serves protected product data, the project must choose whether the backend validates a shared signed token, receives a trusted server-to-server identity, or adopts another explicit session contract.
