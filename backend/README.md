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
```

The service reads environment variables directly. Do not commit real `.env` files or secret values.

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

The health request returns `200` with `{"status":"ok","service":"kubepilot-api"}` by default. The auth context request returns `401` until a future authentication adapter places a server-derived actor in the request state. No endpoint in this foundation connects to PostgreSQL or Kubernetes.

## Checks

```bash
python -m compileall -q app
cd ../k8s-ui && yarn build
```
