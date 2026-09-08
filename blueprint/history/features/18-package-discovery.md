# Current Feature

**Status:** verified
**Type:** Feature
**Branch:** feature/marketplace-package-discovery

## Goal

Show real Helm packages on the Marketplace (build-plan **18b**): fetch the first
pages of Kubernetes Helm charts from Artifact Hub with a **Load More**
pagination control, render them as reusable `PackageCard`s (logo, name,
description, publisher/repository, latest version, Install button), and cover
loading skeletons, an empty state, and an API error state. No raw Artifact Hub
JSON is exposed, and only a bounded number of packages load at once.

## In scope

Discovery transport runs through the existing FastAPI backend (server-side
proxy), **not** browser-direct:

- **Why (surfaced from research, not an invented choice):** Artifact Hub only
  enables CORS for embed-widget endpoints; `/packages/search` does not
  reliably send `Access-Control-Allow-Origin: *` from browsers (confirmed in
  artifacthub/hub#3933 and #4586). The maintainers explicitly recommend a
  server-side proxy. The pasted brief's diagram put Artifact Hub under the
  frontend discovery module; CORS reality makes that impossible, so this spec
  places the Artifact Hub hop in FastAPI (the trusted server boundary), with
  the browser talking only to the same-origin Next proxy like every other
  backend call in the app.

- Backend: `backend/app/api/v1/marketplace.py` + `marketplace_schemas.py`,
  registered in `backend/app/main.py` under `/api/v1`:
  - `GET /api/v1/marketplace/packages` — requires a valid session
    (`Depends(get_current_actor)`; 401 otherwise, existing dependency).
  - Calls `https://artifacthub.io/api/v1/packages/search` with `httpx`
    (installed; `httpx>=0.27`) as `httpx.AsyncClient` with a 15s timeout,
    pinning `kind=0` (Helm charts only) and `deprecated=false`; forwards
    optional `limit`, `offset`, `ts_query_web`, and `sort` query params.
  - Returns a **normalized envelope** — never raw Artifact Hub JSON:
    `{ "packages": [...], "total": <int> }` where `total` comes from the
    upstream `Pagination-Total-Count` response header and each package is
    whitelisted to: `package_id`, `name`, `normalized_name`, `description`,
    `version`, `app_version`, `logo_image_id`, `stars`, `deprecated`, `official`,
    `signed`, `license`, `repository` (only `name`, `display_name`,
    `organization_name`, `organization_display_name`, `url`, `kind`). `facets`
    and unknown fields dropped.
  - Error mapping: non-2xx upstream or httpx failure → HTTP 502 with
    `{"code": "marketplace_upstream_error", "message": ...}`. Invalid
    `limit`/`offset` (non-integer, or limit outside 1-60) → 400
    `{"code": "invalid_pagination"}`.
  - A module-level `async def _fetch_artifact_hub_url(url)`/fetch seam that
    tests can patch (nondeterministic external call).
  - Backend tests (`backend/tests/test_marketplace.py`) mirroring the
    authenticated-endpoint pattern in `tests/test_cluster_management.py`
    (TestClient + valid session cookie), patching the fetch seam:
    normalization/whitelist, `kind=0` pinning, total-header handling, 401
    without session, 400 invalid pagination, and 502 upstream failure.
- Frontend Next proxy: `k8s-ui/app/api/marketplace/packages/route.ts` —
  GET only, forwards `limit`/`offset`/`ts_query_web`/`sort` query params to
  `/api/v1/marketplace/packages`, uses the helpers from `@/lib/backend`
  (`backendUrl`, `forwardedCookie`, `proxyResponse`), and returns 503
  `backend_unavailable` on fetch failure (the `app/api/users/route.ts` pattern).
- Frontend browser UI (extend the 18a page, keep the header):
  - `k8s-ui/components/marketplace-browser.tsx` — client component, fetch
    `GET /api/marketplace/packages?limit=24&offset=…` (AbortController +
    `cache: "no-store"` per repo view pattern). State machine: id → loading →
    ready → error; keeps `packages[]`, `total`, `offset`.
  - Initial load: skeletons (six `animate-pulse` rows, no Skeleton component
    exists). Empty first page → `Empty` + `EmptyHeader` + `EmptyTitle`
    ("No packages found") + `EmptyDescription` using the installed
    `components/ui/empty.tsx`. Error (non-OK response incl. 503, or network
    failure) → `Empty` error layout with a Retry button that refetches.
  - `Load more` (`Button` variant `secondary`): appends the next page; hidden
    when `packages.length >= total`; disabled + shows loading while fetching;
    a load-more failure surfaces the same error state (list kept, retry
    resumes from the current offset).
  - `k8s-ui/components/package-card.tsx` — reusable card: `rounded-xl border
    border-border bg-surface-elevated p-4 shadow-sm flex flex-col gap-3`;
    logo `<img src="https://artifacthub.io/image/<logo_image_id>">` (plain
    `img`, remote, `size-9 rounded-md`, hidden replaced by a muted
    placeholder block when `logo_image_id` is null or the image fails), name,
    `line-clamp-2` description, publisher/repository line
    (`repository.organization_display_name ?? repository.display_name ??
    repository.name`), "Latest version" row with the version, and an
    **Install** button (`Button`, `size="sm"`, `variant="default"`) that has
    no click handler in 18b — the Installation Dialog (18e) wires it.
  - Responsive grid: `grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4`.
  - Mount the browser below the existing page header in
    `components/marketplace-view.tsx`.
- No frontend test runner (none declared); frontend checks are build + lint.

## Out of scope

- Search input, debounce, explicit sort control (18c).
- Package detail view/drawer (18d) — cards are not clickable to details yet.
- Install dialog, install/status/history APIs or worker (18e-18l).
- Release management, upgrades, rollbacks, uninstalls (explicitly excluded).
- Any kubeconfig/Helm/backend cluster work; the proxy adds no DB writes, no
  new table, no categories/curation, no favorites, no caching beyond the
  browser.

## Build loop

- `workflow.stepReview: "feature"` → one review packet after all steps, no
  per-step approval pauses. `workflow.checkpointCommits: "disabled"` → no
  intermediate commits (verified off).
- Run the narrowest check per step (`pytest tests/test_marketplace.py`;
  `yarn lint` + `yarn build`); the exact declared Verify runs once in the
  final step.

## Build steps

^- [x] 1. **Backend Artifact Hub proxy + tests.** Add `marketplace_schemas.py`
  (normalized response models) and `marketplace.py` (`GET /packages`, session
  auth, pinned `kind=0`/`deprecated=false`, optional `limit`/`offset`/
  `ts_query_web`/`sort`, whitelist envelope + `total`, 400/401/502 mapping, 15s
  httpx timeout, patchable fetch seam), register the router in `main.py`, and
  add `tests/test_marketplace.py` (authenticated pattern; patched seam:
  success normalize, kind pinning, total, 401 no session, 400 bad pagination,
  502 upstream failure).
  **Done when:** `cd backend && .venv/bin/python3 -m pytest tests/test_marketplace.py`
  passes; `GET /api/v1/marketplace/packages` returns only normalized fields for
  an authenticated caller and 401 without a session.

^- [x] 2. **Next proxy route.** Add `app/api/marketplace/packages/route.ts`
  forwarding `limit`/`offset`/`ts_query_web`/`sort` to the backend with
  `@/lib/backend` helpers.
  **Done when:** `cd k8s-ui && yarn build` and `cd k8s-ui && yarn lint` pass;
  a live backend makes `GET /api/marketplace/packages` return the normalized
  payload and a stopped backend returns 503 `backend_unavailable`.

^- [x] 3. **Card grid + states.** Add `components/package-card.tsx` and
  `components/marketplace-browser.tsx`; mount under the Marketplace header in
  `marketplace-view.tsx`.
  **Done when:** `cd k8s-ui && yarn build` and `cd k8s-ui && yarn lint` pass;
  first load shows skeletons, then real package cards (logo/name/description/
  publisher/version/Install button); empty page shows the empty state; Load
  More appends the next page and hides at `total`; API/upstream failure shows
  the error state with a retry that resumes at the current offset.

- [x] 4. **Verify.** Run the exact declared Verify once.
  **Done when:** `cd backend && .venv/bin/python3 -m pytest` passes and
  `cd k8s-ui && yarn verify` passes (161 backend tests baseline + frontend
  build).

## Files / areas

- `backend/app/api/v1/marketplace.py` (new), `backend/app/api/v1/marketplace_schemas.py` (new),
  `backend/app/api/v1/__init__.py` (export), `backend/app/main.py` (register router),
  `backend/tests/test_marketplace.py` (new), `backend/requirements.txt` (already has httpx — no change).
- `k8s-ui/app/api/marketplace/packages/route.ts` (new).
- `k8s-ui/components/marketplace-browser.tsx` (new), `k8s-ui/components/package-card.tsx` (new),
  `k8s-ui/components/marketplace-view.tsx` (mount browser under header).
- No DB migration, no new UI dependency.

## Data / contracts

- `GET /api/v1/marketplace/packages` (backend, session-authenticated). Query:
  `kind` pinned to 0 regardless of input; `deprecated` pinned to `false`;
  optional `limit` (int, 1-60, default 24), `offset` (int ≥ 0, default 0),
  `ts_query_web` (string), `sort` (string). Response 200:
  `{"packages": MarketplacePackageSummary[], "total": int}` with the exact
  whitelisted field set above. Errors: 400 `invalid_pagination`, 401
  `authentication_required` (existing), 502 `marketplace_upstream_error`.
- Same-origin proxy preserves query params + session cookie; client reads only
  `packages` and `total`.
- No stored data; external-source rules deferred to 18k (this feature never
  evaluates Artifact Hub content; it only renders whitelisted strings/images
  through React escaping).

## Testing

- Backend: focused pytest in step 1 (auth, normalization contract, error
  mapping, sealed fetch seam); full suite in step 4.
- Frontend: no test runner configured — `yarn lint` (0 errors baseline; 17
  pre-existing warnings) and `yarn build` are the checks. No browser harness
  (opt-in `/browser-tests` not configured).
- No live/visual claims: done-whens are build/lint + code-observable states;
  the manual try path verifies against a live backend and network.

## Notes for the AI

- The frontend Next proxy route must forward the incoming query params the
  client sends, not hardcode them; mirror `app/api/users/route.ts` helper
  usage. The backend controls the `kind`/`deprecated` pins (contract lives
  server-side).
- `logo_image_id` URL pattern is `https://artifacthub.io/image/<logo_image_id>`:
  confirm it still serves at implementation time; if the remote image 404s,
  the card still renders with the placeholder (onError fallback). Use a plain
  `<img>` (no next/image remote-pattern config needed).
- Tailwind v4 ships `line-clamp-2`, `animate-pulse`, and the full grid/size
  utilities; the app has no `card.tsx`/`skeleton.tsx` components, so card and
  skeleton are Tailwind divs matching the shell's `border-border
  bg-surface-elevated` visual language.
- Keep the 18a page header intact; the browser goes below it.
- The Install button renders enabled but with no onClick in 18b — 18e provides
  the dialog. Do not invent a click behavior.

## Open questions

- **Transport deviation (decided, flagged):** discovery is proxied through
  FastAPI rather than browser-direct because Artifact Hub intentionally
  disallows browser CORS on `/packages/search` (maintainer-confirmed).
  Review this decision; the backend proxy is the only workable routing given
  the API contract.
- Default ordering for the empty initial listing (Artifact Hub default
  relevance, no query) is used for 18b; search + sort controls arrive in 18c.
- Deprecated charts are excluded by default (`deprecated=false`) — revisit in
  18c if the product wants a toggle.
- Rate limits (429) from Artifact Hub surface as the generic upstream error in
  18b; retry policy and caching are out of scope.