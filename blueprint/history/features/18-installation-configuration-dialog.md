# Current Feature

**Status:** verified
**Type:** Feature
**Scope:** 18e — KubePilot Marketplace installation configuration dialog
**Branch:** `feature/installation-configuration-dialog`

## Goal

A reusable dialog that collects package, version, cluster, namespace, and release
name for a Marketplace installation, with client-side validation, and that does
**not** execute any Helm command or call an install API (build-plan **18e**). The
dialog reuses the existing cluster selection (`useClusterSelection`) and the
cluster-namespaces lookup the app shell already uses, and is opened from both the
package-card Install button and the 18d package-details Install button. Because
the UI must let the user pick a package version, this feature also adds the
backend + proxy plumbing that fetches a package's available versions from
Artifact Hub. The install POST, authorization policy, background Helm work, and
status UI stay in 18f-18k.

## In scope

1. **Backend versions endpoint** (new) - `GET /api/v1/marketplace/packages/{repository}/{package}/versions`
   in `backend/app/api/v1/marketplace.py`:
   - Auth: `Depends(get_current_actor)` (401 when unauthenticated), same as the
     existing `list_marketplace_packages`.
   - Upstream call to `https://artifacthub.io/api/v1/packages/helm/{repository}/{package}`
     (we pin Helm, kind=0) reusing the existing `_fetch_artifact_hub_search`
     seam (`httpx` `client.get`, 15 s timeout).
   - **URL safety:** validate both path segments against DNS-1123 label
     `^[a-z0-9]([-a-z0-9]*[a-z0-9])?$` with a max length of 63 before
     interpolating them into the upstream URL; violation returns 400
     `invalid_package_reference`. Guards the URL against traversal/injection.
   - Normalized response `MarketplaceVersionsResponse` (`extra="forbid"`):
     `{ package_id: str, name: str, repository_name: str, versions: list[str] }`,
     where `versions` are the string `version` values of the upstream
     `available_versions` list, excluding entries without a usable `version`,
     sorted most-recent-first (`ts` descending; tie-break by version string
     descending). No deprecated filtering here (release availability is an 18f/18g
     install-time decision).
   - Errors: 200 shape above; 401 unauthenticated; 400 `invalid_package_reference`;
     404 `marketplace_not_found` when Artifact Hub returns 404; 502
     `marketplace_upstream_error` on any other non-200, transport error, or
     unexpected/invalid payload shape with a stable message.
2. **Next.js proxy route** (new) -
   `k8s-ui/app/api/marketplace/packages/[repository]/[package]/versions/route.ts`
   forwarding the two path segments to the backend using the same
   `@/lib/backend` helpers as the existing `app/api/marketplace/packages/route.ts`
   (cookie from the incoming request; `503 backend_unavailable` on failure).
3. **Install dialog** (`k8s-ui/components/install-dialog.tsx`, new) - a controlled
   Base UI dialog (`ui/dialog`), opened only when an install target package is
   set, with a per-package form (form state keyed by `package_id` so it resets on
   open). Fields:
   - **Package** (read-only header): name + publisher line (reuse
     `publisherOf`).
   - **Version** - `ui/select`, populated from the new endpoint, sorted
     most-recent-first, defaulting to the first (latest) entry once loaded.
     Loading: select disabled with a placeholder. Error: inline message +
     Retry. Empty (`versions: []`): note that no versions are available and the
     submit stays disabled.
   - **Cluster** - `useClusterSelection()` (the existing hook: list from
     `/api/clusters`, active clusters only, stored selection honored) rendered
     with `ui/select`. No active clusters: disabled select + "No active
     clusters" note.
   - **Namespace** - `ui/select` populated from
     `withCluster("/api/cluster/namespaces", cluster)` exactly like the app
     shell does (dashboard-shell.tsx), refetched when the cluster changes.
     Loading: disabled + placeholder. Error: inline message + Retry. Empty:
     note + submit disabled.
   - **Release name** - `ui/input` with label
     `htmlFor="install-release-name"`, validated client-side as a Helm
     release name (k8s DNS-1123 label: `/^[a-z0-9]([-a-z0-9]*[a-z0-9])?$/`,
     max length 63). Validation feedback: inline error text under the field,
     `aria-invalid` on the input, and `aria-describedby` pointing at the error
     (live-region announced). Error renders only when the value is non-empty and
     invalid; empty is treated as required (submit disabled).
   - **Submit** (`Button` "Install" in `DialogFooter`): enabled only when a
     package is set, versions loaded, a version selected, a cluster and namespace
     selected, and the release name is non-empty and valid. In 18e the button
     performs no HTTP call or Helm action - 18f wires the POST
     (`/api/marketplace/install`); 18g executes Helm. The UI never executes Helm.
4. **Wiring** - open the install dialog from the package-card Install button
   (`onInstall` prop) and from the 18d details-dialog Install button (`onInstall`
   prop); the existing card overlay approach keeps them separate interactive
   elements. `marketplace-browser.tsx` owns `installTarget` state and mounts the
   dialog.

## Out of scope

- The install POST endpoint (`POST /api/marketplace/install`) - 18f.
- Cluster/namespace/release-name authorization policy, kube-system protection,
  backend validation, and safe Helm command construction - 18k; 18e is
  client-side UX validation only.
- Installation job model, background worker, status API, progress and history UI
  - 18g-18j.
- Persisting the collected values anywhere; the dialog is a transient form.
- Full package-detail fetching (long description, keywords, maintainers, README)
  - still out of scope (18d); this feature fetches only the versions list.

## Build loop

Follow `blueprint/config.json`: `stepReview: feature`, `checkpointCommits:
disabled` - one review packet after the small steps below, a single feature
commit at the end via `/complete`. Every step stays on branch
`feature/installation-configuration-dialog` (never master), ends green, and
carries an observable `Done when`. Backend steps run
`cd backend && .venv/bin/python3 -m pytest` (focused) and
`cd backend && python3 -m compileall -q app`; frontend steps run `yarn lint`
(0 errors) + `yarn build`. Stop on any P0/P1 finding; `/complete` archives and
squash-merges only with the user's explicit go-ahead.

## Build steps

- [x] 1. **Backend versions endpoint + tests.** Add `MarketplaceVersionsResponse`
  to `marketplace_schemas.py` and `get_package_versions` to `marketplace.py`
  (route, validation, seam reuse, upstream mapping/errors). Add focused tests to
  `backend/tests/test_marketplace.py` mirroring the existing seam-mocked style
  (auth 401, invalid name 400, upstream non-200 502, upstream 404 -> 404
  `marketplace_not_found`, happy path whitelisted + most-recent-first). `Done
  when`: the new focused pytest tests pass and `python3 -m compileall -q app` is
  clean.
- [x] 2. **Proxy route + install dialog opens from both Install buttons.** Add
  the `[repository]/[package]/versions` proxy route. Create `install-dialog.tsx`
  with the controlled dialog, package header, and a version `ui/select` driven by
  the endpoint (loading disabled state, error + Retry, empty note). Wire
  `onInstall` on `PackageCard` (opens the dialog) and on the 18d details dialog's
  Install button (via a new `onInstall` prop); mount the dialog from
  `marketplace-browser.tsx` via `installTarget` state. `Done when`: clicking
  either Install button opens the dialog showing the package, the version select
  loads from the API with a disabled loading state and Retry on failure, ESC/
  backdrop/close dismiss it, and `yarn lint` + `yarn build` pass.
- [x] 3. **Cluster, namespace, release-name validation + submit gating.** Add
  the cluster `ui/select` (reuse `useClusterSelection`, empty-cluster note), the
  namespace `ui/select` (refetch on cluster change, loading/error+Retry/empty
  handling), the release-name input with DNS-1123 validation and
  `aria-invalid`/`aria-describedby`/error-text feedback, and footer Submit
  gating (enabled only when everything required is present). `Done when`: with no
  cluster selected Submit stays disabled; switching clusters refetches
  namespaces and resets the selection; an invalid release name shows the error
  and disables Submit; a fully valid form enables Submit (which performs no
  request in 18e); and `yarn lint` + `yarn build` pass.
- [ ] 4. **Verify.** Run the declared Verify once: `cd backend &&
  .venv/bin/python3 -m pytest` (baseline 173 + the new endpoint tests) and
  `cd k8s-ui && yarn verify`. `Done when`: both commands pass.

## Files / areas

- `backend/app/api/v1/marketplace.py` - `get_package_versions` route + URL-safe
  segment validation, reusing `_fetch_artifact_hub_search` and `_upstream_error`.
- `backend/app/api/v1/marketplace_schemas.py` - `MarketplaceVersionsResponse`.
- `backend/tests/test_marketplace.py` - focused tests for `/versions`.
- `k8s-ui/app/api/marketplace/packages/[repository]/[package]/versions/route.ts` -
  new Next proxy route (cookie + 503 pattern from the existing marketplace route).
- `k8s-ui/components/install-dialog.tsx` - new dialog (version/cluster/namespace/
  release form + validation + gating).
- `k8s-ui/components/package-card.tsx` - `onInstall` prop on the card Install
  button.
- `k8s-ui/components/package-details-dialog.tsx` - `onInstall` prop, Install
  button opens the dialog.
- `k8s-ui/components/marketplace-browser.tsx` - `installTarget` state + dialog
  mount.
- Reused unchanged: `ui/dialog.tsx`, `ui/select.tsx`, `ui/input.tsx`,
  `lib/use-cluster-selection.ts` (cluster + `/api/clusters`),
  `lib/cluster-query.ts` (`withCluster` for `/api/cluster/namespaces`), and the
  `MarketplacePackage` types.

## Data / contracts

- New backend contract `GET /api/v1/marketplace/packages/{repository}/{package}/versions`
  returns `{ package_id, name, repository_name, versions }` with `versions`
  most-recent-first; request/response shapes and error codes are pinned in step 1
  so 18f reuses them. Both path segments must be DNS-1123 labels (400 otherwise)
  because they are interpolated into a fixed Artifact Hub URL.
- Cluster and namespace identity stay names (the existing selectors' units).
  18f's `cluster_id` (DB id) is that feature's responsibility to resolve from the
  selected cluster name; this spec does not add a new id plumbing.
- Collected values (package, version, cluster name, namespace, release name) are
  the future `POST /api/marketplace/install` input but are never sent anywhere in
  18e. No secrets, stored data, or external side effects.
- Namespaces fetch reuses the app shell's endpoint
  (`/api/cluster/namespaces?cluster=<name>`), so 18e adds no new backend surface
  for clusters or namespaces.
- The version list comes from Artifact Hub only; the dialog applies no
  deprecation filter (install-time availability checking is 18f/18g).
- All labels/values render as plain React text; the release-name regex and error
  copy are the only new validation rules, and they match Helm/k8s naming used by
  the eventual 18k backend validation.

## Testing

- Backend: `cd backend && .venv/bin/python3 -m pytest` - existing 173 tests plus
  the new `get_package_versions` tests (seam-mocked, no live network), and
  `cd backend && python3 -m compileall -q app`.
- Frontend: no test runner exists (opt-in per coding standards); verified by
  `yarn lint` (0 errors; the two `no-img-element` warnings remain the accepted
  baseline) and `yarn build`. Check step 3's release-name gating via the manual
  try path - it is pure client-side logic without a test runner.
- Manual try path: start backend + `yarn dev`, open `/marketplace`, click a card
  install button; choose version/cluster/namespace, clear/submit release name and
  watch errors; switch clusters and confirm the namespace list refetches; confirm
  Submit enables only on a fully valid form and performs no request in 18e.

## Notes for the AI

- Reuse the `_fetch_artifact_hub_search` seam name even though it predates the
  versions endpoint; tests patch it with `unittest.mock`, as the existing 12
  marketplace tests do. Do not rename it (namespace churn in tests).
- The dialog form resets per package by rendering its body with
  `key={pkg.package_id}` (the package-details dialog already uses this pattern);
  avoid synchronous `setState` in effect bodies (the React compiler flags it).
- Follow the existing controlled-dialog and Base UI Select usage from
  `clusters-management.tsx:365` and `dashboard-shell.tsx`; labels use native
  `htmlFor` as in the clusters form, not a `ui/label` component (none exists).
- Keep the two Install buttons (card, details dialog) as separate non-nested
  interactive elements, consistent with 18d's overlay-button card.
- The namespaces fetch should mirror `dashboard-shell.tsx`:
  `fetch(withCluster("/api/cluster/namespaces", cluster), { cache: "no-store" })`
  with a per-cluster AbortController.
- 18e's Submit click is a deliberate no-op; add a short note in the review
  handoff so the user knows 18f wires the POST, never invent a mock POST or fake
  success state.

## Open questions

None remaining - version source, cluster/namespace reuse, release-name rule,
and the 18f-boundary for submission are all resolved by repository evidence and
the plan text above.