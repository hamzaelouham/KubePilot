# Current Feature

> **Generated file.** Holds the one feature, fix, or rollback being built right now. Run
> `/feature <number-or-name>` to spec a build-plan feature, or `/fix "<bug>"` for
> an ad-hoc fix. Use `/rollback <completed-feature>` to plan a safe reversal.
> Build one thing at a time; `/complete` archives it under
> `blueprint/history/` and resets this file.

## Deploy the local Secret safely

**Type:** Fix
**Status:** verified
**Branch:** fix/deploy-the-local-secret-safely
**Fixes:** F-20, F-21

### The problem

`deploy.sh` validates only the Secret already in Minikube and never applies
`backend/deploy/kubernetes/secret.yaml`. The user wants the ignored local file
included in deployment. Applying it blindly could overwrite the encryption key
or desynchronize credentials from an initialized PostgreSQL database.

### The fix

- When the local Secret file exists, validate its complete contents and expected
  Secret name/namespace before applying it. Support Kubernetes data/stringData
  representations without printing values or including them in command arguments.
- For an existing installation, reject any encryption-key change before Secret
  application. Reject database credential/URL changes that need a coordinated
  database update rather than silently overwriting the working configuration.
- Apply the valid local Secret after the namespace exists and before the current
  live validation and database/application workload application. Preserve the
  existing externally provisioned Secret path when no local file exists.
- Keep the file ignored/untracked. Do not change credentials, encryption keys,
  database contents, images, or running workloads during implementation.
- Preserve the existing uncommitted PostgreSQL recovery manifest change; do not
  include it as a new change or silently discard it.

### Build steps

- [x] Add guarded local Secret application, focused regression tests and a short
  deployment documentation update. Reuse the existing Secret validator and
  installed tooling rather than adding dependencies.
  **Done when:** a valid new Secret is applied before workloads; a matching
  existing Secret is accepted; absent local files retain external provisioning;
  invalid/incomplete/wrong-identity Secrets, changed encryption keys and unsafe
  database credential updates fail before Secret/workload writes. Tests use
  synthetic Secrets and mocked Kubernetes commands, and check error output does
  not reveal credentials.

- [x] Address F-20 in the shared deployment validator: reject unsupported database
  drivers, missing hosts and invalid ports before Secret writes.
  **Done when:** direct validator and executable deployment regression tests
  reject unusable URLs before Secret/workload writes, while supported URLs with
  default/custom ports and URL-encoded matching credentials still pass.

- [x] Address F-21: compare the database name as SQLAlchemy actually uses it;
  reject query parameters, fragments and parser-normalized/ambiguous URLs before
  Secret writes. Preserve encoded username/password support without new dependencies.
  **Done when:** accepted URLs produce matching effective SQLAlchemy connection
  fields; encoded-name mismatches and query overrides fail direct validation and
  executable deployment tests before Secret/workload writes. Document the bounded
  deployment URL format and its unsupported query-based options.

### Verify

- `bash -n deploy.sh`.
- Focused backend deployment/Secret tests, including executable script ordering
  and failure-path checks without contacting the live cluster.
- Final project gate: `./scripts/verify-feature.sh`.
- Graphify AST update after changes. No live deployment, commit, merge or push
  without separate approval. Review through `/audit` before completion because
  the change touches Secret provisioning and encryption-key preservation.

### Implementation evidence

- 2026-10-09: `bash -n deploy.sh` and `git diff --check` passed.
- `cd backend && .venv/bin/python3 -m pytest tests/test_bootstrap_security.py`
  passed 65 tests. The executable deployment tests use synthetic Secrets and a
  fake Minikube executable; they never contact the running cluster.
- `./scripts/verify-feature.sh` passed: 65 focused backend tests, 36 frontend
  tests, and the production build. Ran outside the sandbox to avoid the known
  build port-binding restriction. No skips or gate waivers.
- The helper validates and normalizes one local Secret, compares immutable
  installation key/database fields, refuses missing live credentials when
  PostgreSQL storage exists, and sends normalized values only through stdin.
  Existing updates retain resourceVersion for conflict detection. API details
  and YAML parser errors are suppressed; uncertain API failures instruct the
  operator to inspect live state rather than claiming no write occurred.
- Graphify AST update completed. Regular gates are manual; `/audit` of this
  security-sensitive provisioning change remains the next step before completion.
  At that initial handoff, no independent review was requested and no open/fixed
  P0/P1 ledger entries remained. The subsequent audit raised F-20; see the repair
  evidence below. Existing P2 follow-ups remain unchanged.
- No live deployment or credential changes, commit, merge, or push performed.
  The pre-existing PostgreSQL recovery YAML change is preserved, not part of this
  fix. Review its inclusion separately before creating any completion commit.
- Manual try, only when ready for a local rollout: `./deploy.sh --no-build`
  uses the ignored Secret if present, otherwise the externally provisioned live
  Secret. Preserve the working encryption key/database values; this is not a
  database password rotation tool. Live application of this new path is untested.

### F-20 repair evidence — 2026-10-09

- The shared validator now requires the installed `postgresql+psycopg` driver,
  a nonempty host and an optional port from 1 to 65535. Invalid URL errors are
  generic and credential-free, before local Secret writes or workload application.
- Direct validator tests and executable fake-Minikube tests cover unsupported
  drivers, missing hosts and invalid ports across new local, existing local and
  externally provisioned Secrets. Encoded matching fields, omitted/custom ports
  and IPv6 hosts remain supported.
- Focused bootstrap tests passed: 104. Exact `./scripts/verify-feature.sh` passed:
  104 backend tests, 36 frontend tests and production build; no skipped tests.
  The gate ran outside the sandbox for the known Next.js port-binding restriction.
- `bash -n deploy.sh`, `git diff --check` and Graphify AST update passed.
- F-20 is fixed, pending `/audit` re-review; it is not closed and still blocks
  `/complete`. No live deployment, credential changes, commit, merge or push.
  The unrelated PostgreSQL recovery manifest edit remains preserved separately.

### F-21 repair evidence — 2026-10-09

- Compare the database path literally, consistent with SQLAlchemy's actual
  connection arguments. Retain encoded username/password support. Reject query
  parameters/fragments and parser-normalized/ambiguous URL forms before writes.
  Document that query-based connection/TLS options are unsupported in this
  Minikube deployment path; no runtime dependencies added.
- Accepted-URL tests use the installed SQLAlchemy dialect to verify effective
  username/password/database values without a database connection. Rejection
  cases include encoded-name mismatches, credential/database/host/port query
  overrides, fragments and ambiguous forms; fake executable deployment tests
  prove no Secret/workload writes for new local, existing local and external
  provisioning cases.
- Focused bootstrap tests passed: 156. Exact `./scripts/verify-feature.sh` passed:
  156 backend tests, 36 frontend tests and production build. No skips or waivers;
  ran outside the sandbox for the known Next.js port-binding restriction.
- `bash -n deploy.sh`, `git diff --check` and Graphify AST update passed.
- F-20 was closed by the preceding audit. F-21 is fixed, pending `/audit`
  re-review, and still blocks `/complete`. All configured regular gates are
  manual; no independent review requested and no runtime check performed.
- No live deployment, real Secret access, credential changes, commit, merge or
  push. The unrelated PostgreSQL recovery manifest edit remains preserved;
  resolve its inclusion separately before a completion commit. The existing
  manual try path remains `./deploy.sh --no-build`, only with separate rollout
  approval and the working installation's encryption key/database values.

### Completion approval and final gates — 2026-10-09

- User explicitly approved committing all tracked changes, including the existing
  PostgreSQL recovery manifest edit. This supersedes the earlier instruction to
  decide its inclusion separately: retain Recreate and the matching recovered PVC
  name in both Deployment and PVC. No recovery artifacts or Secret values included.
- Completion reran exact `./scripts/verify-feature.sh`: 156 backend tests,
  36 frontend tests and production build passed. Shell syntax and diff whitespace
  passed. F-20 and F-21 closed by audit; unresolved P2 entries stay in the live ledger.
- Local Secret remains ignored/untracked. No independent review requested;
  configured regular gates manual. No live deployment, credential change or push.
- How to try, only with separate rollout approval: `./deploy.sh --no-build`.
  Preserve the installation key/database values. Query-based connection/TLS
  options are unsupported; real API-server deployment/concurrency remains untested.

## Findings

### deploy-the-local-secret-safely.md/F-20 [P1] closed - Reject unusable database URLs before deploying Secrets

**File:** scripts/validate-deployment-secret.py:31
**Found:** 2026-10-09 by /audit (scope: current; lenses: quality, security, tests)
**Why it matters:** The shared validator compares decoded username/password/database but does not validate the supported SQLAlchemy driver or port. The new local Secret path relies on that validator before creating/replacing the live Secret. A synthetic, complete Secret using an unsupported driver passed through apply_local_secret and reached a mocked Kubernetes create; SQLAlchemy create_engine rejected the same URL with NoSuchModuleError, without any network connection. A PostgreSQL+psycopg URL with a nonnumeric port also passed prepare_local_secret and was rejected by create_engine with ValueError. The deployment can therefore write an unusable Secret and proceed to application workloads that cannot start. This is an existing validator gap exposed by the newly added local-file deployment path, not an encryption-key rotation bypass.
**Suggested fix:** Validate the deployment database URL against the actual supported PostgreSQL driver and structural URL requirements before any Secret write. Reject invalid ports and unsupported schemes/drivers with generic credential-free errors. Add direct validator and executable deployment tests showing these inputs cannot create/replace a Secret or apply workloads; retain valid URL-encoded credential cases.
**Resolution:** Closed by /audit on 2026-10-09 after re-reading the repaired validator, its callers and regression tests. The original unsupported-driver and invalid-port defects are gone: the installed postgresql+psycopg driver, nonempty host and optional port from 1 to 65535 are required before writes. All 104 bootstrap tests passed again, including rejection across new local, existing local and externally provisioned Secrets; valid ports and encoded credentials remain accepted. Shell syntax and diff whitespace passed. Reused the immediately preceding exact Verify evidence: 104 backend tests, 36 frontend tests and production build. A separate, pre-existing disagreement with SQLAlchemy's connection-field parsing is recorded as F-21, not a failure of this driver/port repair. No real Secret was read or written, no deployment or credential changes occurred, and unrelated P2 findings remain unchanged.

### deploy-the-local-secret-safely.md/F-21 [P1] closed - Validate the connection fields the backend actually uses

**File:** scripts/validate-deployment-secret.py:44
**Found:** 2026-10-09 by /audit (scope: current; lenses: quality, security, tests)
**Why it matters:** The validator checks urllib URL fields, but backend/app/db/session.py:11 passes the unchanged URL to SQLAlchemy. Those parsers do not have identical semantics. SQLAlchemy retains percent escapes in the database name, so the advertised encoded database-name case validates against the decoded POSTGRES_DB but connects using a different database name. SQLAlchemy's PostgreSQL dialect also allows query parameters to override connection fields: a URL whose authority/path match the Secret but whose query supplies different password and dbname values passes validation and uses those different values at runtime. Two synthetic, read-only reproductions each reached a mocked Secret create, then SQLAlchemy's actual dialect.create_connect_args confirmed a different database; the query case also confirmed a different password. This can deploy an unusable or unintended database configuration despite a passing validator. Existing tests only assert validator acceptance/rejection, not agreement with the runtime connection arguments.
**Suggested fix:** Align deployment validation with the backend's effective SQLAlchemy/psycopg connection fields. Reject credential/database overrides in query parameters (or validate their effective values), and correctly support or explicitly reject database-name encoding before Secret writes. Preserve supported encoded username/password behavior. Add regression tests comparing effective runtime arguments and proving mismatches cannot write Secrets or apply workloads; correct the documentation's encoded database-name claim.
**Resolution:** Closed by /audit on 2026-10-09 after re-reviewing the complete validator, deployment callers, tests, documentation and SQLAlchemy runtime parsing. The original encoded database-name mismatch and query overrides are rejected before writes; accepted encoded username/password and literal database names agree with actual SQLAlchemy dialect connection arguments. Query parameters/fragments, parser-normalized URL forms and ambiguous raw authority separators fail closed. Documentation explicitly excludes query-based connection/TLS options. Re-ran all 156 bootstrap tests successfully, including effective runtime-field assertions and no-write checks for new local, existing local and externally provisioned Secrets. Shell syntax and diff whitespace passed. Reused immediately preceding exact Verify evidence: 156 backend tests, 36 frontend tests and production build. No new confirmed defect from this repair. No live deployment, real Secret access, credential changes, commit, merge or push.
