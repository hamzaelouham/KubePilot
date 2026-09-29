# Manual Slack Bot Token for private deployments

**Type:** Fix

**Status:** verified

**Branch:** `fix/manual-slack-bot-token`

## The problem

KubePilot's Slack connection flow currently requires OAuth Client ID/Secret
credentials and a browser callback URL. That is a poor fit for an on-premise
installation that is intentionally not publicly exposed, especially when an
administrator has already installed a Slack app manually in one workspace and
has its `xoxb-...` Bot User OAuth Token. The Settings UI has no safe way to use
that token, so Connect reaches the OAuth path and fails when
`KUBEPILOT_PUBLIC_URL` is unavailable.

## The fix

Add an admin-only, write-only `integration.slack.bot_token` credential and a
manual Slack connection path. When that credential is configured, the Slack
Integrations card uses the manual path to validate the token with Slack,
identify the workspace, encrypt the token into the existing
`IntegrationConnection`, and return only safe connection metadata. Keep the
existing OAuth path unchanged and use it when no manual Bot Token is present.

The token must never appear in API responses, logs, audit context, browser
state, or client bundles. No database migration is needed because the existing
registered credential and encrypted connection storage are reused. Delivery
continues through the existing worker and Slack `chat.postMessage` adapter.

## Build steps

- [x] **1. Add manual Slack token configuration and connection.** Register the
  write-only Bot Token credential, expose safe metadata indicating manual Slack
  credentials are available, add a protected same-origin/manual-connect route,
  validate and persist the token through the existing Slack adapter and
  encrypted connection boundary, and update the Settings UI to choose manual
  connect for Slack while retaining OAuth fallback.

  **Done when:** an administrator can save a `xoxb-...` token under Settings
  Credentials and connect Slack without `KUBEPILOT_PUBLIC_URL`; invalid or
  revoked tokens fail safely without mutation; successful connection shows only
  workspace/status metadata; OAuth still works when no Bot Token is configured;
  delivery uses the connected token; focused backend tests, frontend lint, and
  the production Verify command pass.

## Verify

- Focused backend tests for credential registration, manual connection success,
  invalid-token failure, permission boundaries, redaction, and OAuth fallback.
- `yarn lint` and `./scripts/verify-feature.sh`.
- Confirm the Settings flow manually when a Slack Bot Token and Slack workspace
  are available; no public callback or inbound Slack endpoint should be needed.
- Evidence: 36 focused integration/credential/delivery tests passed during
  implementation; the final Verify passed 21 focused backend tests, 13
  Assistant tests, and the production build with 45 generated routes. Full
  `yarn lint` passed with 0 errors and 13 pre-existing warnings. Manual live
  Slack verification was not run because no Slack token or running app was
  available in this environment.

## Notes

- This is an unplanned on-prem compatibility fix and is not a new build-plan
  item.
- Manual Slack delivery still requires outbound HTTPS access from KubePilot to
  Slack APIs; fully air-gapped delivery remains unsupported.
