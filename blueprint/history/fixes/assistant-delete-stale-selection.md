# Assistant delete retains stale conversation selection

**Type:** Fix

**Status:** verified

**Branch:** `fix/assistant-delete-stale-selection`

## The problem

Deleting a selected Assistant conversation succeeds in the backend with `204 No Content`,
and the record is removed. The mounted Assistant page still holds
the original `conversationId` prop from the server-rendered URL, however. The
delete/new-conversation flow updates the address bar with `window.history.replaceState`
but does not update the state consumed by the conversation-loading effect.

When that effect reruns after a selection refresh or other dependency change,
it requests the deleted UUID again and receives `404 Not Found`. The UI can
therefore show a stale selected-conversation error or appear as though delete
did not work. Minikube evidence for UUID
`85f30017-a6ab-4c1c-83c4-b1428e0610bb` confirms the sequence: `DELETE` → `204`,
then later `GET` → `404`.

## The fix

Make the active Assistant conversation ID a local client-state source of truth
for loading and selection transitions. Clear it when deleting the selected
conversation or starting a new one, and update it when opening or creating a
conversation. Keep the URL synchronized with that state without changing the
backend delete contract, ownership checks, persistence behavior, or automatic
creation of a fresh conversation after starting new.

## Build steps

1. [x] **Synchronize Assistant conversation selection state**
   - Update `AssistantView` so the conversation-loading effect cannot reuse the
     stale server prop after delete/new-conversation transitions.
   - Preserve direct URL restore, history-item opening, selected conversation
     deletion, new conversation creation, and model/agent/context selection.
   - Add or extend focused frontend coverage for the stale-ID transition where
     practical.
   - **Done when:** after deleting the selected conversation, the old UUID is
     removed from client selection and URL state, no later `GET` is issued for
     that UUID, the deleted row stays absent, and opening another conversation
     or starting a new one still works.

## Verification notes

- `yarn test:assistant` passed.
- `./node_modules/.bin/tsc --noEmit` passed.
- `yarn verify` passed: Next.js production build, TypeScript, page-data
  collection, and static-page generation all completed successfully.

## Verify

- Run `cd k8s-ui && yarn test:assistant`.
- Run the frontend production verification command used by the project,
  `cd k8s-ui && yarn verify`.
- Manually delete a selected conversation in the Minikube UI and confirm:
  - the DELETE remains `204`;
  - the deleted UUID is absent from the conversation list;
  - no subsequent GET for that UUID appears in backend logs;
  - a new conversation can be created and another saved conversation can be
    opened normally.
