# Pod Logs bounded viewer redesign

**Type:** Fix
**Status:** verified
**Branch:** `fix/pod-logs-bounded-viewer-redesign`

## The problem

The Pod Logs tab renders every returned line in an unconstrained code block, so
large snapshots make the resource-detail page feel endless and force users to
scroll the entire page to reach the newest entries. The presentation is also
visually weaker than the polished card, toolbar, metadata, and state patterns
used by Settings Audit Logs.

The backend already returns a finite snapshot of the latest 500 lines capped at
100 KB. This fix must preserve that boundary and must not introduce live-follow,
automatic polling, or unbounded client-side accumulation.

## The fix

Redesign the Pod Logs tab as a bounded, responsive log viewer using the existing
shadcn/ui and theme tokens. Give it an Audit Logs-style card header with pod and
container context, line-count/truncation metadata, and a manual Refresh action.
Render the snapshot inside a fixed-height, internally scrollable monospace
surface so the surrounding page stays stable. Position a newly loaded snapshot
at the newest line, preserve intentional manual reading while the user is away
from the bottom, and expose an accessible Scroll to bottom control whenever the
latest line is out of view.

Preserve authentication, cluster and namespace scoping, backend size limits,
loading/empty/error states, horizontal scrolling for long lines, responsive
layout, and light/dark theme support.

## Build steps

- [x] **Step 1: Build the bounded Pod Logs viewer and controls.** Refactor the
  resource-detail log panel into a reusable, polished card with header context,
  bounded vertical scrolling, line and truncation status, manual refresh, and
  an accessible Scroll to bottom action. Wire refresh through the existing
  scoped logs request without polling or accumulating previous snapshots.
  **Done when:** opening a Pod Logs tab shows the newest line in a fixed-height
  viewer; large snapshots no longer increase the page height; scrolling upward
  reveals a Scroll to bottom control that returns smoothly to the latest line;
  refresh replaces the snapshot and keeps cluster/namespace/pod scope intact;
  and loading, empty, error, truncated, light, dark, desktop, and narrow-screen
  states remain clear and usable.

- [x] **Step 2: Add focused regression coverage and verify the UI.** Add or
  extend the smallest stable frontend tests for the log viewer's bounded
  behavior, refresh request, and scroll-to-bottom state where the existing test
  setup supports them, then run the project verification gates and inspect the
  real resource-detail flow in a browser.
  **Done when:** automated checks pass and browser evidence confirms the viewer
  stays bounded, starts at the newest log entry, respects manual scrolling,
  refreshes without duplication, and matches the visual quality of Audit Logs.

## Verify

- Run `./scripts/verify-feature.sh`.
- Run `cd k8s-ui && yarn lint` and `cd k8s-ui && yarn tsc --noEmit`.
- In the running app, open a Pod detail page and select **Logs** with a large log
  snapshot. Confirm the page does not grow with the log count, the viewer opens
  at the bottom, and the newest timestamp/line is visible.
- Scroll upward and confirm **Scroll to bottom** appears, is keyboard accessible,
  returns to the latest line, and does not pull the user down unexpectedly while
  they are reading older lines.
- Use **Refresh** and confirm the snapshot is replaced rather than appended,
  remains bounded, and preserves the selected cluster, namespace, pod, and
  container context.
- Check loading, empty, error, and truncated states in light and dark themes at
  desktop and narrow widths.
