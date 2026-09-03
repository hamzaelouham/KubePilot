# Feature 9a - Containerize the services

Archive of build-plan sub-feature 9a. **Status:** verified, completed and merged.

## Implemented spec

**Status:** verified
**Branch:** feature/containerize-the-services

## Goal

Containerize the three application services — the Next.js frontend, the FastAPI backend, and PostgreSQL — as reproducible, buildable Docker images with a local Docker Compose runtime so the full stack runs consistently and can later be deployed to Minikube as Kubernetes workloads.

## In scope

- Add a multi-stage `Dockerfile` for the FastAPI backend that installs pinned Python dependencies, runs Alembic migrations, and starts the service with the production runner.
- Add a multi-stage `Dockerfile` for the Next.js frontend that builds the production bundle and serves it with the declared production server.
- Add a root `docker-compose.yml` that runs the PostgreSQL database, the migrated FastAPI backend, and the built Next.js frontend together with environment variables wired from a local env file, defaulting to a single shared cluster identity.
- Add `.dockerignore` files for backend and frontend (and a root one where useful) so build context excludes local state, caches, and secrets.
- Document the container build and local run commands, including env vars and how the frontend reaches the backend, in `backend/README.md` and at the repo root as appropriate.
- Keep Kubernetes credentials backend-only: the containerized backend must still read cluster configuration from the in-cluster ServiceAccount path (unchanged behavior), and the frontend image must contain no Kubernetes client or credential material.

## Out of scope

- Kubernetes Deployment/Service manifests, ConfigMap/Secret wiring, Ingress, or any Minikube orchestration; those belong to sub-feature 9b.
- Helm charts or kustomize overlays; those belong to 9b.
- Publishing images to a container registry.
- Changing the backend or frontend application code beyond what is needed to build and run cleanly in a container.
- CI/CD pipelines or image build automation.
- Modifying the default-local SQLite development workflow unless a container runtime replaces it.

## Build steps

- [x] 1. **Add backend Dockerfile and dockerignore** - multi-stage FastAPI Dockerfile (Python 3.12), Alembic migration entrypoint, non-root runtime user, `.dockerignore` excluding venv/caches/env/secret files.
- [x] 2. **Add frontend Dockerfile and dockerignore** - multi-stage Next.js Dockerfile building the production bundle and serving it with the declared start command, `.dockerignore` excluding node_modules/.next/env/secret files.
- [x] 3. **Add docker-compose.yml** - PostgreSQL 16, migrated backend, built frontend wired with env from a local env file and safe defaults; health checks and dependency ordering.
- [x] 4. **Document container usage** - `backend/README.md` Container section (build/run commands, env var table, frontend-to-backend URL wiring) plus root `.env.example`.
- [x] 5. **Verify container build and runtime** - backend and frontend images build, pytest/compileall pass, frontend build passes, compose config validates, and the live stack brought up against a real Docker daemon and Minikube.

## Files / areas

- `backend/Dockerfile` (new) - multi-stage Python 3.12, `alembic upgrade head && uvicorn ... --port 8000`, non-root user.
- `backend/.dockerignore` (new)
- `k8s-ui/Dockerfile` (new) - multi-stage Node 22, `yarn build` then `yarn start` on port 3000, non-root user.
- `k8s-ui/.dockerignore` (new)
- `docker-compose.yml` (new, repo root)
- `.env.example` (new, repo root) - compose env template with safe local defaults.
- `backend/README.md` - Container section documenting build/run and the env contract.
- `backend/.env.example` - host DATABASE_URL updated to the psycopg 3 driver scheme.
- `.gitignore` (repo root) - ignores `.env`, `.env.local`, `*.db`, `*.db-journal`, `.docker`.

## Data / contracts

- Backend image: reads `KUBEPILOT_AUTH_SECRET`, `KUBEPILOT_DATABASE_URL`, `KUBEPILOT_CLUSTER_NAME`, `KUBEPILOT_SERVICE_NAME`, `KUBEPILOT_ADMIN_EMAIL`, `KUBEPILOT_ADMIN_PASSWORD` from the runtime environment; non-root; no kubeconfig volume or `KUBECONFIG`; in-cluster ServiceAccount path unchanged.
- Frontend image: builds with `yarn` lockfile, serves the production bundle on port 3000; reads `KUBEPILOT_BACKEND_URL` (default `http://backend:8000`) and `KUBEPILOT_CLUSTER_NAME`; proxies same-origin `/api` calls and forwards only the session cookie.
- Compose: `postgres:16-alpine` with a named volume; backend runs migrations on start after the database is healthy; frontend depends on backend health; env from a local `.env` with a required `KUBEPILOT_AUTH_SECRET` (at least 32 chars).
- Database URL uses the psycopg 3 driver (`postgresql+psycopg://`) to match the pinned `psycopg[binary]` dependency.

## Implementation notes

- **Psycopg driver resolution (bug found during runtime verification):** the project pinned psycopg 3 (`psycopg[binary]`) but its PostgreSQL URLs used the plain `postgresql://` scheme, which SQLAlchemy routes to the psycopg2 driver that is not installed. This broke the containerized backend's `alembic upgrade head`. Fixed by using `postgresql+psycopg://` (the psycopg 3 dialect) in `docker-compose.yml`, `backend/.env.example`, and the README contract, so both Alembic and the app's `create_engine` work against Postgres with the already-pinned driver.
- **Live runtime evidence:** the full stack was brought up (`docker compose up -d`) on the local Docker daemon alongside Minikube and observed healthy: `backend` healthy on `0.0.0.0:8000`, `db` healthy on 5432, `frontend` on `:3000`. `GET /api/v1/health` returned `200 {"status":"ok","service":"kubepilot-api"}`; `GET /` returned `200`.
- **Automated gate:** `cd backend && python3 -m pytest` (21 passed), `python3 -m compileall -q app` OK, `cd k8s-ui && yarn build` Done, `docker compose config` valid.

## Findings

> The findings ledger held no entries at completion; there was nothing to archive.

## Independent review

> No independent review was requested for this work item; `blueprint/context/review.md` held the empty stub at completion.
