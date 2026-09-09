# Marketplace release-action toast-only feedback

**Type:** Fix
**Status:** in progress
**Branch:** `fix/marketplace-release-action-toast-only-feedback`

## The problem

Marketplace Installation History is intended to show package installation jobs and their lifecycle states: queued, running, succeeded, failed, and cancelled. When a user starts an uninstall or rollback from a history row, the release-action job completes successfully but is also added to Installation History. This makes completed release actions look like installation records and creates misleading, cluttered history.

## The fix

Keep rollback and uninstall actions and their backend execution intact, but treat their results as transient UI feedback. On successful rollback or uninstall, show a success toast using the project's shadcn/ui toast components and remove or avoid rendering that action's job in Installation History. Preserve existing installation job visibility, status rendering, error feedback, permissions, and refresh behavior.

## Build steps

1. [x] Update the Marketplace release-action and history UI flow so completed rollback and uninstall jobs are communicated through shadcn/ui toast components and are not displayed as Installation History entries.
   - **Done when:** Clicking **Rollback** or **Uninstall** executes the existing action; a successful result is shown in a shadcn/ui toast, while no rollback or uninstall job appears in Installation History.

## Verify

- Open Marketplace Installation History and confirm install jobs still show their normal queued, running, succeeded, failed, or cancelled statuses.
- Roll back and uninstall Marketplace releases; confirm each successful action appears as a toast only, with no rollback or uninstall row left in Installation History.
- Confirm failed rollback and uninstall attempts still provide clear user-facing error feedback and do not regress the action controls.
