# Findings

> **Generated file.** The findings ledger: review findings raised by `/audit`
> against the work in progress, each with a durable ID, severity (P0-P3), and
> status. `/implement` marks repaired findings `fixed`, a later `/audit` pass
> moves them to `closed`, and `/complete` refuses to merge while any P0 or P1
> finding is `open` or `fixed`, then archives resolved findings with the work
> and resets this file.

### F-12 [P2] open - Bind OAuth callbacks to the initiating browser session

**File:** backend/app/api/v1/integrations.py:133
**Found:** 2026-10-08 by /audit (scope: full; lens: all)
**Why it matters:** OAuth state is stored with an actor, but the callback does not verify the current browser session. A valid authorization flow can therefore complete in the wrong browser context and link an unintended provider account.
**Suggested fix:** Bind state to a signed HttpOnly session cookie or session hash and require the same authenticated user on callback.
**Resolution:**

### F-13 [P2] open - Reuse one SQLAlchemy engine and pool

**File:** backend/app/db/session.py:10
**Found:** 2026-10-08 by /audit (scope: full; lens: all)
**Why it matters:** The request dependency constructs a new engine and pool for each database session. Dashboard polling and concurrent users cause avoidable connection churn, latency, and possible connection exhaustion.
**Suggested fix:** Create one engine and session factory during application startup and reuse it for request and worker lifetimes.
**Resolution:**

### F-15 [P2] open - Paginate marketplace history in the database

**File:** backend/app/api/v1/marketplace.py:680
**Found:** 2026-10-08 by /audit (scope: full; lens: all)
**Why it matters:** History queries fetch large fixed batches, sort them in Python, and slice afterward. As job history grows, requests consume unnecessary memory and can report inaccurate pagination.
**Suggested fix:** Use a unified database-side paginated query or bounded per-source fetches, with appropriate indexes and retention.
**Resolution:**

### F-16 [P2] open - Rate-limit login and cap credential input sizes

**File:** backend/app/api/v1/routes.py:105
**Found:** 2026-10-08 by /audit (scope: full; lens: all)
**Why it matters:** Public login has no throttling or input length limits while every attempt performs expensive password hashing. Password spraying, oversized inputs, and audit spam can consume CPU and database capacity.
**Suggested fix:** Add IP/account throttling or backoff, cap email and password lengths before hashing, and limit failed-attempt persistence.
**Resolution:**

### F-19 [P2] unverified - Clarify relative chart URLs after index redirects

**File:** backend/app/kubernetes/chart_source.py:83
**Found:** 2026-10-09 by /audit (scope: current; lens: quality)
**Why it matters:** fetch_public follows redirects but returns only bytes; chart_archive always resolves relative archive entries against the originally requested index URL. A mocked public-to-public index redirect reproduced an archive request on the original host/path rather than the final index host/path. Whether that is a defect depends on the intended repository-relative URL convention and compatibility with the previously used Helm behavior; no live repository or Helm integration evidence establishes that contract yet.
**Suggested fix:** Establish and test the supported relative-URL convention with a redirected public index. Retain the effective index URL only if that is the required base, while preserving validation of every archive and redirect target.
**Resolution:** Unverified lead, not a confirmed defect or completion blocker.

## Audit — notification delivery P2 re-review, 2026-10-09

- Scope: agent notification destinations, test-delivery API, notification panel
  and connected delivery contracts; all four lenses (quality, security,
  performance, tests). This is a path-scoped review based on the preceding user
  request, not a full-project audit. No active spec; clean master at review start.
  Reused valid project config and loaded overview/standards/interaction/review
  context. No independent review requested; no committed-range claim applies.
- Reviewed complete agent_notifications service, relevant agent routes/permission
  dependencies, notification UI/schema, enqueue/error boundary, retry transition,
  unique connection-provider constraint and connected agent/integration tests.
  Used Graphify navigation. Checked operational permission/scope boundaries,
  encrypted destination storage, safe metadata/errors, retry classification,
  idempotency/transaction behavior and query scaling, not only the prior findings.
- Closed F-01, F-02 and F-03 explicitly. No new confirmed finding in this scope.
  F-09/F-12/F-13/F-15/F-16 remain open P2; F-19 remains unverified P2. None accepted
  or closed implicitly; no P0/P1 blocker present.
- Commands: backend .venv/bin/python3 -m pytest tests/test_agents.py
  tests/test_integration_delivery.py -q --tb=short passed 34 tests in 37.22s;
  frontend yarn test:assistant passed 36 tests. git diff --check passed.
  No skipped/focused/xfail/placeholder tests found in selected test files.
  Reused the recent successful build and TypeScript evidence; no source changed.
- Excluded unrelated app areas, generated/build/graph output, dependencies,
  caches, real Secrets/private artifacts and live provider accounts. No new
  browser/component-render test, real provider delivery, load benchmark,
  full backend regression, online security scan or remote CI inspection.
  Frontend tests cover bridge/client contracts, not the retry label render branch.
- Standards: explicit operational authorization, narrow error handling, no raw
  destination/credential disclosure, persisted-data scope, shared safe summaries
  and meaningful SQL/error contract regression assertions. Only the findings
  ledger and generated dashboard activity changed. Next: /fix F-09, then
  implement its exact test/API contract repair; remaining findings retain IDs.

## Audit re-review — 2026-10-09

- Scope: current; all four lenses (quality, security, performance, tests). Base:
  local master; merge base and HEAD are both
  0d0565f546f039c7c0a7f16258d1e392ed0bcb69. There is no committed feature delta;
  the reviewed work consists of tracked local changes and untracked repair code/tests.
- Reviewed deployment/workflow/config changes; RBAC manifests/tests; kubeconfig
  model/encryption/migration and Kubernetes consumers; Helm source fetching,
  resolution and worker calls; password/login code; Next.js proxy/origin guard;
  worker ownership/recovery and nearby delivery/agent execution; new/changed tests
  and operational documentation. Excluded dependencies, generated graph/build
  output, caches, vendored code, and unrelated application areas. Used graph
  queries for caller navigation without changing graph state.
- Checked existing authorization, secret-at-rest, explicit operation, safe-error,
  test, deployment and version-tag contracts. No skipped/focused/placeholder tests
  found in the new repair test files. PostgreSQL lock behavior remains mocked;
  most worker/Helm tests isolate subprocess/network boundaries. The Secret test's
  incomplete positive fixture missed F-18.
- Closed F-05 after inspecting every production kubeconfig consumer, ciphertext
  property and migration. Raw-storage/key-error tests pass; an actual Alembic
  upgrade from the preceding revision encrypted a legacy row on temporary SQLite
  and decrypted back to the original synthetic value. Initial diagnostic seeding
  hit the old SQLite now() default; supplying created_at allowed the migration
  test to complete. Live PostgreSQL migration and backup handling remain pending.
- Closed F-06 after reviewing event triggers, login/push guards, environment-fed
  shell inputs, tag validation and stable-manual-only latest outputs, and rerunning
  workflow tests. This closes the present workflow's automatic PR publishing path;
  it is not proof of remote branch/environment protection or resistance to a
  contributor authorized to alter workflow definitions. No GitHub run performed.
- Closed F-07's original default-credential exposure: no deployable default Secret
  remains; non-local bootstrap rejects defaults; local Compose binds to loopback;
  deployment validation rejects unsafe credentials and preserves encryption keys.
  The distinct incomplete-Secret defect introduced by preflight is tracked as F-18
  and blocks completion, rather than being hidden by closing the original issue.
- Closed F-08's original internal-target SSRF path after tracing both resolution
  and queued install/upgrade through the same public-DNS-pinned downloader and
  local Helm archive. Address/redirect/queued-input tests pass. F-19 is a separate
  unverified compatibility lead; no live chart-source trust or Helm proof is claimed.
- Closed F-10 after inspecting random salts, fixed-cost parsing, constant-time
  verification and successful-login legacy rehash/commit; hash tests pass and the
  prior lifecycle evidence covers password changes and legacy upgrade.
- Closed F-11 after inspecting API matcher coverage and the shared mutation origin
  gate before routing; frontend regression files and TypeScript pass. No browser
  or reverse-proxy integration run performed.
- Closed F-14 after tracing exclusive ownership across recovery/execution, removing
  API-startup requeue, terminal unknown-outcome recovery and cancellation lifetime;
  contention/recovery tests pass. Live PostgreSQL and process-kill/partition tests
  remain unavailable; no exactly-once external-effects claim is made.
- Signals this pass: 39 focused backend tests passed; yarn test:assistant passed
  all three test files; yarn tsc --noEmit and bash -n deploy.sh passed. Direct
  incomplete-Secret reproduction confirmed F-18; redirected-index reproduction
  supports only the F-19 lead. git diff --check reports the preserved pre-existing
  blank EOF line in backend/requirements.txt, not a new repair defect.
- Reused prior expanded Verify evidence: 76 backend and 36 frontend tests passed,
  but the production build failed because Turbopack could not bind a runner port.
  Did not repeat that known infrastructure failure, run a full backend suite,
  start servers, inspect a browser, scan online dependencies, or change external
  services. The prior F-09 full-suite failure remains open. No independent review
  requested or receipt created. F-01–F-03 and unrelated open P2s were not re-reviewed.
- Next: repair F-18 through /implement, establish evidence for F-19 if needed,
  rerun Verify where production builds can run, then /audit before /complete.

## Latest audit — local Secret and F-18 closure

- 2026-10-09; scope current, all four lenses. Local master is the comparison base;
  merge base and HEAD remain 0d0565f546f039c7c0a7f16258d1e392ed0bcb69. No committed
  feature delta exists. Reviewed staged removal, tracked edits, untracked repair
  sources/tests and their affected callers; reused project overview, standards,
  interaction guidelines and prior nearby-code context loaded this session.
- Reviewed configuration/deployment/workflow changes, RBAC, encrypted kubeconfig
  model/migration/consumers, Helm source boundaries and worker ownership/recovery,
  password/login and frontend origin protection, the new Secret validator and
  bootstrap test changes. Used the existing graph read-only for caller navigation.
  Excluded generated graph/build output, dependencies, caches, vendored code and
  unrelated source. Did not read or print the retained local Secret's contents.
- Checked explicit operational authority, authorization, secret-at-rest and
  no-committed-Secret contracts, safe errors, manifest consistency and regression
  coverage. No new confirmed findings. Closed F-18; re-examined the changed F-07
  surface and reconfirmed its closure. Other closed P1 repairs remain closed.
  F-19 stays unverified; existing unrelated P2 entries were not closed implicitly.
- Commands: backend .venv/bin/python3 -m pytest on test_bootstrap_security.py,
  test_rbac.py, test_chart_source.py, test_docker_workflow.py,
  test_kubeconfig_encryption.py, test_password_hashes.py and
  test_worker_ownership.py: 66 passed, no skips. yarn test:assistant: all three
  frontend test files passed. yarn tsc --noEmit and bash -n deploy.sh passed.
  Scoped git diff --check passed excluding the preserved requirements.txt EOF
  warning. Git tracking/ignore/file-presence checks confirm a retained ignored,
  untracked local Secret. No skipped/only/placeholder tests found in new repair
  files; PostgreSQL locking and external Helm/network paths remain mocked.
- Build evidence: the user supplied successful `cd k8s-ui && yarn verify` output
  (Next.js production compilation, TypeScript and prerendering completed). This
  is user-run evidence, not an agent-run pass or a full Verify result. The prior
  agent Verify passed 103 selected backend tests and frontend tests but its build
  failed on the runner port-binding restriction. Did not repeat the known runner
  failure or claim the exact full gate passed. Audit does not change the active
  spec, which still says implementing.
- Remaining signals: no full backend regression rerun (F-09 remains open), live
  PostgreSQL/migration/lock tests, Minikube authorization/Helm smoke checks, browser
  or reverse-proxy flow proof, remote registry/protection check, or online security
  scan. No independent review requested or receipt created. No new P0/P1 blocker
  remains open/fixed in the ledger; existing P2 work and F-19 are still follow-ups.
- Next: obtain successful exact `./scripts/verify-feature.sh` evidence locally,
  record verified spec state through /implement, then /complete. Local untracking
  remains staged until the approved work commit; no commit, push, deployment or
  external setting change occurred during this audit.


## Audit — guarded local Secret deployment

- 2026-10-09; scope current; quality, security, performance and tests. Branch:
  fix/deploy-the-local-secret-safely. Locally recorded remote default ref was
  absent, so local master is the comparison base. Merge base and HEAD are
  cc1d7b34f63d46803347350efa7b8f08323963a9; the committed delta is empty.
  Reviewed every pending source/config change and its affected callers; no
  untracked source files exist.
- Reviewed deploy.sh, scripts/validate-deployment-secret.py, bootstrap tests,
  backend/README.md, the pre-existing PostgreSQL recovery YAML, and nearby Settings,
  SQLAlchemy session creation, dependency declarations and workload Secret fields.
  Reused loaded project overview, standards, interaction guidelines and active
  spec. Used graph navigation for the helper/caller/test relationships. Excluded
  generated graph/build output, dependencies, caches, vendored code, unrelated
  application features, private recovery artifacts and the actual local Secret.
- Checked complete Secret and identity validation; data/stringData normalization;
  key/database preservation; optimistic resourceVersion replacement; refusal to
  guess credentials for retained PostgreSQL storage; stdin-only Secret payloads;
  generic API/YAML errors; deployment ordering; test isolation and documentation.
  F-20 is confirmed. No additional confirmed findings from the other reviewed
  paths. The recovery-specific PVC edit remains separate from this fix and must
  be explicitly addressed before a completion commit mixes pending changes.
- Signals: backend .venv/bin/python3 -m pytest tests/test_bootstrap_security.py
  -q --tb=short: 65 passed. bash -n deploy.sh and git diff --check passed. No
  skipped/focused/placeholder tests found in the changed tests. Reused the current
  implementation's successful exact Verify result: 65 backend tests, 36 frontend
  tests and production build. Did not repeat the unchanged build.
- Reproductions use only synthetic in-memory Secrets and patched subprocesses.
  No cluster commands were executed. The first unsupported-driver fixture used
  an invalid URI scheme spelling and was correctly rejected; the corrected
  syntactically valid scheme reached a mocked Secret create and then failed
  SQLAlchemy engine construction. The supported-driver invalid-port reproduction
  independently confirmed missing structural URL validation. No network calls
  were needed for either engine failure.
- Existing P2 entries remain unchanged; none were closed implicitly. Added F-20
  as open P1, which blocks /complete. No independent review was requested or
  receipt created. Audit does not rewrite the active spec's verified status.
- Gaps: no live deployment of the new local Secret path, API-server concurrency
  integration, new browser flow, full backend regression run, remote CI check,
  online dependency/security scan or performance benchmark. Earlier browser and
  database recovery evidence concerns the running app, not this new script path.
- Next: /implement to repair F-20 and add its regression cases, rerun Verify,
  then /audit before /complete. No source/configuration changes, commit, merge,
  push, deployment or credential changes performed during this audit.


## Audit — local Secret deployment after F-20 repair

- 2026-10-09; scope current; all four lenses: quality, security, performance,
  tests. Local master is the base because no remote default symbolic ref exists.
  Merge base and HEAD: cc1d7b34f63d46803347350efa7b8f08323963a9; committed
  master...HEAD delta is empty. Reviewed all staged/unstaged changes (none staged)
  and checked for untracked source files (none).
- Reviewed deploy.sh, the complete Secret validator, bootstrap tests, README and
  recovery-specific PostgreSQL manifest change; followed Settings, backend session
  creation, requirements and backend/frontend/PostgreSQL Secret consumers. Used
  Graphify navigation and inspected only the installed SQLAlchemy parser/dialect
  needed to confirm runtime semantics. Standards checked: narrow operational
  boundaries, fail-closed validation, credential-free errors, data preservation,
  minimal shared logic, meaningful tests and explicit deployment authority.
- Confirmed identity/data normalization, encryption-key/database preservation,
  optimistic resourceVersion replacement, missing-Secret/storage refusal,
  stdin-only payloads, generic API/YAML failures and workload ordering. Closed
  F-20 explicitly; added F-21 as open P1. No other new confirmed findings.
  Existing P2 entries remain unchanged. No independent receipt requested.
- Commands: focused bootstrap pytest passed 104 tests in 8.34s; bash -n deploy.sh
  and git diff --check passed. No skipped, focused or placeholder tests found
  (the placeholder-secrets test name describes a real rejection test).
  Reused unchanged frontend evidence from the immediately preceding Verify:
  36 frontend tests and production build passed alongside 104 backend tests.
- Synthetic reproductions confirmed both F-21 cases reach mocked Secret writes
  and differ from effective runtime database arguments; query overrides also
  differ from the effective password. No connection to a database or cluster.
- Excluded unrelated app areas, generated graph/build output, dependencies except
  the targeted parser/dialect inspection, caches, vendored/minified assets, actual
  ignored local Secret and private database recovery artifacts. No online scanner,
  full backend regression, performance benchmark, remote CI, browser review or live
  API-server deployment/concurrency integration run. Prior browser/recovery proof
  is not proof of this new script path. Per-command Kubernetes timeouts are bounded;
  no performance claim relies on a benchmark.
- Next repair order: F-21 through /implement, then Verify and /audit. F-21 blocks
  /complete. The unrelated recovery PVC edit still needs a separate inclusion
  decision before any completion commit. Audit changed only this ledger and
  generated activity state, not source, spec, credentials or running workloads.

## Audit — local Secret deployment after F-21 repair

- 2026-10-09; scope current; quality, security, performance and tests. Branch:
  fix/deploy-the-local-secret-safely. No locally recorded remote default symbolic
  ref; local master used as base. Merge base and HEAD both
  cc1d7b34f63d46803347350efa7b8f08323963a9; master...HEAD committed delta empty.
  All seven dirty tracked files reviewed, with no staged or untracked source.
- Reviewed complete Secret validator, deployment script, bootstrap tests, README,
  active spec and ledger plus the pre-existing PostgreSQL recovery manifest diff.
  Reused loaded overview, coding standards and interaction guidelines. Followed
  Settings, session/engine creation, installed driver requirements and workload
  Secret contracts; Graphify navigation and targeted installed SQLAlchemy
  parser/dialect inspection confirmed the effective runtime field semantics.
- Checked narrow shared validation, literal database-name agreement, encoded
  credentials, supported driver/host/ports, forbidden query/fragment/ambiguous
  forms, fail-closed ordering, identity/data normalization, immutable database/key
  preservation, resourceVersion conflicts, retained-storage refusal, generic
  errors and stdin-only values. No new confirmed findings across the four lenses.
  No new hot-path/unbounded-operation issue; Kubernetes helper calls have bounded
  timeouts. No benchmark or live concurrency claim made.
- F-21 explicitly closed; F-20 stays closed. Other P2 statuses unchanged. No
  open/fixed P0/P1 entries remain. No independent review requested or receipt
  created; this is a normal audit, not an independent-review checkpoint.
- Commands: backend .venv/bin/python3 -m pytest tests/test_bootstrap_security.py
  -q --tb=short passed 156 tests in 14.49s; bash -n deploy.sh and git diff --check
  passed. No skipped, focused, xfail or placeholder tests found. SQLAlchemy
  connection-argument assertions construct engines but never connect; shell tests
  use synthetic Secrets and fake Minikube, and inspect output/arguments for leaks.
  Reused the immediately preceding unchanged exact Verify pass: 156 backend tests,
  36 frontend tests and production build; no redundant frontend build run.
- Excluded unrelated application areas, generated graph/build output, dependency
  trees except targeted parser/dialect inspection, caches, vendored/minified
  assets, real ignored local Secret and private recovery artifacts. No live
  deployment/browser/API-server integration, full backend regression, remote CI,
  online vulnerability scan or performance benchmark run. Prior working-browser
  evidence does not prove this new deployment path. Query-based TLS options remain
  intentionally unsupported, as documented.
- Next: /complete safety pass, with a separate decision on the unrelated recovery
  PVC edit before any commit mixes it into this fix. No new repair order required.
  Only this ledger and generated activity state changed during audit; source,
  spec, credentials and workloads were not modified.

## Audit — backend test contract re-review, 2026-10-13

- Scope: current; quality, security, performance and tests. Branch:
  `fix/repair-backend-test-contracts`. Base: local `master`, merge base and HEAD
  `6200b3a8deac4124463695117db2cd2e3c69c532`; committed range is empty. Reviewed
  all four dirty tracked files; no staged or untracked source files.
- Reviewed the test changes, marketplace response schemas/routes and history UI,
  model registration, all eight asserted model constraints and their migrations,
  plus relevant permission contracts and tests. The marketplace history spec
  explicitly keeps read endpoints auth-only. No new confirmed defect in scope.
- Closed F-09. F-12, F-13, F-15 and F-16 remain open P2; F-19 remains unverified
  P2. No P0/P1 finding is open or fixed. No independent review was requested.
- Commands: `cd backend && .venv/bin/python3 -m pytest tests/test_models.py -q
  --tb=short` passed 10 tests; `git diff --check` passed. The combined marketplace
  test run and narrowed response-contract run were interrupted after prolonged
  silence. Reused the active spec's 2026-10-09 evidence for 853 passing backend
  tests and the exact Verify gate; neither was rerun here.
- Standards checked: exact API contracts, explicit expected inventories,
  sensitive-value exclusion, ownership constraints and migration consistency.
  Graphify query was used for navigation. No live app/browser, remote CI, full
  backend regression, full Verify or performance benchmark was run. Excluded
  unrelated app areas, generated output, dependencies and build artifacts.
- Next: `/complete` safety pass. Only the findings ledger and generated activity
  state changed during this audit; application source and tests were untouched.
