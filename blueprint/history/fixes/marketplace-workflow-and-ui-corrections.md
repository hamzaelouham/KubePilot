# Marketplace workflow and UI corrections

**Type:** Fix
**Status:** verified
**Branch:** `fix/marketplace-workflow-and-ui-corrections`

## The problem

Marketplace release actions are not represented in installation history, leaving
stale Roll back and Uninstall controls after an action completes. The Marketplace
page and install dialog hold separate cluster-selection state. History is capped
at 100 server records, and FastAPI error messages are discarded by the frontend.
The package cards also lack the interaction and visual treatment established by
the supplied reference.

## The fix

Keep Marketplace cluster state in one page-level owner and pass it to the
installer. Show a release timeline in history and derive action availability
from the most recent job for each release. Add paginated history requests,
display the real total, and read API errors from both proxy and FastAPI shapes.
Polish package cards with the native rounded, focus, and hover treatment plus
available trust metadata.

## Build steps

1. [x] **Make the Marketplace context and package cards clearer.**
   - Share the selected cluster between the header and install dialog.
   - Add card affordance and concise trust metadata without weakening existing
     button or keyboard behavior.
   - **Done when:** opening an installer targets the header-selected cluster and
     cards visibly respond to keyboard focus and pointer hover.

2. [x] **Correct Marketplace history state and scale.**
   - Return and consume paginated installation history, with actionable release
     state derived from the latest related job.
   - Render release jobs in history and preserve useful FastAPI error messages.
   - **Done when:** older records remain reachable, completed uninstalls no
     longer expose stale actions, and release outcomes appear in history.

## Verification evidence

- `yarn lint` completed with pre-existing warnings only.
- `yarn tsc --noEmit` passed.
- Focused Marketplace backend tests passed (2 tests).
- `yarn verify` passed when run manually by the user on 2026-09-10.
