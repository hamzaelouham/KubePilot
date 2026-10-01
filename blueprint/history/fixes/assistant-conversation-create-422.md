# Current Feature

> **Generated file.** Holds the one feature, fix, or rollback being built right now. Run
> `/feature <number-or-name>` to spec a build-plan feature, or `/fix "<bug>"` for
> an ad-hoc fix. Use `/rollback <completed-feature>` to plan a safe reversal.
> Build one thing at a time; `/complete` archives it under `blueprint/history/` and resets this file.

# Assistant conversation creation returns 422

**Type:** Fix

**Status:** verified

**Branch:** `fix/assistant-conversation-create-422`

## The problem

Creating a persisted Assistant conversation from the browser with the selected
direct model or agent is rejected by `POST /api/assistant/conversations` with
`422` and the generic `Request validation failed` response. The browser and
FastAPI conversation contracts need a single validated payload shape, with a
regression test covering the non-null model/agent selection used by the UI.

## The fix

Align the conversation-create request contract with the payload emitted by the
Assistant UI, preserving strict mode/selection validation and owner/cluster
checks. Add focused backend and frontend coverage for a valid selected-model
create request and keep the existing null-selection and agent behavior intact.

## Build steps

1. [x] **Make selected conversation creation accept the UI payload**
   - Update the smallest affected request/proxy/schema surface and add focused
     regression coverage.
   - **Done when:** a valid browser-shaped POST with a selected model reaches
     conversation creation successfully, invalid selection combinations remain
     rejected, and focused checks pass.

## Verify

- Run the focused Assistant backend tests and `k8s-ui` Assistant tests.
- Run `./scripts/verify-feature.sh`.
- Reproduce from the Assistant UI and confirm `POST /api/assistant/conversations`
  returns `201` instead of `422`.
