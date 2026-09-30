# AI Agents progressive-disclosure management UI

**Type:** Fix
**Status:** verified
**Branch:** `fix/ai-agents-progressive-disclosure-ui`

## The problem

The authenticated AI Agents management page exposed too many configuration areas
in one vertically long surface, making agent identity, capabilities,
automation, notifications, and activity difficult to scan.

## The fix

- Made AI Assistant an expandable sidebar parent with Group chat and AI agents
  child navigation.
- Added a compact selected-agent header, metadata, actions, and progressive
  disclosure tabs for Overview, Tools, Skills, Automation, Notifications, and
  Activity.
- Added an activity/run-history table and same-origin API bridge for existing
  agent run data.
- Preserved existing agent APIs, permissions, execution, automation,
  notification, save, delete, and responsive library behavior.

## Verification

- `./scripts/verify-feature.sh` passed.
- 29 Assistant tests passed.
- Next.js production build and TypeScript compilation passed.
- Changed-file lint passed; unrelated existing lint errors remain outside the
  changed surface.
- `graphify update .` completed.

## How to try it

1. Start the frontend with `yarn dev` from `k8s-ui/`.
2. Open `/assistant/agents` and expand/collapse AI Assistant in the sidebar.
3. Select an agent and inspect each configuration tab, including Activity.
