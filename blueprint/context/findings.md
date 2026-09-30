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
