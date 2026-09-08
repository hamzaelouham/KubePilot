# Current Feature

**Status:** verified
**Type:** Feature
**Branch:** feature/package-search-and-filtering

## Goal

Add search and sorting to the Marketplace package browser (build-plan **18c**):
a debounced search input wired to Artifact Hub's `ts_query_web` parameter and a
sort control offering Relevance (default) and Most stars. Both controls reset
pagination, and the existing skeletons / empty / error / Load More states from
18b keep working with the active term and sort. No backend or proxy changes.

## In scope

Frontend-only, confined to `k8s-ui/components/marketplace-browser.tsx` (18b's
browser) plus its own state:

- **Search input** — reusable `Input` from `@/components/ui/input`. Visible
  label via a native `<label htmlFor="marketplace-packages-search">Search
  packages</label>` (the repo has no `ui/label` component; `htmlFor` + `id`
  association is repo-native), input `id="marketplace-packages-search"`,
  placeholder "Search packages…". The typed value is trimmed and debounced by
  350 ms; an empty trimmed query sends no `ts_query_web` (default listing).
- **Sort control** — `Select` composable from `@/components/ui/select` (the
  `Select`/`SelectTrigger`/`SelectValue`/`SelectContent`/`SelectItem` pattern
  already used in `users-management.tsx`). Two options:
  - "Relevance" (value `relevance`) → send no `sort` param (Artifact Hub
    default, including its documented tiebreakers).
  - "Most stars" (value `stars`) → send `sort=stars`.
  - `aria-label="Sort packages"` on the `SelectTrigger` for keyboard
    accessibility.
- **Refetch plumbing** — on a debounced query change or a sort change: abort
  the in-flight request (existing `AbortController` per request), reset
  `offsetRef` to 0, replace the list (never append), and show the 18b skeleton
  grid. After the response, ready / empty / error rendering is exactly 18b's.
- **Pagination continuity** — Load More keeps sending the active trimmed query
  and sort and appends to the current list; it stops when `packages.length >=
  total` as in 18b.
- **States preserved from 18b** — initial/loading skeletons, empty state ("No
  packages found" — now reachable in practice via a zero-result search), the
  full-page error state with Retry, and the post-load-more error banner. Retry
  refetches the current query + sort at the current offset. PackageCard is
  untouched.
- **Race safety** — every new request is issued by an async fetcher that first
  aborts the previous controller; the component only applies the response of
  the request it last started (sequence guard by abort, matching the 18b
  pattern).

## Out of scope

- Facets and extra filters (verified publisher, official, CNCF, operators,
  package category, deprecated toggle). The Artifact Hub API exposes them, but
  the build-plan line scopes 18c to search + optional sort; filters stay for a
  later slice.
- Package details (18d), install dialog (18e) and everything downstream.
- URL-query syncing of `q`/`sort` for shareable marketplace links — 18c keeps
  the controls in component state (the `/marketplace` page has no query-param
  contract yet). Deferred to 18l surface work if wanted.
- Backend, proxy route, PackageCard changes, new dependencies.

## Build loop

- `workflow.stepReview: "feature"` → one review packet after all steps, no
  per-step approval pauses. `workflow.checkpointCommits: "disabled"` → no
  intermediate commits.
- Narrowest check per step: `cd k8s-ui && yarn lint` (0 errors; 18 warnings
  baseline including the 18b `no-img-element` item) and `cd k8s-ui && yarn
  build`. The exact declared Verify runs once in the final step.

## Build steps

- [x] 1. **Search field + debounced refetch.** Extend `marketplace-browser.tsx`:
  state `query` (raw input) and `debouncedQuery` (350 ms `setTimeout` in an
  effect, cleared on change), a labeled `Input`, and a `fetchPage` that builds
  `URLSearchParams` with `limit`/`offset` plus `ts_query_web` when the trimmed
  term is non-empty. Changing the debounced term aborts the in-flight fetch,
  resets `offsetRef` to 0, replaces the list, and re-shows the skeleton grid.
  **Done when:** `yarn lint` and `yarn build` pass; typing then pausing
  triggers exactly one new request carrying `ts_query_web`; clearing the field
  reverts to the default listing; zero-result terms render the empty state.

- [x] 2. **Sort control + pagination/race/a11y finish.** Add the sort
  `Select` (Relevance / Most stars) with `aria-label="Sort packages"` on the
  trigger; send `sort=stars` only for Most stars. Load More appends with the
  current term + sort and hides at `total`; Retry (both error layouts) refetches
  the current term + sort at the current offset. Confirm every request is
  preceded by aborting the prior one and that term/sort changes always replace
  rather than append.
  **Done when:** `yarn lint` and `yarn build` pass; changing the sort issues a
  fresh request carrying `sort=stars` (and none for Relevance) and resets the
  list; Load More keeps the active term/sort; the input is reachable by label
  and the sort control by `aria-label`.

- [x] 3. **Verify.** Run the declared Verify once.
  **Done when:** `cd backend && .venv/bin/python3 -m pytest` passes and
  `cd k8s-ui && yarn verify` passes (173 backend tests baseline; no backend
  changes expected).

## Files / areas

- `k8s-ui/components/marketplace-browser.tsx` — the only product file.
- Reference: `k8s-ui/app/api/marketplace/packages/route.ts` (already forwards
  `ts_query_web`/`sort`, unchanged), `backend/app/api/v1/marketplace.py`
  (already passes both through to Artifact Hub, unchanged),
  `k8s-ui/components/package-card.tsx` (unchanged),
  `k8s-ui/components/ui/select.tsx` + `input.tsx` (installed).
- No tests-resources, migration, or dependency changes.

## Data / contracts

- Frontend → proxy: `GET /api/marketplace/packages?limit=24&offset=N` with
  optional `ts_query_web=<encoded trimmed term>` and `sort=stars` (omitted for
  Relevance). Proxy and backend pass these through already (implemented in 18b,
  verified by `test_marketplace.py::test_forwards_limit_offset_search_and_sort`
  and `test_pins_kind_and_deprecated`).
- Artifact Hub contract (confirmed from the public API docs and
  `artifacthub/hub#1080`): `ts_query_web` is free-text search; `sort` accepts
  `relevance` (default) and `stars` — the only two values offered. Pagination
  stays `limit`/`offset` + `Pagination-Total-Count` (already normalized
  server-side to `total`).
- Response envelope unchanged from 18b; `kind=0` and `deprecated=false`
  remain pinned server-side.

## Testing

- Frontend: no test runner configured (coding standards confirm testing is
  opt-in; there is no `Browser tests` command). Checks are `yarn lint` (0
  errors) and `yarn build`; observable behavior is validated via the running
  app in the manual try path, not claimed from build output.
- Backend: no changes; the existing `test_marketplace.py` parametric
  passthrough test already covers `ts_query_web`/`sort` forwarding.
- Full declared Verify in the last step.

## Notes for the AI

- Keep `fetchPage` and the state machine from 18b; only widen the request
  builder to accept `{ offset, query, sort }` and build the search params with
  `URLSearchParams` (append only when non-empty).
- Debounce is a plain `useEffect` + `setTimeout` cleared on dependency change
  (no dependency, no new library). On debounced change: abort current request,
  `offsetRef.current = 0`, replace — this must not toggle Load More state into
  an append.
- The React compiler will flag synchronous `setState` inside effects (18b hit
  this); route state transitions through the request handlers and the
  deferred-invocation effect pattern already in the component.
- Do not add a clear (×) button in this slice; clearing the field with
  backspace reverts to the default listing after debounce.
- No URL parameter syncing, no facets, no new sort values beyond
  `relevance`/`stars`.

## Open questions

- **Scope read of "search & filtering" (flagged for review):** this slice
  includes the search input + relevance/stars sort only. Facets such as
  verified/official/CNCF and a deprecated toggle are excluded and deferred to a
  later marketplace slice; say so if the plan intended them here.
- Debounce latency (350 ms), client-only query state, and omitting the URL
  params are internal choices with no user-visible, security, persisted-data,
  or interoperability impact; they are recorded above rather than gated.