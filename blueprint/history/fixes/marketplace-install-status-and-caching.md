# Marketplace install status 404 + frontend API caching

> **Type:** Fix
> **Status:** verified
> **Branch:** `fix/marketplace-install-status-and-caching`

## The problem

Two related issues in the Marketplace feature:

1. **Installation status polling returns HTML instead of JSON.** After
   submitting a Helm install, the `JobProgress` component
   (`k8s-ui/components/install-dialog.tsx`) polls
   `GET /api/marketplace/installations/${jobId}` for status. No Next.js proxy
   route existed at that path. Next.js returned its HTML 404 page, which
   `response.json()` cannot parse, producing
   `Unexpected token '<', "<!DOCTYPE "... is not valid JSON`.
2. **Every marketplace fetch hit the backend with no caching.** All marketplace
   `fetch()` calls used `cache: "no-store"` with no deduplication layer.
   Navigating between marketplace views, switching tabs, or re-rendering
   re-fetched identical data from the backend unnecessarily.

## The fix

**Part A — Add the missing installations proxy route.**

Create `k8s-ui/app/api/marketplace/installations/[job_id]/route.ts` following
the same pattern as the existing proxy routes (`packages/route.ts`,
`versions/route.ts`). It proxies
`GET /api/v1/marketplace/installations/{job_id}` to the backend, forwarding the
session cookie.

**Part B — Add a lightweight client-side cache for marketplace GET requests.**

Add `k8s-ui/lib/marketplace-cache.ts` exporting `cachedFetch` and
`invalidateCache`:
- Stores responses keyed by full URL string.
- Applies a configurable TTL (default 30 seconds) — returns cached data if still
  fresh; preserves each caller's `signal` for abort support.
- `invalidateCache(pattern?)` clears entries by URL prefix or all.
- Used by `marketplace-browser.tsx` (package search) and `install-dialog.tsx`
  (versions, namespaces). The installation status polling in `JobProgress` is
  intentionally **not** cached — it must always reflect live state.

## Build steps

- **Step 1 — Create the missing installations proxy route.**
  `k8s-ui/app/api/marketplace/installations/[job_id]/route.ts`, matching the
  existing proxy pattern (extract `job_id`, build target URL, forward cookie,
  proxy response).
  Done when: file exists, follows the existing proxy pattern, the build passes.
  **Status: done** (`yarn verify` builds; the new route is registered in the
  build output).
- **Step 2 — Add `lib/marketplace-cache.ts` and integrate into marketplace GET
  fetches.** Cache package search, versions, and namespaces; invalidate package
  entries after a successful install submit.
  Done when: package search, versions, and namespaces use cached fetch; install
  submit invalidates the cache; build passes.
  **Status: done** (`yarn verify` builds, `yarn lint` 0 errors).

## Verify

- `cd backend && .venv/bin/python3 -m pytest`
- `cd k8s-ui && yarn verify`
- Live (`/marketplace`): open a package install dialog twice quickly — the
  second open serves versions from cache (no new network request within the 30s
  TTL). Submit an install — status polling hits the new proxy route and returns
  JSON (not an HTML 404).

## Verification evidence

- `cd backend && .venv/bin/python3 -m pytest` → **210 passed**.
- `cd k8s-ui && yarn verify` (`next build`) → builds clean; new route
  `/api/marketplace/installations/[job_id]` registered; `yarn lint` → 0 errors
  (19 pre-existing warnings, none in changed files).
- Ledgers `findings.md` / `review.md`: clean canonical stubs (no P0/P1).
