# Fix: Assistant origin validation behind forwarded ports

**Type:** Fix
**Status:** verified
**Branch:** `fix/assistant-origin-validation-behind-forwarded-ports`

## The problem

The Assistant rejected a legitimate same-origin `POST /api/assistant` with
`403 invalid_origin` when KubePilot was opened through a Minikube-forwarded
port. The browser sent matching `Origin` and `Host` authorities, such as
`127.0.0.1:37047`, but `sameOrigin()` compared that origin with
`new URL(request.url).origin`, which could contain the frontend's internal
authority and port (`3000`) after proxying.

## The fix

Updated the shared Assistant origin guard to reconstruct the browser-facing
origin from the validated `Host` header and the request URL's `http`/`https`
scheme, then compare normalized URL origins. The existing `403 invalid_origin`
contract and guard ordering remain unchanged. No wildcard origins or arbitrary
forwarded-host/protocol values are trusted.

## Build steps

### 1. [x] Validate Assistant origins against the browser-facing authority

Updated `sameOrigin()` and focused Assistant tests for direct, forwarded-port,
missing, malformed, ambiguous, and cross-origin requests.

Done when:

- Matching browser-visible `Origin` and Minikube-exposed `Host` pass even when
  the internal request URL uses port `3000`.
- Invalid origin/host metadata still fails with `403 invalid_origin` before
  authentication or provider access.
- Existing Assistant behavior remains unchanged.

## Verify

- `./scripts/verify-feature.sh` passed: all 11 Assistant tests passed and the
  Turbopack production build completed successfully.
- `git diff --check` passed.
