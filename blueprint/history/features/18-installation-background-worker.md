# Current Feature

**Status:** verified
**Type:** Feature
**Scope:** 18g — KubePilot Marketplace installation background worker
**Branch:** `feature/installation-background-worker`

## Goal

Run the Marketplace installs that 18f queued. A single in-process FastAPI
background worker picks each `queued` `InstallationJob`, claims it as `running`,
executes `helm repo add` / `helm repo update` / `helm install` through the helm
CLI added to the backend image, and records `succeeded` or `failed` with
`started_at`/`completed_at`/`error_message` and system audit rows. No Celery/RQ;
no separate worker process. On restart, orphaned `running` jobs are requeued so
work is never stranded.

## In scope

1. **Worker settings.** In `backend/app/core/config.py` add to `Settings`:
   `worker_enabled: bool = True` (`KUBEPILOT_WORKER_ENABLED`),
   `worker_poll_seconds: int = 5` (`KUBEPILOT_WORKER_POLL_SECONDS`, positive int
   via the existing `_positive_int`),
   `helm_binary: str = "helm"` (`KUBEPILOT_HELM_BINARY`, non-empty),
   `helm_install_timeout_seconds: int = 600`
   (`KUBEPILOT_HELM_INSTALL_TIMEOUT_SECONDS`, positive int). Add a small boolean
   env parser (`_env_bool`) that accepts `true/1/yes/on` and `false/0/no/off`
   (case-insensitive) and raises `ConfigurationError` otherwise, matching the
   existing config failure style. Tests must opt out of the worker: set
   `KUBEPILOT_WORKER_ENABLED=false` in every fixture/inline TestClient boot point
   that calls `create_app()` (see Files/areas), because the lifespan will start
   the loop when the setting defaults on.
2. **Persist the chart repo URL.** 18f deliberately did not store the
   repository URL; 18g resolves it. Extend `_fetch_package_detail` in
   `backend/app/api/v1/marketplace.py` to also return `chart_repository_url`
   from the upstream detail's `repository.url`, and have `create_installation`
   store it in a new nullable `installation_jobs.chart_repository_url` column.
   New Alembic revision `d1e2f3a4b5c6_add_chart_repository_url.py` chained after
   `c4d5e6f7a8b9` adding the nullable column (no index). The worker fails jobs
   with a NULL URL (legacy/queued rows) with a clear `error_message`; fresh
   jobs always carry it.
3. **Worker module.** New `backend/app/jobs/__init__.py` and
   `backend/app/jobs/worker.py`:
   - `claim_next_job(database) -> InstallationJob | None`: select the oldest
     `queued` job (`ORDER BY created_at, id LIMIT 1`), then atomically claim via
     `UPDATE installation_jobs SET status='running', started_at=now WHERE id=:id
     AND status='queued'`; on `rowcount == 1` set `started_at` on the returned
     row and return it, else return None.
   - `run_pending_installations(database, settings)`: loop `claim_next_job`
     until None; for each claimed job build a temp kubeconfig when
     `cluster.kubeconfig_content` is present (writable `tempfile.NamedTemporaryFile`,
     mode `0600`, cleaned in `finally`, passed via `--kubeconfig <path>`; for the
     in-cluster row run with no `--kubeconfig` so helm auto-discovers
     in-cluster config), then call `_run_helm_install(...)`. On success set
     `status='succeeded'`; on `HelmInstallError` set `status='failed'` and
     `error_message` (trimmed stderr tail, capped ~4 KiB); set `completed_at`
     in both cases; commit. Record an audit row after each terminal transition
     with `actor_id=None` (system), `resource_type="installation_job"`,
     `resource_id=str(job.id)`.
   - `_run_helm_install(settings, job, repository_url, kubeconfig_path) -> str`
     (module-level seam tests patch as `app.jobs.worker._run_helm_install`):
     run with the helm binary (list-args subprocess, **never** `shell=True`,
     no shell metacharacters accepted):
     1. `<helm> repo add <job.chart_repository> <repository_url> --force-update`
     2. `<helm> repo update <job.chart_repository>`
     3. `<helm> install <job.release_name> <job.chart_repository>/<job.chart_name>
        --version <job.chart_version> --namespace <job.namespace> --wait
        --timeout <helm_install_timeout_seconds>s [--kubeconfig <path>]`
     Each command observes `helm_install_timeout_seconds`; any non-zero exit or
     timeout raises `HelmInstallError` carrying trimmed merged output.
     Default helm config home (writable under the appuser HOME) is used; helm
     env vars are passed through untouched.
4. **Lifespan wiring + image.** In `backend/app/main.py` lifespan, before
   yielding: requeue orphaned jobs
   (`UPDATE installation_jobs SET status='queued', started_at=NULL WHERE
   status='running'`; commit; no audit rows), then when `settings.worker_enabled`
   start one `asyncio` task running `_worker_loop(settings)`:
   `while True: run pending installations in a thread (sync SQLAlchemy), sleep
   worker_poll_seconds, swallow+log exceptions so the loop survives`; cancel the
   task on shutdown in `finally`. In `backend/Dockerfile`, install a pinned
   `helm` binary (exact semantic version + sha256, `https://get.helm.sh/helm-*`),
   `chmod +x` into `/usr/local/bin/helm` before `USER appuser`, keeping the
   non-root runtime user. No frontend changes.
5. **Focused tests.** New `backend/tests/test_worker.py`: patch
   `app.jobs.worker._run_helm_install`; seed `InstallationJob` rows directly via
   a session factory against a temp sqlite DB (a dedicated `ClusterConnection`
   row with `kubeconfig_content`); assert claim marks `running` +
   `started_at` and a second call claims nothing; success path flips
   `succeeded` with `completed_at` and an audit row
   (`marketplace.install_succeeded`, actor None) and the fake receives the
   expected repo/release/chart/version/namespace args; failure path (fake raises
   `HelmInstallError`) flips `failed` with `error_message` and the
   `marketplace.install_failed` audit row; NULL `chart_repository_url` fails
   the job without invoking helm; `requeue_running_jobs` turns `running` rows
   back to `queued` with a NULL `started_at`. Extend
   `test_marketplace.py::test_install_happy_path` to assert
   `chart_repository_url` persisted from the upstream detail `repository.url`.

## Out of scope

- Status API (`GET .../installations/{job_id}`) - 18h; cancellation (`cancelled`
  status is reserved by the model, unused by 18g) - later; progress/history UI -
  18i/18j.
- Retries/backoff, per-repo helm config isolation beyond the shared HOME, OCI
  registries, private/authenticated chart repos, and dependency pins for chart
  values - 18k decides trust/security; 18g only runs what 18f queued.
- Release upgrades/rollbacks/uninstalls (an existing release name makes the helm
  install fail and the job is recorded `failed`; no `--atomic`, `--force`,
  `--create-namespace`, or destructive flags).
- Cluster re-discovery, namespace re-validation at run time (the namespace was
  validated live at 18f queue time; helm fails naturally if it vanished).
- Frontend changes of any kind.

## Build loop

Follow `blueprint/config.json`: `stepReview: feature`, `checkpointCommits:
disabled` - one review packet after the small steps below, one feature commit at
the end via `/complete`. Stay on branch
`feature/installation-background-worker` (never master); every step ends green
with an observable `Done when`. Backend steps run `cd backend && python3 -m
compileall -q app` and `.venv/bin/python3 -m pytest`; the combined Verify gate at
the end also runs `cd k8s-ui && yarn verify`. KubePilot worker tests never need
a live cluster or helm binary (seam-patched). Stop on any P0/P1 finding.

## Build steps

- [x] 1. **Settings + test opt-out.** Add the four `Settings` fields, a
  `_env_bool` parser, and `KUBEPILOT_WORKER_ENABLED=false` to every
  `create_app()` boot point in tests (fixtures in `test_marketplace.py`,
  `test_user_management.py`, `test_end_to_end_rbac.py`,
  `test_cluster_management.py`, `test_cluster_routing.py`,
  `test_password_lifecycle.py`, `test_rbac_permissions.py`, and the inline
  apps in `test_kubernetes.py`). `Done when`: `python3 -m compileall -q app`
  clean and `.venv/bin/python3 -m pytest` passes untouched (196 tests), so the
  opt-out is proven (worker would otherwise start under TestClient).
- [x] 2. **Repo URL persistence + migration.** Add
  `d1e2f3a4b5c6_add_chart_repository_url.py` chaining after `c4d5e6f7a8b9`
  (nullable String column, no index); extend `_fetch_package_detail` to return
  `chart_repository_url` from `repository.url` and store it in
  `create_installation`; extend `test_install_happy_path` and the
  `UPSTREAM_INSTALL_DETAIL` fake. `Done when`:
  `PYTHONPATH=. alembic upgrade head --sql` renders
  `ADD COLUMN chart_repository_url` and
  `.venv/bin/python3 -m pytest tests/test_marketplace.py` passes.
- [x] 3. **Worker core + unit tests.** Add `app/jobs/worker.py` (claim,
  requeue hook `requeue_running_jobs(database)`, `run_pending_installations`,
  `_run_helm_install` seam, `HelmInstallError`, temp-kubeconfig handling) and
  the two new audit events (`MARKETPLACE_INSTALL_SUCCEEDED =
  "marketplace.install_succeeded"`, `MARKETPLACE_INSTALL_FAILED =
  "marketplace.install_failed"`). Add `tests/test_worker.py` covering every
  case in In-scope item 5. `Done when`: `python3 -m compileall -q app` clean
  and `.venv/bin/python3 -m pytest tests/test_worker.py` passes.
- [x] 4. **Lifespan wiring + Dockerfile.** Start/stop the worker loop and run
  the startup requeue in `app.main.lifespan`; add the pinned helm install to
  `backend/Dockerfile`. `Done when`: `.venv/bin/python3 -m pytest` passes
  (196 + new), the lifespan wiring is exercised by a worker-on app boot check,
  and the Dockerfile change is reviewed for the pinned version/checksum
  (build/live-test via the documented GitHub Actions docker workflow, which
  needs egress - see Testing).
- [x] 5. **Verify.** Run the declared Verify once: `cd backend &&
  .venv/bin/python3 -m pytest` (196 + new) and `cd k8s-ui && yarn verify`.
  `Done when`: both commands pass.

## Files / areas

- `backend/app/core/config.py` - four new settings + `_env_bool` parser.
- `backend/app/jobs/__init__.py`, `backend/app/jobs/worker.py` - new worker
  module (seam-patched entry point `app.jobs.worker._run_helm_install`).
- `backend/alembic/versions/d1e2f3a4b5c6_add_chart_repository_url.py` - new.
- `backend/app/api/v1/marketplace.py` - `_fetch_package_detail` returns
  `chart_repository_url`; `create_installation` stores it. `marketplace_schemas.py`
  unchanged (response schema untouched).
- `backend/app/core/audit.py` - two new `AuditEvent` constants.
- `backend/app/main.py` - lifespan: startup requeue + worker task start/stop.
- `backend/Dockerfile` - pinned `helm` binary install before `USER appuser`.
- `backend/tests/test_worker.py` - new; `backend/tests/test_marketplace.py` -
  happy-path extends to assert `chart_repository_url`; the eight other test
  boot points listed in step 1 set `KUBEPILOT_WORKER_ENABLED=false`.
- Reused unchanged: `record_audit` (supports `actor_id=None` system rows),
  `ClusterConnection` (`kubeconfig_content`), `create_session_factory`,
  `InstallationJob` (18f table).

## Data / contracts

- `installation_jobs` gains nullable `chart_repository_url` (String). Existing
  queued rows without it fail on processing with the message noting the missing
  URL; fresh 18g-era jobs always carry upstream `repository.url`.
- Job lifecycle in 18g: `queued` -> `running` (claim: `started_at` set) ->
  `succeeded` (`completed_at` set, no result column) or `failed`
  (`error_message` capped ~4 KiB, `completed_at` set). `cancelled` is a
  reserved value, unused until a later cancellation feature.
- Helm execution contract: three list-args subprocess commands run in order
  (`repo add --force-update`, `repo update`, `install ... --wait --timeout`),
  never through a shell; non-zero exit or per-command timeout -> job `failed`
  with merged output (trimmed) as the message. No `--atomic`, `--force`,
  `--create-namespace`, or upgrade/uninstall verbs in 18g. Release name,
  chart name, chart version, namespace are the stored 18f values; the repo
  alias is `chart_repository` (the Artifact Hub repo name).
- Kubeconfig: per-job temp file (0600) when `cluster.kubeconfig_content` is
  present; otherwise helm runs with no `--kubeconfig` (in-cluster discovery).
  The temp file never persists and is removed in `finally`.
- Audits: system rows with `actor_id=None`, `resource_type="installation_job"`,
  `resource_id=str(job.id)`, `result="success"` or `"failure"`, action
  `marketplace.install_succeeded` / `marketplace.install_failed`. The startup
  requeue writes no audit rows.
- Worker single-flight: one job at a time, oldest-first; `worker_poll_seconds`
  gap between cycles; an exception raised anywhere in a cycle is logged by the
  loop and swallowed so the worker keeps running.
- Restart behavior: `running` at boot is requeued (`status='queued'`,
  `started_at=NULL`) before the loop starts; `queued` jobs wait for the next
  cycle.

## Testing

- Backend: `.venv/bin/python3 -m pytest` - existing 196 plus the new worker
  tests (seam-patched `_run_helm_install`, temp sqlite, no live helm/k8s) and
  the extended marketplace happy-path. `python3 -m compileall -q app`;
  migration renders via `PYTHONPATH=. alembic upgrade head --sql`. The eight
  existing test boot points opt out of the worker loop via
  `KUBEPILOT_WORKER_ENABLED=false`.
- Image: the pinned helm layer is verified by building/pushing the backend
  image through the documented GitHub Actions docker workflow (reliable
  egress; see AGENTS.md) and then `docker run --rm <image> helm version`, or a
  comparable local build when egress allows. This is the only runtime check
  needing an OCI environment; the standard Verify gate is pytest + `yarn
  verify` and does not require it.
- Manual try path: with a live cluster + backend running helm, queue an
  install from `/marketplace`, then poll `installation_jobs` - the row goes
  `running` (`started_at`) and ends `succeeded` with a real release, or
  `failed` with `error_message` when the release name already exists or the
  namespace is gone; a backend restart requeues any `running` row.
- Frontend: untouched; `cd k8s-ui && yarn verify` must still pass (Verify gate).

## Notes for the AI

- Keep all worker logic behind the `app.jobs.worker` module namespace so tests
  monkeypatch `app.jobs.worker._run_helm_install` exactly like
  `app.api.v1.marketplace._fetch_artifact_hub_search` / `create_cluster_client`.
- The 18f table + fixture ground truths confirmed this session:
  `InstallationJob` columns as pinned, `record_audit(... actor_id=None)` is
  supported, `Settings.from_env()` reads only env vars, tests build the app via
  `create_app()` per-fixture. Do not rename or move those seams; 196 tests
  depend on them.
- Helm is currently absent from the runtime image (python:3.12-slim, non-root
  `appuser`, HOME `/app`); the Dockerfile step must place helm in `/usr/local/
  bin` before `USER appuser` and pin exact version + sha256. Use
  `https://get.helm.sh/` artifacts (amd64/arm64) with checksum verification.
- The worker runs sync SQLAlchemy; offload each cycle with
  `asyncio.to_thread` so the event loop stays responsive; the polling loop must
  not crash the app on a bad job (wrap per-cycle exceptions and log them).
- In the review handoff, call out the helm-packaging decision (pinned helm CLI
  in the backend image per user choice, no Celery/RQ, no sidecar), the restart
  semantics (requeue `running`), and that `chart_repository_url` now lives on
  the job (18f did not store it; 18g's migration adds it).

## Open questions

- **Chart repo auth / OCI:** only public classic Artifact Hub Helm repos are
  supported (repo add uses the stored public URL); private repos,
  authenticated registries, and OCI charts are deferred - 18k governs trust and
  executable-input policy for chart sources.
- **Failed-job retry policy:** 18g records `failed` with no automatic retry;
  whether a user can force-requeue a failed or cancelled job is a later 18h/18j
  decision, not a 18g contract.