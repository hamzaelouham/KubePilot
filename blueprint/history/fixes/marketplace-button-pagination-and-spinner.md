# Fix — Marketplace button pagination with loading spinner

**Type:** Fix
**Status:** verified
**Branch:** fix/marketplace-button-pagination-and-spinner

### The problem

The Marketplace package grid paginated with a single **"Load more"** button
(`k8s-ui/components/marketplace-browser.tsx`) that appended a second batch of
`PAGE_SIZE = 24` cards. The user wanted classic **numbered button pagination** with
**12 cards per page** (approved at 9 in the spec; changed to 12 by explicit user
decision during completion), and a **loading spinner** instead of the skeleton grid.

### The fix

Reworked `k8s-ui/components/marketplace-browser.tsx` (client component; no
backend or manifest change — `/api/marketplace/packages?limit&offset` already
returns `total`):

- `PAGE_SIZE` changed 24 → `12`.
- Replaced the load-more append flow (`loadingMore`, `offsetRef`, `loadMore`,
  `showLoadMore`) with a `page` state; each page change replaces the grid with
  the requested offset (`offset = page * PAGE_SIZE`), and the page resets to 0
  when search or sort changes (via the debounce callback and sort handler, not a
  synchronous effect — keeps the react-hooks lint rule clean).
- A centered **Spinner** (same SVG pattern as `install-dialog.tsx`, `role="status"`)
  shows during any full-grid load; `SkeletonGrid` was removed.
- Added a pagination bar (Previous / numbered page buttons with `…` gaps when
  many pages / Next) below the grid, disabled while loading, hidden on a single
  page; `aria-current="page"` marks the active page.
- Preserved: abort of stale requests (`AbortController`), search debounce
  (350ms), sort reset, `cachedFetch`, the empty error state with Retry, and the
  in-grid error banner with Retry (wording updated to "Unable to load packages.").
- Button variants/sizes use the existing `ui/button` tokens (`default`, `outline`,
  `sm`).

### Build steps

**Step 1 — Button pagination + spinner in `marketplace-browser.tsx`.**
- [x] Done: `PAGE_SIZE = 12` (approved as 9 in the spec; final value 12 per the
  user's explicit decision); numbered pagination with Prev/Next and `…` gaps;
  spinner replaces `SkeletonGrid`; page resets to 1 on search/sort change;
  `yarn lint` 0 errors (19 pre-existing warnings elsewhere);
  `yarn verify` (build) passes.

**Step 2 — Whole Verify.**
- [x] Done: backend `pytest` **210 passed**; `k8s-ui yarn verify` (next build) passes.
  Exact `Verify` rerun at completion after the safety pass.

### Verify

- `cd k8s-ui && yarn verify` (build) — passed.
- `cd k8s-ui && yarn lint` — 0 errors.
- Live: open the Marketplace, confirm exactly 12 package cards per page, navigate
  with Previous/Next and page numbers (spinner shows between pages, no skeleton).
- The frontend has no test runner; verification is the build, lint, and the
  manual marketplace interaction.

### Notes

- Frontend-only; `cachedFetch` already caches `packages` requests regardless of
  `limit`/`offset`.
- The react-hooks lint rule blocks synchronous `setState` in effects, so page
  reset on search/sort lives in the debounce callback and sort handler.
- `PAGE_SIZE` was 9 in the approved spec and 12 in the merged fix — the change
  was the user's explicit in-chat decision during `/complete`, recorded here.