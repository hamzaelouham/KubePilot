# Findings

> **Generated file.** The findings ledger: review findings raised by `/audit`
> against the work in progress, each with a durable ID, severity (P0-P3), and
> status. `/implement` marks repaired findings `fixed`, a later `/audit` pass
> moves them to `closed`, and `/complete` refuses to merge while any P0 or P1
> finding is `open` or `fixed`, then archives resolved findings with the work
> and resets this file.

### F-01 [P2] fixed - Translate queued test-delivery failures into API errors

**File:** backend/app/api/v1/agents.py:178
**Found:** 2026-09-30 by /audit (scope: current; lens: all)
**Why it matters:** `queue_test_delivery` delegates to `enqueue_delivery`, which can raise `DeliveryServiceError` if the connection is revoked between the pre-check and the queue operation. This route does not translate that error, so the global handler returns a generic 500 instead of the stable safe delivery error contract.
**Suggested fix:** Catch `DeliveryServiceError` in the agent test endpoint and map it to the same status/code response used by the integration delivery routes.
**Resolution:** Fixed in `/implement`: the agent test-delivery endpoint now catches `DeliveryServiceError` and returns its stable status/code/message contract. Regression coverage proves a revoked-connection race returns the safe 409 response.

### F-02 [P2] fixed - Distinguish retrying from initially queued deliveries

**File:** k8s-ui/components/assistant/agents/notifications.tsx:234
**Found:** 2026-09-30 by /audit (scope: current; lens: all)
**Why it matters:** The worker represents a scheduled retry as `status="queued"` with `attempt_count > 0`, but this panel renders only the raw status, so an administrator cannot tell whether a test is waiting for its first attempt or retrying after a provider failure.
**Suggested fix:** Derive and render a retrying state from the attempt count, matching the existing Settings delivery-history presentation.
**Resolution:** Fixed in `/implement`: the agent notification panel derives `retrying` from `status === "queued" && attempt_count > 0`, displays the retrying label, and shows attempt progress. Frontend tests, TypeScript, and the production build pass.

### F-03 [P2] fixed - Avoid one connection query per destination

**File:** backend/app/services/agent_notifications.py:57
**Found:** 2026-09-30 by /audit (scope: current; lens: all)
**Why it matters:** `list_destinations` calls `destination_summary` once per row, and each summary performs a separate `IntegrationConnection` query. Because destinations are independently configurable and have no per-agent bound, listing an agent with many destinations performs an unbounded N+1 query pattern.
**Suggested fix:** Load the supported connection rows once and pass a provider-to-status map into the summaries, or join the connection status into the destination query.
**Resolution:** Fixed in `/implement`: destination listing now joins connection status into the single destination query. Regression coverage counts one connection-table query for a multi-destination listing, and the focused backend suite passes.

### F-09 [P2] open - Repair the failing backend test contract

**File:** backend/tests/test_marketplace.py:744
**Found:** 2026-10-08 by /audit (scope: full; lens: all)
**Why it matters:** The backend suite reports 654 passed and 3 failed. Marketplace tests reject fields now returned by the API, and metadata tests reject newly added tables, so the repository Verify command remains red.
**Suggested fix:** Decide whether the new response fields and tables are intentional, then update the exact contract tests or remove the unintended behavior. Do not weaken assertions merely to pass.
**Resolution:**

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
