# Current Feature

**Type:** Feature
**Build plan:** 18h
**Branch:** `feature/installation-status-api`
**Status:** verified

## Goal

Add the installation status API (18h): a backend GET endpoint,
`GET /api/v1/marketplace/installations/{job_id}`, that returns one
`InstallationJob`'s status, package name, cluster name, namespace, release
name, error_message, and useful timestamps. This is the read half that 18i
(progress UI) and 18j (history) build on; no frontend change ships here.

## In scope

- `MarketplaceInstallationStatus` response schema:
  - `job_id: UUID`, `package_name: str`, `cluster: str` (the
    `ClusterConnection.name`), `namespace: str`, `release_name: str`
  - `status: Literal["queued", "running", "succeeded", "failed", "cancelled"]`
  - `error_message: str | None`
  - `created_at: datetime`, `started_at: datetime | None`, `completed_at: datetime | None`
  - `model_config = ConfigDict(extra="forbid")`, matching sibling schemas
- `GET /api/v1/marketplace/installations/{job_id}` in
  `app/api/v1/marketplace.py`:
  - requires an authenticated actor (`get_current_actor`), same as every other
    marketplace endpoint; no per-cluster or per-role authorization exists yet
    and none is invented here (18k remains the authorization gate)
  - `job_id` is a typed `uuid.UUID` path parameter (invalid UUID → FastAPI 422,
    existing behavior for typed path params)
  - resolves `cluster.name` via the existing `InstallationJob.cluster`
    relationship; job not found → HTTP 404 with
    `detail={"code": "installation_not_found", "message": "Installation job was not found"}`
  - pure database read: no Artifact Hub call, no cluster client, no worker call
- Focused endpoint tests in `tests/test_marketplace.py`, seeding
  `InstallationJob` rows directly through `create_session_factory(api.settings)`
  (the `_add_job` pattern from `tests/test_worker.py`):
  - succeeded job returns the full contract (every field present, cluster
    resolved by name, `error_message` and both terminal timestamps set)
  - queued job returns `error_message=None`, `started_at=None`,
    `completed_at=None`
  - running job returns `started_at` set and `completed_at=None`
  - failed job returns `error_message` and `completed_at`
  - unknown job_id → 404 with code `installation_not_found`
  - no cookie → 401

## Out of scope

- **18i** progress UI / polling, **18j** history listing endpoint and table,
  **18k** install authorization policy and validation tightening
- Job cancellation, retry, release management (upgrade/rollback/uninstall)
- Any changes to `InstallationJob` model, worker, migrations, or the install
  POST response shape

## Build loop

`workflow.stepReview: "feature"` (one review after all steps);
`workflow.checkpointCommits: "disabled"`. `/complete` creates the final feature
commit.

## Build steps

- [x] 1. **Schema + read endpoint.**
      Add `MarketplaceInstallationStatus` to `app/api/v1/marketplace_schemas.py`
      and `get_installation_status` to `app/api/v1/marketplace.py` (mounted
      router already registered; no new wiring). Return the full contract for a
      seeded succeeded job and HTTP 404 for an unknown job_id with code
      `installation_not_found`.
      **Done when:** `cd backend && python3 -m compileall -q app` is clean and
      `cd backend && .venv/bin/python3 -m pytest tests/test_marketplace.py -k installation_status`
      passes (happy path + 404).
- [x] 2. **State coverage tests.**
      Add tests for the queued, running, and failed jobs (timestamps and
      `error_message` per the In-scope matrix) plus the unauthenticated 401
      case.
      **Done when:**
      `cd backend && .venv/bin/python3 -m pytest tests/test_marketplace.py -k installation_status`
      passes all cases.
- [x] 3. **Verify.**
      Run the declared Verify once:
      `cd backend && .venv/bin/python3 -m pytest` (current 204 + new) and
      `cd k8s-ui && yarn verify`. Self-review against In-scope, then set
      `**Status:** verified`.
      **Done when:** both commands pass and the spec is marked verified.

## Files / areas

- `backend/app/api/v1/marketplace_schemas.py` — add `MarketplaceInstallationStatus`
- `backend/app/api/v1/marketplace.py` — add the GET route
- `backend/tests/test_marketplace.py` — add endpoint tests (reuse `api`,
  `admin_cookie` fixtures; seed jobs via `create_session_factory(api.settings)`)

## Data / contracts

- Read-only against `installation_jobs`; all fields already in the model
  (18g): `package_name`, `cluster_id` → `cluster_connections.name`,
  `namespace`, `release_name`, `status`, `error_message`, `created_at`,
  `started_at`, `completed_at`.
- Response clusters are identified by **name** (matches every existing
  cluster-facing API and the UI's name-based selectors).
- Status values are the exact 18g lifecycle strings; `cancelled` remains
  reserved/unused but is a legal response value per the model.

## Testing

- Backend pytest is the configured runner (`verification.logicTests:
  when-configured`), used above. No browser tests exist for this repo and 18h
  is backend-only, so none are added.

## Notes for the AI

- 404 before 401 handling as in the existing marketplace routes: auth via
  `get_current_actor` dependency does not touch the job.
- Serialize datetimes as pydantic `datetime` (ISO-8601 by default), matching
  other API timestamps in the project.
- Do not call verify again in step 3 if steps 1-2 already ran the full suite as
  part of their Done-when; record observed results once.

## Open questions

None. Remaining product decisions (install authorization per role, kube-system
policy, validation tightening, private/OCI chart repos) belong to 18k.