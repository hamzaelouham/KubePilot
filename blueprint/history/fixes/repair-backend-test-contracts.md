# Current Feature

> **Generated file.** Holds the one feature, fix, or rollback being built right now. Run
> `/feature <number-or-name>` to spec a build-plan feature, or `/fix "<bug>"` for
> an ad-hoc fix. Use `/rollback <completed-feature>` to plan a safe reversal.
> Build one thing at a time; `/complete` archives it under
> `blueprint/history/` and resets this file.

## Repair backend test contracts

**Type:** Fix
**Status:** verified
**Branch:** fix/repair-backend-test-contracts
**Fixes:** F-09

### The problem

F-09 records a full backend run with 654 passing tests and three failures:
marketplace response assertions reject added fields, and the metadata test's
exact table inventory omits tables introduced by shipped features. That result
is historical; reproduce the current failures before editing expectations.
The local focused gate does not substitute for the full backend CI regression.

### The fix

- Compare failing assertions in `backend/tests/test_marketplace.py` and
  `backend/tests/test_models.py` with the actual response schemas, consumers,
  model registrations, migrations and shipped feature contracts.
- Where additions are intentional, update the explicit field/table inventories
  and assert meaningful new-field values and relevant ownership constraints.
  Retain exact contract checks and sensitive-data exclusion assertions.
- If an addition is unintended or its contract is ambiguous, stop for a decision
  instead of treating current output as automatically correct.
- Do not remove shipped functionality, weaken exact assertions to subset checks,
  derive expected inventories from the implementation, skip tests, alter CI or
  change database contents/credentials. No new runtime dependencies or live
  migrations. Preserve the pending F-01/F-02/F-03 audit ledger changes.

### Build steps

- [x] Reproduce the marketplace/model failures, establish the intended contracts
  and make the smallest test/fixture repair with explicit regression assertions.
  **Done when:** the exact marketplace response checks and metadata inventory
  agree with documented shipped behavior, preserve ownership and secret-safety
  checks, and all marketplace/model tests pass. Run the full backend suite to
  prove F-09's failing-regression condition is gone; unrelated failures must be
  reported rather than waived or repaired outside this scope.

### Verify

- Narrow reproduction and iteration:
  `cd backend && .venv/bin/python3 -m pytest tests/test_marketplace.py tests/test_models.py -q --tb=short`.
- Full backend regression: `cd backend && .venv/bin/python3 -m pytest`.
- Final exact project gate: `./scripts/verify-feature.sh` (focused backend tests,
  frontend Assistant tests and production build). Do not weaken focused coverage.
- `git diff --check`; Graphify AST update after code/test changes.
- No new user-facing behavior is intended; no live deployment/provider calls,
  dev server or online database migration needed. After passing checks, mark F-09
  fixed and request `/audit` to re-review before closure/completion. Configured
  regular gates are manual; no independent review requested.

### Implementation evidence — 2026-10-09

- Reproduced exactly three failures in marketplace/model tests: 69 passed,
  3 failed. The response schema and marketplace-history consumer intentionally
  support installation/agent-run metadata; model declarations and shipped agent
  and conversation migrations account for the eight omitted tables.
- Updated two explicit response-field inventories and asserted installation
  defaults for job_type, trigger_type, owner_id, result_code and attempt_count.
  Added eight explicit table names and eight parameterized non-null ownership
  foreign-key/deletion-policy checks. Existing exact equality, ordering and
  sensitive-value exclusion checks retained. No application/schema/migration
  changes or new dependencies.
- Targeted formerly failing cases plus model tests passed: 12 tests.
- Full backend `cd backend && .venv/bin/python3 -m pytest` passed all 853 tests
  in 760.45s. No skips, failing tests or waivers.
- Exact final `./scripts/verify-feature.sh` passed: 80 changed-file backend tests,
  36 frontend tests, TypeScript and production build. `git diff --check` and
  Graphify AST update passed.
- F-09 marked fixed pending `/audit` re-review, not closed. Earlier F-01/F-02/F-03
  closure updates preserved; other remaining P2 entries unchanged. No P0/P1
  blockers or independent review request; configured regular gates are manual.
- Manual proof path: rerun the narrow marketplace/model command under Verify;
  no new UI behavior to try. No dev server, online database migration, live
  provider call, deployment, commit, merge or push performed. Remote CI results
  have not been checked. Next: `/audit`, then `/complete` after re-review.

### Final completion verification — 2026-10-13

- `./scripts/verify-feature.sh` passed: 80 focused backend tests, 36 Assistant
  tests, TypeScript checking and the Next.js production build.

## Findings

### repair-backend-test-contracts/F-01 [P2] closed - Translate queued test-delivery failures into API errors

**File:** backend/app/api/v1/agents.py:178
**Found:** 2026-09-30 by /audit (scope: current; lens: all)
**Why it matters:** `queue_test_delivery` delegates to `enqueue_delivery`, which can raise `DeliveryServiceError` if the connection is revoked between the pre-check and the queue operation. This route does not translate that error, so the global handler returns a generic 500 instead of the stable safe delivery error contract.
**Suggested fix:** Catch `DeliveryServiceError` in the agent test endpoint and map it to the same status/code response used by the integration delivery routes.
**Resolution:** Closed by /audit on 2026-10-09. Re-reviewed the test route, enqueue boundary, permission dependencies and regression test. DeliveryServiceError preserves its status/code/message; the simulated revoked-connection case verifies the exact safe 409 body. Agent/integration-delivery tests passed 34 cases. No new defect found in the repaired boundary; no actual provider message sent.

### repair-backend-test-contracts/F-02 [P2] closed - Distinguish retrying from initially queued deliveries

**File:** k8s-ui/components/assistant/agents/notifications.tsx:234
**Found:** 2026-09-30 by /audit (scope: current; lens: all)
**Why it matters:** The worker represents a scheduled retry as `status="queued"` with `attempt_count > 0`, but this panel renders only the raw status, so an administrator cannot tell whether a test is waiting for its first attempt or retrying after a provider failure.
**Suggested fix:** Derive and render a retrying state from the attempt count, matching the existing Settings delivery-history presentation.
**Resolution:** Closed by /audit on 2026-10-09. Re-reviewed the notification panel, delivery schema and worker retry transitions: queued with attempt_count greater than zero renders retrying, initial queued remains queued, and attempt progress is shown. Frontend bridge/client tests passed 36 cases; reused the recent successful build/TypeScript evidence for the unchanged component. This label branch was verified by code inspection, not a component/browser test; live retry presentation remains untested. No new defect found in the repair.

### repair-backend-test-contracts/F-03 [P2] closed - Avoid one connection query per destination

**File:** backend/app/services/agent_notifications.py:57
**Found:** 2026-09-30 by /audit (scope: current; lens: all)
**Why it matters:** `list_destinations` calls `destination_summary` once per row, and each summary performs a separate `IntegrationConnection` query. Because destinations are independently configurable and have no per-agent bound, listing an agent with many destinations performs an unbounded N+1 query pattern.
**Suggested fix:** Load the supported connection rows once and pass a provider-to-status map into the summaries, or join the connection status into the destination query.
**Resolution:** Closed by /audit on 2026-10-09. Re-reviewed listing, summary callers and the unique provider constraint. Listing uses one outer join and pure summaries; single-item mutation summaries retain their one lookup. SQL capture verifies exactly one connection-table query for three destinations across multiple providers, including missing connections. Agent/integration-delivery tests passed 34 cases. No new defect found in the repair; no load benchmark performed.

### repair-backend-test-contracts/F-09 [P2] closed - Repair the failing backend test contract

**File:** backend/tests/test_marketplace.py:744
**Found:** 2026-10-08 by /audit (scope: full; lens: all)
**Why it matters:** The backend suite reports 654 passed and 3 failed. Marketplace tests reject fields now returned by the API, and metadata tests reject newly added tables, so the repository Verify command remains red.
**Suggested fix:** Decide whether the new response fields and tables are intentional, then update the exact contract tests or remove the unintended behavior. Do not weaken assertions merely to pass.
**Resolution:** Closed by /audit on 2026-10-13. Re-reviewed the exact response schema, route construction and UI consumer, registered models, and corresponding migrations. The explicit response fields/defaults match the schema and consumer; all eight added table names and tested ownership foreign-key/nullability/deletion policies match model metadata and migrations. Exact key, ordering, and sensitive-value checks remain intact. `tests/test_models.py` passed 10 tests; the marketplace test run could not be reconfirmed during that audit because it produced no output and was interrupted. The subsequent final `./scripts/verify-feature.sh` passed 80 focused backend tests, 36 Assistant tests, TypeScript checking, and the production build.
