# Current Feature

> **Generated file.** Holds the one feature, fix, or rollback being built right now. Run
> `/feature <number-or-name>` to spec a build-plan feature, or `/fix "<bug>"` for
> an ad-hoc fix. Use `/rollback <completed-feature>` to plan a safe reversal.
> Build one thing at a time; `/complete` archives it under `blueprint/history/`
> and resets this file.

## Replace backend cluster-admin with explicit permissions

**Type:** Fix
**Status:** verified
**Branch:** fix/replace-backend-cluster-admin-with-explicit-permissions
**Fixes:** F-04, F-06, F-05, F-07, F-08, F-10, F-11, F-14, F-18

### The problem

The `kubepilot-api-admin` binding grants unrestricted cluster authority.
`backend/tests/test_rbac.py` checks only the discovery role and misses it.
The historical fix added cluster-admin for privileged charts such as cert-manager.
Simply removing it would also break supported resource and Helm operations.

### The fix

Preserve the discovery role/binding and replace the admin binding with an
explicit operations role/binding. Grant get/list/watch/create/update/patch/delete
only on these resources:

- Core: pods, services, namespaces, configmaps, secrets, serviceaccounts,
  persistentvolumeclaims, replicationcontrollers.
- Apps: deployments, replicasets, daemonsets, statefulsets.
- Batch: jobs, cronjobs.
- Networking: ingresses, networkpolicies.
- Autoscaling: horizontalpodautoscalers.
- Policy: poddisruptionbudgets.

Reject wildcards, RBAC writes, bind/escalate/impersonate, token creation,
pod exec/attach, node writes, CRD writes, and webhook configuration writes.
Secret access supports Helm release storage and charts; workload creation still
allows powerful actions, so document the residual authority rather than claiming
this identity provides namespace isolation or prevents every escalation path.

Charts requiring privileges outside this baseline must fail through existing
error handling. Document separate administrator-provisioned chart-specific
permissions; never silently restore cluster-admin. Managed-cluster permissions
and application authorization/approval boundaries remain unchanged; the expanded
F-05 step encrypts kubeconfig storage without changing their credential contents.

Removing a binding from YAML does not delete it from existing clusters. Document
an upgrade that applies the replacement permissions before explicitly deleting
only `kubepilot-api-admin`. Live changes require separate rollout authorization.
Preserve unrelated requirements and findings-ledger edits.

### Build steps

- [x] Replace the admin binding in `backend/deploy/kubernetes/service-account.yaml`
  with the explicit operations role/binding. Extend `backend/tests/test_rbac.py`
  to examine every role and binding, assert exact resource/verb allowlists,
  preserve discovery, and reject unrestricted or escalation permissions.
  Update deployment documentation with supported operations, privileged-chart
  limitations, residual authority, the retained-binding upgrade procedure, and
  positive/negative authorization checks.
  **Done when:** focused RBAC tests pass; every supplied binding targets an
  explicitly tested local role; no cluster-admin binding remains; allowed and
  forbidden permissions are tested; upgrade documentation explains deletion of
  the old live binding.

### Remaining P1 repair steps (authorized 2026-10-09)

- [x] F-06: build PR images without registry credentials or pushes; gate publishing
  to trusted push/manual events, validate tags using shell environment inputs,
  reserve latest for approved stable releases, and test workflow guard contracts.
  Done when PR builds cannot log in or publish and preview tags follow docs/versions.md.
- [x] F-05: encrypt persisted kubeconfigs with the existing Fernet service, migrate
  legacy plaintext safely, and decrypt only at Kubernetes/Helm use boundaries.
  Done when upload/update/read/error and migration regression checks pass without
  exposing secrets, and missing keys fail closed without losing existing data.
- [x] F-07: remove deployable default secrets and enforce bootstrap validation,
  preserving an explicit local development path. Done when non-local startup and
  deployment reject default credentials and tests cover valid and invalid inputs.
- [x] F-08: validate Helm repository targets at API and execution boundaries,
  including queued legacy inputs. Reuse existing policy; protect against internal
  targets and redirects. Done when focused tests demonstrate denied targets cannot
  cause network requests and supported chart sources remain usable.
- [x] F-10: use random per-password salts and constant-time comparisons; verify
  legacy hashes and upgrade on login. Done when legacy login, salted hashes,
  malformed input and password-change regression tests pass.
- [x] F-11: enforce shared same-origin protection for all frontend mutation
  proxies. Done when representative foreign-origin requests fail before upstream
  access and existing authenticated same-origin flows pass.
- [x] F-14: prevent startup recovery from requeuing work owned by another live
  worker. Use a minimal exclusive worker ownership mechanism or expiring leases;
  preserve crash recovery and shutdown correctness. Done when concurrent-worker
  and recovery tests pass without automatically replaying uncertain side effects.

Implementation boundaries: migrate kubeconfigs online with the preserved Fernet
key; older backups may still contain plaintext. Kubernetes secrets must be
provisioned externally. Helm sources must be public HTTP(S), with dependencies
packaged in the archive; private/OCI/query-bearing URLs are not supported.
Worker recovery marks interrupted jobs failed or outcome_unknown for inspection,
not automatic replay. PostgreSQL ownership retains a dedicated lock connection;
database/network failures do not provide exactly-once external side effects.

### F-18 follow-up (authorized 2026-10-09)

- [x] Require every Secret key consumed by the supplied deployments, rejecting
  absent, empty and whitespace-only values. Check the URL's decoded username,
  password and database against the bundled PostgreSQL Secret fields. Add a
  complete positive fixture and tests for every missing/blank key, mismatches and
  URL-encoded matching fields; retain generic errors without secret values.
  Done when focused validation checks pass and deployment invokes the validator
  before applying database/application workloads. Preserve restored secret.yaml
  and unrelated .gitignore edits; report any conflict with earlier verification.

- [x] Keep secret.yaml as a local-only Minikube file (explicitly authorized):
  correct its ignore rule and remove only its Git index entry, without reading,
  deleting or changing the local Secret. Replace the file-absence assertion with
  checks that the path is ignored and not tracked. Done when bootstrap tests
  pass and read-only Git checks confirm the local file remains ignored/untracked.

### Final verification

- Focused: `cd backend && .venv/bin/python3 -m pytest tests/test_rbac.py`.
- Final gate: `./scripts/verify-feature.sh`.
- Inspect other deployment manifests for bindings granting unrestricted access
  to the same service account.
- After a separately authorized rollout, check
  `minikube kubectl -- auth can-i --as=system:serviceaccount:kubepilot:kubepilot-api`
  for allowed discovery, deployment mutation, and Helm secret operations; denied
  clusterrolebinding creation, CRD creation, node deletion, and pod exec.
  Confirm the old admin binding is absent. Test an ordinary chart and safe
  rejection of a privileged chart. Record live verification as pending until run.
- `/audit` closed all nine P1 findings in this fix, including F-18, and
  re-reviewed the updated F-07 local Secret surface. The user-authorized local
  Secret remains ignored and untracked, with regression coverage. No independent
  review was requested. The successful full local Verify evidence below supersedes
  the earlier environment-restricted attempts.

### Verification evidence

- 2026-10-09: focused RBAC tests passed (2 tests).
- `./scripts/verify-feature.sh` passed its backend tests and frontend tests.
  First build attempt failed fetching Google Fonts. A network-enabled retry
  passed all 35 frontend tests but failed in Turbopack while binding a port
  (`Operation not permitted`). Final gate remains blocked; status is not verified.
- Deployment manifest search found no additional backend admin binding.
- Graphify AST update completed. Live rollout, authorization checks, and Helm
  smoke tests remain pending. Regular audit/check/independent-review/try gates
  are manual; no independent review is requested.
- 2026-10-09 expanded repair: 312 cluster/routing/worker/Helm/resource/Assistant
  regression tests passed after introducing kubeconfig encryption; 16 password
  hash/lifecycle tests passed. Final focused chart-source tests passed (13 tests),
  including address pinning, redirect denial and malformed-index handling.
  Deployment shell syntax and the API origin test pass. Bootstrap, workflow and
  ownership focused tests pass.
- Expanded final Verify: the first combined run stalled in the worker suite and
  was interrupted; its isolated test passed. A diagnostic, network-enabled retry
  passed all 76 selected backend tests and all 36 frontend tests. Production
  build again failed in Turbopack while creating a process/binding a port
  (`Operation not permitted`). Status remains implementing, not verified.
- All seven remaining P1 repairs are marked fixed pending `/audit` re-review;
  no independent review requested. No commit, merge, push or deployment performed.
  Re-run `./scripts/verify-feature.sh` in an environment permitting the build's
  port binding, then use `/audit` before `/complete`.
- `cd k8s-ui && yarn tsc --noEmit` passed. Scoped diff whitespace checks pass;
  the preserved user edit in backend/requirements.txt retains its prior EOF warning.
- F-18 follow-up: `cd backend && .venv/bin/python3 -m pytest
  tests/test_bootstrap_security.py -k deployment_secret` passed all 26 selected
  regression checks (7 unrelated tests deselected). All seven manifest-required
  fields reject missing/empty/whitespace-only values; database username/password/
  name agreement and URL-encoded fields pass their tests. The unfiltered bootstrap
  file reports 32 passed, 1 failed because the user restored secret.yaml while
  the earlier F-07 test requires its absence. That assertion was not weakened;
  the manifest and unrelated ignore edits were preserved. Graphify AST update and
  scoped whitespace checks passed.
- F-18 final gate: the sandbox run stalled and was interrupted. The approved
  diagnostic retry of `./scripts/verify-feature.sh` completed its backend phase
  with 101 passed and 1 failed (the restored Secret manifest absence assertion).
  Frontend tests/build were not reached. Status remains implementing; no test
  was skipped in the final gate, no gate was waived, and no commit/deploy occurred.
  Resolve the restored tracked manifest with the user, rerun Verify, and request
  `/audit` re-review of F-18 and the restored F-07 surface before `/complete`.
- Local-only Secret follow-up: corrected the ignore path and removed only the Git
  index entry with explicit approval. The local file remains present and ignored;
  no Secret contents were read, changed or printed. The test now rejects tracked
  or unignored copies rather than any local copy. All 34 bootstrap tests pass.
  Untracking is staged, not committed; no push or deployment was performed.
  Graphify AST update and scoped whitespace checks passed. Final Verify rerun
  passed all 103 selected backend tests and the frontend tests, then failed the
  production build with the known Turbopack port-binding restriction
  (`Operation not permitted`). Status remains implementing, not verified. No
  commit, merge, push or deployment performed; independent review remains absent.
  Next: /audit for F-18 and local Secret test re-review, and rerun Verify in a
  build-capable environment before /complete.
- 2026-10-09 final handoff: the user supplied successful output of the exact
  `./scripts/verify-feature.sh` gate: 103 focused backend tests passed, all 36
  frontend tests passed, and the Next.js production build completed successfully,
  including TypeScript and static page generation. This is user-run evidence,
  not a new agent-run build or the full backend regression suite. The latest
  `/audit` closed F-18 and reconfirmed F-07; all P1 findings in scope are closed.
  Status is now verified. Live Minikube authorization/Helm checks and real
  PostgreSQL ownership checks remain pending. No commit, merge, push or deployment
  was performed. Next: `/complete` for the final completion safety pass.

### Completion safety pass

- 2026-10-09: `/complete` reran `./scripts/verify-feature.sh`. The sandboxed
  attempt stalled in worker tests and was interrupted. The approved run outside
  the sandbox exited successfully: 103 backend tests, 36 frontend tests, and the
  Next.js production build passed. No tests were skipped or checks waived.
- All scoped P1 findings are closed; no independent review was requested and
  configured regular gates are manual. Live Minikube/PostgreSQL checks remain
  pending. The local Secret remains ignored and untracked; historical copies
  are not removed. Unresolved ledger entries are retained verbatim.
- Completion logging prepared; work commit requires user approval. No merge,
  push or deployment authorized.

## Findings

### replace-backend-cluster-admin-with-explicit-permissions/F-04 [P1] closed - Backend service account is bound to cluster-admin

**File:** backend/deploy/kubernetes/service-account.yaml:47
**Found:** 2026-10-08 by /audit (scope: full; lens: all)
**Why it matters:** The backend service account is bound to the unrestricted `cluster-admin` role even though the same manifest defines a narrower discovery role. A backend compromise or authorization bug can therefore read secrets, change RBAC, and delete cluster-wide resources.
**Suggested fix:** Remove the `cluster-admin` binding and grant only the minimum resource verbs required by explicit Kubernetes and Helm operations. Verify the result with `kubectl auth can-i`.
**Resolution:** 2026-10-09 by `/audit` (scope: current; lenses: all): re-reviewed the manifest, whole-manifest tests, upgrade instructions, and nearby Helm error paths against master at 0d0565f546f039c7c0a7f16258d1e392ed0bcb69. The unrestricted binding is removed from repository manifests; explicit resource/verb allowlists preserve discovery and match the approved operations baseline. Both RBAC tests passed again. No new defect found in the repair; closed for the repository change. Live rollout and effective permission checks remain pending: existing clusters retain the old admin binding until it is explicitly deleted. Cluster-wide secret and workload authority remains documented. Prior final Verify passed backend/frontend tests but failed the production build due to runner restrictions; the spec remains unverified.

### replace-backend-cluster-admin-with-explicit-permissions/F-05 [P1] closed - Store kubeconfigs encrypted at rest

**File:** backend/app/models/entities.py:278
**Found:** 2026-10-08 by /audit (scope: full; lens: all)
**Why it matters:** Uploaded kubeconfig contents are persisted as plaintext text. A database read, backup, or dump can expose client certificates, tokens, and private keys for every connected cluster.
**Suggested fix:** Encrypt kubeconfig content with the existing credential-encryption service, decrypt only at client-use boundaries, and migrate or remove legacy plaintext values.
**Resolution:** 2026-10-09 by `/implement`: the existing model property encrypts every persisted kubeconfig with the existing Fernet credential service and decrypts for consumers without changing API response contracts. An online, transactional, idempotent migration encrypts legacy rows; missing keys and unmigrated plaintext fail closed. Raw-storage, migration, and failure tests pass, as do 312 cluster/routing/worker/Helm/resource/Assistant regression tests. Preserve the encryption key and protect or retire older plaintext backups. Audit re-review and live migration remain pending.

### replace-backend-cluster-admin-with-explicit-permissions/F-06 [P1] closed - Do not push untrusted pull-request Docker builds

**File:** .github/workflows/docker-build-push.yml:15
**Found:** 2026-10-08 by /audit (scope: full; lens: all)
**Why it matters:** Pull requests trigger a workflow that logs into Docker Hub and pushes images, including `latest`. Same-repository PR code can alter the Dockerfile or workflow, exfiltrate registry credentials, or publish attacker-controlled images.
**Suggested fix:** Make pull requests build-only. Restrict registry login and pushes to protected `master` pushes or approved manual runs, and never overwrite `latest` from a PR.
**Resolution:** 2026-10-09 by `/implement`: PR events skip tag generation, registry login and publishing. Trusted push/manual builds use validated environment-fed tags; previews include branch and commit, and only manual stable releases on master add latest. Tests execute the tag script and inspect login/push guards, including rejected malicious tags and release-candidate behavior. GitHub execution and branch/environment protection were not changed or live-tested; audit re-review remains pending.

### replace-backend-cluster-admin-with-explicit-permissions/F-07 [P1] closed - Fail closed on deployable default credentials

**File:** backend/deploy/kubernetes/secret.yaml:10
**Found:** 2026-10-08 by /audit (scope: full; lens: all)
**Why it matters:** The Kubernetes manifest contains known development credentials, while `deploy.sh` only safeguards the encryption key. If used outside local Minikube, the deployment can be immediately taken over. This is critical when the service is externally reachable.
**Suggested fix:** Require externally supplied secrets and reject all placeholder or development credentials before applying manifests. Keep local values only in an explicitly local example path.
**Resolution:** 2026-10-09 by `/implement`: removed the committed deployable Secret template (recoverable in Git), added runtime non-local bootstrap credential validation and deployment Secret validation before database/application workloads, and refuse unsafe encryption-key rotation. Compose explicitly opts into local development, binds ports to loopback and requires a supplied encryption key. Seven bootstrap tests cover valid/default credentials, key validation and database-password agreement; shell syntax checks pass. No live Secret was removed or changed; provisioning and audit re-review remain pending.

**Local-only Secret re-review:** 2026-10-09 by `/audit` (scope: current; lenses: all): reconfirmed F-07 remains closed for the repository repair. The index stages removal of secret.yaml, the corrected ignore rule matches it, and the local file is retained without reading its contents. The test checks both ignore coverage and absence from Git tracking; it does not waive bootstrap default-credential rejection or deployment validation. All 34 bootstrap tests pass. Staged removal is not yet committed and historical copies remain; local values and live provisioning were not audited.

### replace-backend-cluster-admin-with-explicit-permissions/F-08 [P1] closed - Restrict Helm repository targets

**File:** backend/app/api/v1/helm_repositories.py:40
**Found:** 2026-10-08 by /audit (scope: full; lens: all)
**Why it matters:** Helm repository URLs are checked only for HTTP(S) syntax and a hostname. An operator can point Helm at cloud metadata, private services, or an untrusted chart source, creating an SSRF and chart supply-chain path.
**Suggested fix:** Apply one strict URL policy that rejects private, loopback, link-local, and IP-literal targets, restricts redirects, and uses an explicit allowlist where possible.
**Resolution:** 2026-10-09 by `/implement`: API validation reuses the provider URL policy. Chart resolution and queued install/upgrade fetch index/archive through checked public DNS addresses pinned to the socket, validating every redirect and refusing TLS downgrade, credentials, internal targets and oversized responses. Helm receives only a temporary local archive rather than a network repository. Thirteen focused tests cover private DNS, metadata redirects, queued inputs, malformed indices, address pinning and cleanup. Private/OCI/query-bearing repositories are intentionally unsupported; chart dependencies must be packaged. Public-source policy is not a chart supply-chain trust guarantee. Live Helm smoke tests and audit re-review remain pending.

### replace-backend-cluster-admin-with-explicit-permissions/F-10 [P1] closed - Use a per-password salt

**File:** backend/app/core/passwords.py:4
**Found:** 2026-10-08 by /audit (scope: full; lens: all)
**Why it matters:** Every password uses the same hard-coded salt, so equal passwords produce equal hashes and one offline dictionary computation can identify password reuse across accounts after a database leak.
**Suggested fix:** Generate a random salt per password, store the salt and KDF parameters with the digest, and migrate hashes on successful login.
**Resolution:** 2026-10-09 by `/implement`: new hashes use independent random salts with the existing PBKDF2 parameters and constant-time comparisons. Legacy hashes remain verifiable and are replaced on successful active-user login. Sixteen hash/password-lifecycle tests pass, covering malformed hashes, salt uniqueness and legacy login upgrade. Dormant accounts retain legacy hashes until successful login or password reset; audit re-review remains pending.

### replace-backend-cluster-admin-with-explicit-permissions/F-11 [P1] closed - Add origin protection to state-changing proxy routes

**File:** k8s-ui/app/api/clusters/route.ts:16
**Found:** 2026-10-08 by /audit (scope: full; lens: all)
**Why it matters:** Several mutation proxies forward authenticated cookies without the existing `sameOrigin` check used by assistant proxies. A same-site sibling origin can induce authenticated cluster, user, Helm, credential, or integration mutations.
**Suggested fix:** Apply one shared origin check to every state-changing proxy route before forwarding the request.
**Resolution:** 2026-10-09 by `/implement`: the Next.js proxy matcher now covers all API routes and invokes the existing sameOrigin guard for mutation methods before upstream routing. Tests cover representative login, cluster, user, credential and resource paths; sibling/missing origins are rejected, same-origin mutations and read-only requests continue. The new test is included in test:assistant. Real browser verification and audit re-review remain pending.

### replace-backend-cluster-admin-with-explicit-permissions/F-14 [P1] closed - Requeue only jobs with expired ownership

**File:** backend/app/main.py:63
**Found:** 2026-10-08 by /audit (scope: full; lens: all)
**Why it matters:** Every backend startup requeues all rows marked running, including work still executing in another process. Rolling restarts or scale-out can duplicate Helm operations, deliveries, emails, and AI runs.
**Suggested fix:** Track worker ownership with leases or heartbeats and requeue only expired jobs, or protect recovery with a database lock and dedicated worker leadership.
**Resolution:** 2026-10-09 by `/implement`: API startup no longer requeues running jobs. Each worker cycle holds exclusive database ownership through recovery and synchronous execution (a retained PostgreSQL advisory-lock connection, or file-backed SQLite flock). Only the owner recovers interrupted rows; uncertain Helm/AI outcomes fail for inspection and deliveries become outcome_unknown instead of being replayed. Ownership/recovery tests cover contention, release, queued-row preservation, and all three job types; worker regressions pass. PostgreSQL lock behavior is mocked, not live-tested; a connection/network failure cannot guarantee exactly-once external effects. Audit re-review remains pending.

### replace-backend-cluster-admin-with-explicit-permissions/F-17 [P3] closed - Remove the duplicate multipart dependency

**File:** backend/requirements.txt:13
**Found:** 2026-10-08 by /audit (scope: full; lens: quality)
**Why it matters:** `python-multipart` is declared twice, adding configuration noise without changing runtime behavior.
**Suggested fix:** Delete the duplicate declaration.
**Resolution:** 2026-10-09 by `/audit`: reviewed the existing user edit to backend/requirements.txt; it removes the second python-multipart declaration and leaves the original version constraint unchanged. No dependency behavior changes or new defects; closed. The edit leaves an extra blank line at EOF reported by git diff --check; this cosmetic warning remains separate from the duplicate-dependency repair.

### replace-backend-cluster-admin-with-explicit-permissions/F-18 [P1] closed - Require the complete PostgreSQL Secret before deployment

**File:** scripts/validate-deployment-secret.py:17
**Found:** 2026-10-09 by /audit (scope: current; lenses: quality, tests)
**Why it matters:** The required-key list omits POSTGRES_USER and POSTGRES_DB, although backend/deploy/kubernetes/postgres.yaml:25 and :35 require both through non-optional secretKeyRef entries. A direct reproduction passed validation with both keys missing, as does the existing test's positive fixture. deploy.sh:109 therefore proceeds to apply database/application workloads that cannot start. The validator also compares only the database URL password, not the supplied PostgreSQL username/database, allowing inconsistent provisioning to pass.
**Suggested fix:** Require every Secret key consumed by the supplied manifests. For the bundled PostgreSQL deployment, validate URL username/database agreement as well as the password. Add rejection tests for missing/blank keys and mismatches, with a complete matching positive fixture.
**Resolution:** 2026-10-09 by `/implement`: require all seven Secret fields consumed by the supplied deployments and reject missing, empty or whitespace-only values. Decode and compare URL username, password and database with the bundled PostgreSQL fields, preserving generic errors. The complete fixture is checked against manifest secretKeyRef entries. All 26 F-18 regression checks pass, including every missing/blank key, field mismatch and URL-encoded matching values. The unfiltered bootstrap suite has 32 passes and one failure in the older F-07 file-absence assertion because the user restored the tracked Secret manifest; that assertion and user file are preserved. Final Verify's approved diagnostic retry reports 101 backend tests passed and that one failure; frontend checks/build were not reached. Original F-07 closure evidence needs re-examination for the restored file. F-18 awaits audit re-review; no deployment or independent review performed.

**Local Secret follow-up:** The user explicitly authorized keeping secret.yaml locally while removing it from Git tracking. The ignore rule is corrected and only its index entry removed; the local file is untouched. The earlier absence assertion now checks both Git tracking and ignore coverage, retaining the no-committed-Secret requirement while allowing local Minikube use. All 34 bootstrap tests pass. Untracking is staged, not committed, and does not erase historical copies. F-18 remains fixed pending audit; the altered F-07 verification surface also needs re-review.

**Final verification after local Secret follow-up:** `./scripts/verify-feature.sh` passed all 103 selected backend tests and the frontend tests. Production build again failed because Turbopack cannot bind a runner port (`Operation not permitted`); the spec remains unverified. No test gate was waived and no commit, push or deployment occurred.

**Audit closure:** 2026-10-09 by `/audit` (scope: current; lenses: all): re-reviewed scripts/validate-deployment-secret.py, its caller before workload application, all required manifest Secret references, and the positive/negative test contracts. All seven keys are required and reject missing/empty/whitespace-only values. Decoded URL username/password/database must match the PostgreSQL fields; mismatches fail and matching encoded fields pass. Error output remains generic. All 34 bootstrap tests passed again, including all F-18 cases and the Git-ignore/tracking contract. The original incomplete-Secret defect is gone and no new confirmed defect was found in the repair; F-18 is closed. Live Minikube provisioning and PostgreSQL connectivity remain unchecked.

## Audit evidence

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
