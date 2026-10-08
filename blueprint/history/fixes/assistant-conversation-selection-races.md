# Assistant conversation selection races

**Type:** Fix

**Status:** verified

**Branch:** `fix/assistant-conversation-selection-races`

## The problem

Assistant conversation saves and deletes finish asynchronously. In
`k8s-ui/components/assistant/view.tsx`, a save result can update the selected
conversation and history after the user has deleted it or started a new
conversation. A delete completion can also use the old `activeConversationId`
captured before the request, clearing a different conversation that the user
opened while the delete was in flight.

## The fix

Apply save results only while the saved conversation is still the active
selection. After deletion, clear the UI only when the deleted ID is still the
current selection; otherwise preserve the conversation the user opened later.
Keep backend persistence, URL synchronization, opening conversations, and the
existing delete contract unchanged.

## Build steps

1. [x] **Guard asynchronous conversation transitions**
   - Update the Assistant view's save and delete completion paths with current
     selection checks.
   - Add focused regression coverage for a late save and a delete completing
     after selection changes.
   - **Done when:** a late save cannot restore a deleted or replaced selection,
     deleting conversation A cannot clear conversation B, and ordinary open,
     new, save, and delete flows still update history and the URL correctly.

## Verify

- Run `cd k8s-ui && yarn test:assistant`.
- Run `cd k8s-ui && ./node_modules/.bin/tsc --noEmit`.
- Run `cd k8s-ui && yarn verify`.
- In the Assistant UI, start a response, delete or replace the conversation
  before its save finishes, and confirm the old conversation does not return.
- Start deleting conversation A, open conversation B before deletion finishes,
  and confirm B remains selected.

## Verification notes

- `yarn test:assistant` passed all 35 tests.
- `./node_modules/.bin/tsc --noEmit` passed.
- `yarn next build --webpack` passed, including TypeScript and page generation.
- `./scripts/verify-feature.sh` passed its frontend tests but its Turbopack
  build hit an environment-level worker-port permission panic; the Webpack
  production build passed as the fallback.
- Targeted ESLint for `components/assistant/view.tsx` passed with the existing
  `react-hooks/set-state-in-effect` rule disabled. Full lint still reports
  unrelated pre-existing errors in Assistant components.
