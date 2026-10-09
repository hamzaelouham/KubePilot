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

# 3. Apply all workloads and RBAC (or use `./deploy.sh` from the repository root)
minikube kubectl -- apply -f deploy/kubernetes/

# 4. Open the UI (NodePort 30080) in the browser
minikube service kubepilot-ui -n kubepilot

# Teardown
minikube kubectl -- delete -f deploy/kubernetes/
```

- Postgres (`postgres-deploy`, PVC `postgres-data`, `db` Service on 5432), the FastAPI backend (`backend` Service on 8000), and the Next.js frontend (NodePort `kubepilot-ui` on 30080) are defined under `deploy/kubernetes/`.
- `deploy/kubernetes/service-account.yaml` binds `kubepilot-api` to explicit discovery and operations roles, tested by `tests/test_rbac.py`. Discovery remains read-only, including pod logs and metrics. Operations allow get/list/watch/create/update/patch/delete on core pods, services, namespaces, configmaps, secrets, serviceaccounts, PVCs and replicationcontrollers; apps deployments, replicasets, daemonsets and statefulsets; batch jobs/cronjobs; networking ingresses/networkpolicies; autoscaling HPAs; and policy PDBs. In-cluster operations use this ServiceAccount; managed clusters use their registered kubeconfig permissions.
- Non-secret env comes from `kubepilot-config`; provision `kubepilot-secret` externally before applying workloads. No deployable Secret is stored in Git. Include POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, KUBEPILOT_DATABASE_URL, KUBEPILOT_AUTH_SECRET, KUBEPILOT_ADMIN_PASSWORD, and KUBEPILOT_ENCRYPTION_KEY. Use unique database/admin passwords and a random authentication secret of at least 32 characters. The database URL must match the provisioned PostgreSQL credentials.
- `./deploy.sh` validates and deploys `backend/deploy/kubernetes/secret.yaml` when that ignored local file exists, before applying database/application workloads. Both `data` and `stringData` are supported; the object must be `kubepilot-secret` in `kubepilot`. Without the file, externally provision the live Secret as before. Invalid/default/incomplete values stop deployment without printing credentials. Existing encryption-key or database credential/URL changes are rejected before Secret writes; changing a Secret alone cannot rotate an initialized PostgreSQL role. If PostgreSQL storage exists but the live Secret is missing, restore the original credentials rather than guessing new ones. Concurrent Secret updates fail rather than overwrite one another. Provision a Fernet key once and retain it securely; losing it prevents access to encrypted credentials and kubeconfigs. Keep the local file untracked; do not use shell tracing when deploying Secrets.

Protected discovery endpoints are `/api/v1/cluster/status`, `/api/v1/cluster/namespaces`, and `/api/v1/cluster/resources/{resource_type}`. The browser and AI integrations reach these through the Next.js `/api` proxy and FastAPI, and never contact Kubernetes directly.

### RBAC limits and upgrades

The backend has no direct permission to write RBAC, CRDs, admission webhooks or
nodes, create service-account tokens, or use pod exec/attach. Charts requiring
those permissions (including typical cert-manager installations) fail through
the existing Kubernetes/Helm error handling. A cluster administrator must
install those components separately or explicitly provision reviewed,
chart-specific permissions. Do not restore cluster-admin automatically.

This is still a privileged workload-management identity: it can read Secrets
across namespaces and create workloads that use other service accounts or
privileged containers where admission policy permits. It does not provide
namespace isolation or prevent indirect escalation. Kubernetes admission policy
and narrowly scoped deployment credentials remain necessary where isolation is
required. Uploaded kubeconfigs retain their own permissions.

For an existing installation, applying YAML alone leaves the old admin binding
active. Run the following only during an authorized rollout, from the repository
root, using a cluster administrator context. Apply the replacement before
removing the old binding; these steps do not delete workloads or application data.

```bash
minikube kubectl -- apply -f backend/deploy/kubernetes/service-account.yaml
minikube kubectl -- delete clusterrolebinding kubepilot-api-admin --ignore-not-found
minikube kubectl -- get clusterrolebinding kubepilot-api-admin --ignore-not-found
```

The final command must produce no object. Effective permissions are additive;
review any other bindings to this ServiceAccount if a denied check returns yes.

```bash
# Expected yes:
minikube kubectl -- auth can-i --as=system:serviceaccount:kubepilot:kubepilot-api list pods --all-namespaces
minikube kubectl -- auth can-i --as=system:serviceaccount:kubepilot:kubepilot-api patch deployments.apps -n default
minikube kubectl -- auth can-i --as=system:serviceaccount:kubepilot:kubepilot-api create secrets -n default
# Expected no:
minikube kubectl -- auth can-i --as=system:serviceaccount:kubepilot:kubepilot-api create clusterrolebindings.rbac.authorization.k8s.io
minikube kubectl -- auth can-i --as=system:serviceaccount:kubepilot:kubepilot-api create customresourcedefinitions.apiextensions.k8s.io
minikube kubectl -- auth can-i --as=system:serviceaccount:kubepilot:kubepilot-api delete nodes
minikube kubectl -- auth can-i --as=system:serviceaccount:kubepilot:kubepilot-api create pods --subresource=exec -n default
```

Verify discovery and supported resource operations through the UI. In a disposable
namespace, test an ordinary workload-only chart and verify a chart needing CRDs
or RBAC fails visibly. A failed Helm installation can leave partial resources;
inspect them before cleanup. Live checks remain pending until the rollout.

## Container

Compose is an explicit local-development path (`KUBEPILOT_LOCAL_DEVELOPMENT=true`)
with frontend/backend ports bound to 127.0.0.1. Generate the required Fernet key
before starting it. Outside this local path, backend startup rejects missing or
development administrator/auth/database credentials. Never enable local mode on
an externally reachable deployment.

### Kubeconfig encryption upgrade

Set KUBEPILOT_ENCRYPTION_KEY to the existing installation encryption key before
running online `alembic upgrade head`. Migration s5h6i7j8k9l0 encrypts legacy
kubeconfigs transactionally in the existing column. It is idempotent and fails
without rewriting records when a key is unavailable. Offline SQL generation and
downgrade across this data migration are intentionally rejected. Back up the
database and key before upgrading; older code cannot consume the ciphertext.
Kubernetes/Helm readers decrypt through the cluster property only when accessing
the content. Do not rotate the key by simply changing an environment variable.
Old database backups may still contain plaintext and require separate protection.

### Helm sources and worker recovery

Helm indexes and archives must use public HTTP(S) hostnames. DNS addresses,
redirects, and chart archive URLs are checked before connecting; private/IP/local
targets and HTTPS downgrades are denied. Connections use the checked address and
verify TLS against the original hostname. Indexes are capped at 2 MiB and archives
at 50 MiB. Helm receives a local archive instead of fetching repository URLs;
dependencies must already be packaged. Internal repositories, authenticated/query
URLs, and OCI sources are unsupported by this path. Charts remain executable
deployment inputs: only install sources trusted by your operators.

Worker cycles acquire a PostgreSQL session advisory lock (file lock for local
SQLite) before recovery or execution. API startup does not requeue jobs. On
exclusive recovery, interrupted deliveries become outcome_unknown; installations
and agent runs fail with an interruption message instead of being automatically
replayed. Inspect external outcomes before manually starting replacement work.
This guards restarts/replica contention; it does not promise exactly-once delivery
across provider or database network failures.

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
| `KUBEPILOT_ENCRYPTION_KEY` | optional at startup | A unique `cryptography.fernet.Fernet.generate_key()` value kept in Kubernetes Secret; credential operations fail closed when absent or invalid |
| `KUBEPILOT_PROVIDER_ALLOWED_HOSTS` | empty | Comma-separated exact hostnames allowed for private/internal provider endpoints; never editable through Settings |
| `KUBEPILOT_DB_USER` / `KUBEPILOT_DB_PASSWORD` / `KUBEPILOT_DB_NAME` | `kubepilot` / `change-me` / `kubepilot` | Sets the PostgreSQL image and the backend URL |
| `KUBEPILOT_CLUSTER_NAME` | `primary` | Cluster identity used by the frontend and backend |
| `KUBEPILOT_SERVICE_NAME` | `kubepilot-api` | Backend service name |
| `KUBEPILOT_ADMIN_EMAIL` / `KUBEPILOT_ADMIN_PASSWORD` | `ops@kubepilot.io` / `kubepilot` | Local admin login |
| `KUBEPILOT_BACKEND_URL` | `http://backend:8000` | Frontend-only; where the frontend proxies `/api` calls |

Deployment Secrets must use `postgresql+psycopg://` (the installed psycopg 3
driver), a nonempty host and, if supplied, a port from 1 to 65535. URL-encode
special characters in usernames/passwords; their decoded values must match
`POSTGRES_USER` and `POSTGRES_PASSWORD`. The database path must match `POSTGRES_DB`
literally: SQLAlchemy does not decode database-name percent escapes. Query
parameters (including connection overrides or TLS options), fragments and
ambiguous/normalized URL forms are not supported by this deployment path. These
checks run before local Secret writes and also validate externally provisioned
Secrets; no connection to the database is attempted by the validator.

## AI Assistant (optional)

The sidebar **AI Assistant** route is available to signed-in users with resource
read access. To enable responses, configure and test OpenAI, OpenRouter, or Ollama
under **Settings → AI Providers**; create and check a streaming- and tool-capable
model under **Settings → Models**; enable it and set it as the default. The
Assistant stream-responds through the AI SDK while FastAPI keeps the provider
credential encrypted at rest and uses it only for the outbound provider request:
read tools inspect the selected cluster/namespace, and every write action
(scale, restart, delete, install, upgrade, rollback, uninstall) is staged as an
immutable 10-minute proposal that the user must type-confirm in the review card
before the backend dispatches it. The model never receives Secret/ConfigMap
data, raw manifests, or environment values, and never touches Kubernetes
directly. Without an eligible configured default model, the Assistant returns a
clear "not configured" error and changes nothing.

## Checks

```bash
python -m compileall -q app
python -m pytest
PYTHONPATH=. alembic upgrade head --sql > /tmp/kubepilot-upgrade.sql
PYTHONPATH=. alembic downgrade dd752e8644a9:base --sql > /tmp/kubepilot-downgrade.sql
cd ../k8s-ui && yarn build
```
