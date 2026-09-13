# KubePilot API

The backend is a standalone FastAPI service. It currently provides the versioned health contract and shared configuration, authentication-context, and database-session boundaries. PostgreSQL tables and Kubernetes access are planned features.

## Local setup

Use Python 3.12 or a compatible Python 3.11+ runtime, create a virtual environment, and install the dependencies:

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
export KUBEPILOT_AUTH_SECRET="replace-with-at-least-32-random-characters"
export KUBEPILOT_DATABASE_URL="postgresql://kubepilot:change-me@localhost:5432/kubepilot"
export KUBEPILOT_CLUSTER_NAME="primary"
```

The service reads environment variables directly. Do not commit real `.env` files or secret values.

For a local smoke run without PostgreSQL, use `KUBEPILOT_DATABASE_URL=sqlite:///./dev.db`; initialize it with `PYTHONPATH=. alembic upgrade head` before starting FastAPI. Production deployments must use PostgreSQL.

## Run

```bash
cd backend
PYTHONPATH=. uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Check the service:

```bash
curl -i http://127.0.0.1:8000/api/v1/health
curl -i http://127.0.0.1:8000/api/v1/auth/context
```

The health request returns `200` with `{"status":"ok","service":"kubepilot-api"}` by default. Protected requests use the shared `kubepilot_session` HMAC-SHA256 cookie and load the user from PostgreSQL before reaching discovery. Discovery endpoints connect to Kubernetes only through the backend ServiceAccount path.

## Kubernetes deployment (Minikube)

The platform deploys as Kubernetes workloads into a local Minikube cluster. `kubectl` is not on the host PATH, so use the bundled `minikube kubectl --` wrapper. All workloads and the backend ServiceAccount live in the `kubepilot` namespace.

```bash
# 1. Build the images (reuses the 9a Dockerfiles)
docker build -t kubepilot-backend ./backend && docker build -t kubepilot-ui ./k8s-ui

# 2. Load them into Minikube's own daemon (not a registry)
minikube image load kubepilot-backend:latest kubepilot-ui:latest

# 3. Apply all workloads and RBAC
minikube kubectl -- apply -f deploy/kubernetes/

# 4. Open the UI (NodePort 30080) in the browser
minikube service kubepilot-ui -n kubepilot

# Teardown
minikube kubectl -- delete -f deploy/kubernetes/
```

- Postgres (`postgres-deploy`, PVC `postgres-data`, `db` Service on 5432), the FastAPI backend (`backend` Service on 8000), and the Next.js frontend (NodePort `kubepilot-ui` on 30080) are defined under `deploy/kubernetes/`.
- `deploy/kubernetes/service-account.yaml` grants the backend ServiceAccount `kubepilot-api` only `get`, `list`, and `watch` access to namespaces, pods, services, endpoints, nodes, and deployments (enforced by `tests/test_rbac.py`). The backend must run in a cluster so the Kubernetes client can use its in-cluster ServiceAccount; it does not accept kubeconfig uploads or request-supplied tokens.
- Non-secret env comes from the `kubepilot-config` ConfigMap; secrets (`KUBEPILOT_AUTH_SECRET`, DB credentials, admin password) from the `kubepilot-secret` Secret. The committed Secret holds local Minikube dev placeholder values and must be overridden for any non-local deployment.

Protected discovery endpoints are `/api/v1/cluster/status`, `/api/v1/cluster/namespaces`, and `/api/v1/cluster/resources/{resource_type}`. The browser and AI integrations reach these through the Next.js `/api` proxy and FastAPI, and never contact Kubernetes directly.

## Container

The backend, frontend, and database can run together with Docker Compose from the repository root:

```bash
cp .env.example .env   # or provide KUBEPILOT_AUTH_SECRET etc. in your shell
docker compose up --build
```

This starts PostgreSQL (`postgres:16-alpine`), the migrated FastAPI backend on `http://127.0.0.1:8000`, and the built Next.js frontend on `http://127.0.0.1:3000`. The backend applies Alembic migrations on start and reads all configuration from environment variables; the frontend proxies same-origin `/api` calls to the backend and forwards only the session cookie, never Kubernetes credentials.

Build an image alone with `docker build -t kubepilot-backend ./backend` or `docker build -t kubepilot-ui ./k8s-ui`. Both images run as a non-root user and never bake secrets or kubeconfigs into a layer; the containerized backend still authenticates to Kubernetes only through its in-cluster ServiceAccount.

Required environment variables (with local-safe defaults for Compose):

| Variable | Default | Notes |
| --- | --- | --- |
| `KUBEPILOT_AUTH_SECRET` | required | At least 32 characters; shared by backend and frontend |
| `KUBEPILOT_DATABASE_URL` | composed | `postgresql+psycopg://<user>:<password>@db:5432/<db>` (psycopg 3 driver) |
| `KUBEPILOT_DB_USER` / `KUBEPILOT_DB_PASSWORD` / `KUBEPILOT_DB_NAME` | `kubepilot` / `change-me` / `kubepilot` | Sets the PostgreSQL image and the backend URL |
| `KUBEPILOT_CLUSTER_NAME` | `primary` | Cluster identity used by the frontend and backend |
| `KUBEPILOT_SERVICE_NAME` | `kubepilot-api` | Backend service name |
| `KUBEPILOT_ADMIN_EMAIL` / `KUBEPILOT_ADMIN_PASSWORD` | `ops@kubepilot.io` / `kubepilot` | Local admin login |
| `KUBEPILOT_BACKEND_URL` | `http://backend:8000` | Frontend-only; where the frontend proxies `/api` calls |
| `KUBEPILOT_AI_MODEL` / `AI_GATEWAY_API_KEY` | (empty) | Optional: enables the AI Assistant (Next.js runtime only). Set a tool-capable model identifier enabled in your AI Gateway account; the key stays server-side and is never exposed to the browser. |

## AI Assistant (optional)

When `KUBEPILOT_AI_MODEL` and `AI_GATEWAY_API_KEY` are set in the frontend runtime,
the sidebar **AI Assistant** route is available to signed-in users with resource
read access. It stream-responds with a tool-capable model through the AI SDK:
read tools inspect the selected cluster/namespace, and every write action
(scale, restart, delete, install, upgrade, rollback, uninstall) is staged as an
immutable 10-minute proposal that the user must type-confirm in the review card
before the backend dispatches it. The model never receives Secret/ConfigMap
data, raw manifests, or environment values, and never touches Kubernetes
directly. Without these two variables the assistant returns a clear
"not configured" error and changes nothing.

## Checks

```bash
python -m compileall -q app
python -m pytest
PYTHONPATH=. alembic upgrade head --sql > /tmp/kubepilot-upgrade.sql
PYTHONPATH=. alembic downgrade dd752e8644a9:base --sql > /tmp/kubepilot-downgrade.sql
cd ../k8s-ui && yarn build
```
