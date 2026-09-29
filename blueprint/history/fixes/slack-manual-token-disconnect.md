# Current Fix

## Title

Allow Slack manual-token reconnect after disconnect

## Type

Fix

## Status

Verified

## Branch

`fix/slack-manual-token-disconnect`

## The problem

Disconnecting a Slack connection always calls Slack `auth.revoke` for the
connection token. When the connection was created from the administrator's
manually configured Bot User OAuth Token, this revokes the externally managed
token. A later Connect attempt reuses that token and fails because Slack has
already invalidated it.

## The fix

Identify when the stored Slack connection token matches the configured manual
Bot User OAuth Token. For that manual-token connection, clear KubePilot's local
encrypted connection state without calling the provider revoke API. Preserve
the existing external revoke behavior for OAuth-managed connections. Keep the
credential write-only and unchanged so the same manual token can reconnect.

## Build steps

1. [x] Update the integration disconnect service and add a regression test for
   manual Slack disconnect followed by reconnect. Done when the manual token is
   not revoked externally, local connection state is cleared, and reconnecting
   with the same token succeeds; OAuth disconnect still revokes its provider
   token.

## Verify

- Run focused integration tests covering manual disconnect/reconnect and OAuth
  disconnect behavior.
- Run `./scripts/verify-feature.sh`.
