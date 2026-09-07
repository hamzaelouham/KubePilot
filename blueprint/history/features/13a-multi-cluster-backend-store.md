# Current Feature

**Status:** verified (complete)
**Type:** Feature
**Branch:** feature/multi-cluster-backend-store

## Goal

Feature 13a — **Backend cluster store and management API.** Seed the default
cluster connection row on app startup (from `KUBEPILOT_CLUSTER_NAME`), add
`GET /api/v1/clusters` (list all registered clusters, any authenticated user)
and `POST /api/v1/clusters` (register or import a cluster, admin-only). The
admin can either paste kubeconfig YAML content directly or upload a kubeconfig
file; the backend parses the YAML, extracts the API server endpoint, validates
the structure, and stores the kubeconfig content in the database. This lays
the database and API foundation for the frontend cluster selector (13c) and
the cluster routing layer (13b) that follows.

## In scope

- **Database migration.** Add a `kubeconfig_content` column (TEXT, nullable) to
  the `cluster_connections` table via a new Alembic migration. The existing
  `kubeconfig_ref` column (String(512)) is left in place for backward
  compatibility but is not used by 13a; it can be removed in a later cleanup.
  The migration is reversible.
- **Startup seeding.** On each app startup (inside the existing FastAPI
  `lifespan`), upsert a `cluster_connections` row for the default cluster:
  `name` = `settings.cluster_name`, `endpoint` = `"in-cluster"`,
  `kubeconfig_content` = `None` (the default cluster uses in-cluster
  ServiceAccount auth, not a stored kubeconfig), `status` = `"active"`.
  This must be idempotent (insert-or-update on `name`).
- **List clusters.** `GET /api/v1/clusters` returns all `ClusterConnection`
  rows as `ClusterSummary` objects. Any authenticated user (VIEWER+) may call
  this endpoint. The response does **not** include `kubeconfig_content`
  (sensitive). Response shape:
  ```json
  { "items": [ { "id": "...", "name": "primary", "endpoint": "in-cluster",
    "status": "active", "created_at": "..." } ] }
  ```
- **Register / import a cluster.** `POST /api/v1/clusters` (admin-only,
  requires `CLUSTERS_CREATE` permission). The endpoint accepts two mutually
  exclusive input modes:
  1. **Paste content (JSON).** `Content-Type: application/json` with body:
     ```json
     { "name": "staging", "kubeconfig_content": "<raw kubeconfig YAML string>" }
     ```
  2. **Upload file (multipart).** `Content-Type: multipart/form-data` with
     fields `name` (string) and `kubeconfig_file` (file, `.yaml`/`.yml`).
     The backend reads the file bytes, decodes to UTF-8, and treats the
     result identically to `kubeconfig_content`.

  In both cases the backend:
  - Parses the kubeconfig as YAML (PyYAML).
  - Validates the structure: top-level `clusters` key must be a non-empty list;
    the first entry must have a `cluster.server` string.
  - Extracts the endpoint from `clusters[0].cluster.server`.
  - Stores the full raw YAML text in the `kubeconfig_content` column.
  - Sets `status` = `"active"`.
  - Returns the created `ClusterSummary` (HTTP 201).
  - Audit-logs the event via `record_audit`.

  Error responses:
  - 409 `duplicate_cluster_name` — a cluster with the same `name` already exists.
  - 422 `invalid_kubeconfig` — the YAML is unparseable, missing `clusters`,
    or has no `cluster.server`.
  - 403 `authorization_required` — caller is not admin.

- **Schema module.** Add `backend/app/api/v1/cluster_schemas.py` with:
  - `ClusterSummary` — `id`, `name`, `endpoint`, `status`, `created_at`
    (no `kubeconfig_content` in response).
  - `ClusterListResponse` — `items: list[ClusterSummary]`.
  - `ClusterCreateRequest` — `name: str`, `kubeconfig_content: str | None = None`.
    (The multipart path uses FastAPI `Form` + `UploadFile` instead of this
    model; the schema is for the JSON path only.)

- **Routes module.** Add the two endpoints to `backend/app/api/v1/routes.py`
  (same router as existing `/cluster/*` routes), using `require_permission`
  and the existing `get_database_session` dependency. The POST endpoint
  detects JSON vs multipart via `request.headers["content-type"]` and routes
  accordingly. Audit-log the creation with `action="cluster.create"`,
  `resource_type="cluster_connection"`, `resource_id=<new cluster id>`.

- **Unit tests.** Add `backend/tests/test_cluster_management.py` covering:
  1. Default cluster seeded on startup (name matches `KUBEPILOT_CLUSTER_NAME`,
     `kubeconfig_content` is None, `endpoint` is `"in-cluster"`).
  2. Startup seeding is idempotent (two startups → exactly one row).
  3. `GET /api/v1/clusters` returns at least the default cluster (viewer auth),
     response does not contain `kubeconfig_content`.
  4. `POST /api/v1/clusters` with `kubeconfig_content` (JSON) creates a
     cluster (admin auth), returns 201, `endpoint` extracted correctly,
     `kubeconfig_content` stored.
  5. `POST /api/v1/clusters` with multipart file upload creates a cluster,
     returns 201, `kubeconfig_content` matches uploaded file content.
  6. `POST /api/v1/clusters` with a duplicate name returns 409.
  7. `POST /api/v1/clusters` with invalid kubeconfig YAML returns 422.
  8. `POST /api/v1/clusters` with valid YAML but no `clusters` key returns 422.
  9. `POST /api/v1/clusters` with valid YAML but no `cluster.server` returns 422.
  10. `POST /api/v1/clusters` without admin role returns 403.

## Out of scope

- **Cluster routing (13b).** The existing `/api/v1/cluster/*` routes continue
  to use `get_cluster_client(settings)` unchanged; they are not modified in
  this sub-feature.
- **Frontend cluster selector (13c).** No frontend changes.
- **Admin cluster management page (13d).** No UI.
- **Kubeconfig loading for non-default clusters.** The kubeconfig content is
  stored but not yet loaded into a Kubernetes client; that belongs in 13b.
- **Cluster health checks or status polling.** The `status` field is set on
  creation but not actively monitored yet.
- **Deleting or disabling clusters.** A future sub-feature.
- **User-cluster access control.** All authenticated users see all clusters;
  per-user cluster restrictions are not in scope.

## Build loop

- Create branch `feature/multi-cluster-backend-store` (exact `Branch` value).
- `workflow.stepReview: feature` — build all small steps, then one review packet.
- `workflow.checkpointCommits: disabled` — no per-step checkpoint commits.
- Backend Verify is syntax check + tests: `cd backend && PYTHONPATH=. python3 -m compileall -q app && PYTHONPATH=. python3 -m pytest`.
- Frontend Verify unchanged: `cd k8s-ui && yarn build` (no frontend changes).

## Build steps

- [x] 1. **Add `kubeconfig_content` column migration.** Create a new Alembic
  migration (`backend/alembic/versions/..._add_cluster_kubeconfig_content.py`)
  that adds a nullable TEXT column `kubeconfig_content` to `cluster_connections`.
  The downgrade removes the column. Run `alembic upgrade head` to apply.
  **Done when:** `PYTHONPATH=. python3 -m compileall -q app` passes, and
  `alembic upgrade head --sql` shows the new column in the generated SQL.

- [x] 2. **Update the `ClusterConnection` model.** In
  `backend/app/models/entities.py`, add `kubeconfig_content: Mapped[str | None]`
  (Text, nullable) to `ClusterConnection`. Do not remove `kubeconfig_ref`.
  **Done when:** `python3 -m compileall -q app` passes.

- [x] 3. **Add cluster schemas.** Create `backend/app/api/v1/cluster_schemas.py`
  with `ClusterSummary`, `ClusterListResponse`, and `ClusterCreateRequest`
  models, following the `users_schemas.py` pattern. `ClusterSummary` omits
  `kubeconfig_content`.
  **Done when:** `python3 -m compileall -q app` passes.

- [x] 4. **Add startup seeding.** In the `lifespan` function in
  `backend/app/main.py`, after loading `Settings`, upsert the default cluster
  row: `SELECT` by `name`; if absent, `INSERT` with `endpoint="in-cluster"`,
  `kubeconfig_content=None`, `status="active"`. Use a direct database session
  within the lifespan context. Confirm idempotency in a test.
  **Done when:** `python3 -m compileall -q app` passes, and a pytest test
  confirms exactly one row is seeded after two startup cycles, with
  `kubeconfig_content is None`.

- [x] 5. **Add GET /api/v1/clusters.** Add the list endpoint to
  `backend/app/api/v1/routes.py`, using
  `require_permission(Permission.CLUSTERS_READ)`. Return `ClusterListResponse`
  with all rows; exclude `kubeconfig_content` from the response.
  **Done when:** a pytest test confirms a viewer can list clusters and
  receives at least the default cluster (no `kubeconfig_content` in response).

- [x] 6. **Add POST /api/v1/clusters.** Add the create endpoint to
  `backend/app/api/v1/routes.py`, using
  `require_permission(Permission.CLUSTERS_CREATE)`. Accept JSON body
  (`ClusterCreateRequest` with `kubeconfig_content`) **or** multipart form
  (`name` + `kubeconfig_file` UploadFile). Detect via content-type. Parse
  the kubeconfig as YAML (PyYAML), validate `clusters[0].cluster.server`
  exists, extract endpoint, store `kubeconfig_content` (the raw YAML text),
  insert row, audit-log, return 201. Handle `IntegrityError` → 409,
  `yaml.YAMLError` / missing structure → 422. Return 422 if both
  `kubeconfig_content` and `kubeconfig_file` are absent.
  **Done when:** pytest tests confirm: admin JSON create (201), admin file
  upload create (201), duplicate name (409), invalid YAML (422), missing
  `clusters` key (422), missing `cluster.server` (422), non-admin (403).

- [x] 7. **Run full verification.** Run the full backend Verify:
  `cd backend && PYTHONPATH=. python3 -m compileall -q app && PYTHONPATH=. python3 -m pytest`.
  Confirm all new and existing tests pass.
  **Done when:** compileall passes, all pytest tests pass,
  `cd k8s-ui && yarn build` still passes.

## Files / areas

- `backend/alembic/versions/..._add_cluster_kubeconfig_content.py` (new) — migration.
- `backend/app/models/entities.py` — add `kubeconfig_content` to `ClusterConnection`.
- `backend/app/api/v1/cluster_schemas.py` (new) — Pydantic response/request models.
- `backend/app/api/v1/routes.py` — add `GET /clusters` and `POST /clusters`.
- `backend/app/main.py` — add startup seeding in `lifespan`.
- `backend/app/core/rbac.py` — `Permission.CLUSTERS_READ` and `CLUSTERS_CREATE` (already defined, read-only).
- `backend/app/core/dependencies.py` — `get_database_session` (used for seeding, read-only).
- `backend/tests/test_cluster_management.py` (new) — unit tests.

## Data / contracts

- **`ClusterConnection`** (after migration):
  - `id`: UUID PK
  - `name`: String(120), unique, not null
  - `endpoint`: String(2048), not null
  - `kubeconfig_ref`: String(512), not null (legacy, unused by 13a)
  - `kubeconfig_content`: Text, nullable (new — stores raw kubeconfig YAML)
  - `status`: String(32), default `"unknown"`, indexed
  - `created_at`: DateTime with timezone
- **`GET /api/v1/clusters`** response:
  ```json
  { "items": [ { "id": "uuid", "name": "primary", "endpoint": "in-cluster",
    "status": "active", "created_at": "ISO8601" } ] }
  ```
- **`POST /api/v1/clusters`** — JSON path request:
  ```json
  { "name": "staging", "kubeconfig_content": "apiVersion: v1\nclusters:\n..." }
  ```
- **`POST /api/v1/clusters`** — multipart path: `name` (form field) +
  `kubeconfig_file` (file upload, `.yaml`/`.yml`).
- Both paths return (201):
  ```json
  { "id": "uuid", "name": "staging", "endpoint": "https://10.0.0.1:6443",
    "status": "active", "created_at": "ISO8601" }
  ```
- Error codes: 409 `duplicate_cluster_name`, 422 `invalid_kubeconfig`,
  403 `authorization_required`.
- **Audit event** on create: `action="cluster.create"`,
  `resource_type="cluster_connection"`, `resource_id=<new cluster UUID>`,
  `actor_id=<current user UUID>`, `result="success"`.
- **Environment variables** (already exist):
  - `KUBEPILOT_CLUSTER_NAME` — default cluster name (default `"primary"`).

## Testing

- **Backend (`logicTests: when-configured`):** run
  `cd backend && PYTHONPATH=. python3 -m compileall -q app` (syntax) and
  `PYTHONPATH=. python3 -m pytest` (unit tests).
- **Frontend:** `cd k8s-ui && yarn build` (no changes, must still pass).
- **Manual (none):** no UI changes in this sub-feature.

## Notes for the AI

- Follow the existing patterns: Pydantic schemas with `ConfigDict(extra="forbid")`,
  `require_permission` for RBAC, `record_audit` for audit events,
  `get_database_session` for database access, `IntegrityError` catch for
  duplicate-name handling.
- For the multipart upload path, use FastAPI's `UploadFile` and `Form`/
  `File` dependencies directly on the route function (not a Pydantic model).
  Read the file content with `await file.read()`, decode UTF-8, then parse
  as YAML with `yaml.safe_load()`.
- Kubeconfig parsing: `yaml.safe_load(content)` → expect `dict` with key
  `clusters` → expect `list` with at least one entry → expect
  `entry["cluster"]["server"]` as a string. On any `yaml.YAMLError`,
  `KeyError`, `IndexError`, or `TypeError`, raise `HTTPException(422)`
  with `code="invalid_kubeconfig"`.
- The seeding code in `lifespan` runs on every startup and must be idempotent
  (upsert: `SELECT` → `INSERT` if absent, no-op if present). The default
  cluster's `kubeconfig_content` is `None` (it uses in-cluster ServiceAccount
  auth). Its `endpoint` is the literal string `"in-cluster"`.
- Do not modify any existing `/api/v1/cluster/*` routes — those stay single-cluster
  until 13b.
- Run `PYTHONPATH=. python3 -m pytest -x` after each step to confirm no regressions.
- Pre-existing tests in `backend/tests/` must not break; run the full suite
  at the end of step 7.
- `pyyaml` is already in `backend/requirements.txt` (used by the Kubernetes
  client); confirm before adding it.

## Open questions

- None. All material choices (kubeconfig stored in DB as TEXT, JSON + multipart
  dual input, PyYAML parsing, `clusters[0].cluster.server` extraction,
  `kubeconfig_content` excluded from list response, seeding with `None`
  content) are reversible internal decisions with no user-visible, security,
  or persisted-data consequence at this stage.