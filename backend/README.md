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

## Kubernetes deployment

Deploy `deploy/kubernetes/service-account.yaml` in the backend namespace before enabling discovery. It grants the backend ServiceAccount only `get`, `list`, and `watch` access to namespaces, pods, services, endpoints, nodes, and deployments. The backend must run in a cluster so the Kubernetes client can use its in-cluster ServiceAccount; it does not accept kubeconfig uploads or request-supplied tokens.

Protected discovery endpoints are `/api/v1/cluster/status`, `/api/v1/cluster/namespaces`, and `/api/v1/cluster/resources/{resource_type}`. The browser and AI integrations reach these through FastAPI and never contact Kubernetes directly.

## Checks

```bash
python -m compileall -q app
python -m pytest
PYTHONPATH=. alembic upgrade head --sql > /tmp/kubepilot-upgrade.sql
PYTHONPATH=. alembic downgrade dd752e8644a9:base --sql > /tmp/kubepilot-downgrade.sql
cd ../k8s-ui && yarn build
```
