# Current Feature

**Status:** verified
**Type:** Feature
**Scope:** 18d — KubePilot Marketplace package details

## Goal

Show a lightweight details view for a Marketplace package (build-plan **18d**):
a modal dialog opened by clicking a package card, displaying name, logo,
description, publisher, repository, version, Helm install info, and an Install
button. Read-only: the Install configuration dialog and any execution are 18e
and later. Pure frontend; the 18b backend proxy, search envelope, filtering,
pagination, and Install-button behavior are untouched.

## In scope

1. **Clickable package cards** - clicking a `PackageCard` opens the details
   dialog, keyboard accessible. The card is covered by a transparent overlay
   `<button>` (`aria-label` naming the package, base styling with a
   focus-visible ring), so the card itself is not an interactive element. The
   card's existing Install button stays a separate interactive element layered
   above the overlay, with its 18b behavior (rendered, no click handler; 18e
   wires it).
2. **Details dialog (`ui/dialog`, Base UI)** - the repository-native modal the
   app already uses in clusters/users management: controlled `<Dialog open
   onOpenChange>`, `DialogContent`, `DialogTitle`, `DialogDescription`, close
   button, ESC and backdrop dismissal, focus trap. View style decided: **modal
   dialog** (the plan line permits drawer/modal/dedicated view; `ui/` has no
   drawer/sheet and no new route is added).
3. **Fields shown** - all from the already-loaded `MarketplacePackage` (no new
   fetch or API call):
   - logo via the existing `packageLogo` URL with the card's onError
     placeholder pattern
   - name as `DialogTitle`
   - publisher (`organization_display_name` ?? `display_name` ?? `name` ??
     `"Unknown publisher"`)
   - repository name, plus version and app_version (version ?? `"—"`)
   - stars and license (row hidden when absent)
   - official / signed badges (`ui/badge`) when true, and a deprecated note when
     `deprecated`
   - description with `"No description provided."` fallback
   - **Helm install info** - a read-only command block:
     `helm repo add <repository.name> <repository.url>` (line shown only when
     both exist) and `helm install <placeholder-release> <repository.name>/<package.name>`.
     Purely informational; never executed client-side.
   - Install button in `DialogFooter` (default outline, no click handler in 18d).
4. **Scrollable body** - the dialog body caps content height
   (`max-h-[60vh] overflow-y-auto`) so long descriptions never overflow the
   viewport.

## Out of scope

- Fetching the full Artifact Hub package-detail resource (long description,
  keywords, maintainers, README) - that needs a new API endpoint; 18d renders
  the short description already present in the 18b search envelope, which
  satisfies the plan line.
- Install configuration dialog (18e), installation APIs (18f-18h), progress and
  history UI (18i/18j), security & validation policy (18k), UI polish (18l).
- Copy-to-clipboard affordance and shareable/URL-linked details; a drawer or
  dedicated `/marketplace/<slug>` route.
- Any backend, proxy route, search/filter, or pagination change.

## Build loop

Follow `blueprint/config.json`: `stepReview: feature`, `checkpointCommits:
disabled` - one review packet after the small steps below, a single feature
commit at the end via `/complete`. Every step stays on branch
`feature/package-details` (never master), runs `yarn lint` (0 errors) and `yarn
build`, and ends with its observable `Done when`. Stop on any P0/P1 finding
rather than hiding scope; `/complete` archives and squash-merges only with the
user's explicit go-ahead.

## Build steps

- [x] 1. **Clickable card -> details dialog shell.** In `package-card.tsx`,
  place the card content in a relative container and add a transparent overlay
  `<button>` (`absolute inset-0`, `rounded-xl`, `aria-label="View details for
  <pkg.name>"`, focus-visible ring); the existing Install button keeps a higher
  z-index and its 18b behavior so the two are never nested. In
  `marketplace-browser.tsx`, add `selectedPackage` state, pass an `onSelect`
  callback to each card, and create `package-details-dialog.tsx` rendering
  `<Dialog open={selectedPackage !== null}>` with `DialogTitle` (name), close
  button, and the Install footer button (no handler). `Done when`: clicking a
  card opens the dialog, ESC/backdrop/close dismiss it, TAB reaches the card
  with a visible focus ring, and `yarn lint` + `yarn build` pass.
- [x] 2. **Full details content + accessibility finish.** Fill the dialog body
  with logo, publisher, repository, version/app_version, stars, license,
  official/signed badges, deprecated note, description fallback, and the Helm
  install command block (repo add line only when name+url exist; install line
  uses the `<repo>/<name>` chart ref) inside a `max-h-[60vh] overflow-y-auto`
  region. `Done when`: every field renders with its hide-or-fallback rule, long
  descriptions scroll and nothing clips on a small viewport, the Install button
  is present and inert, and `yarn lint` + `yarn build` pass.
- [x] 3. **Verify.** Run the declared Verify once: `cd backend &&
  .venv/bin/python3 -m pytest` and `cd k8s-ui && yarn verify`. Backend is
  untouched (expect the same 173 passing tests recorded in the 18c session
  Verify run). `Done when`: both commands pass.

## Files / areas

- `k8s-ui/components/package-card.tsx` - card click affordance (overlay button,
  z-order vs Install).
- `k8s-ui/components/marketplace-browser.tsx` - `selectedPackage` state and
  dialog mount.
- `k8s-ui/components/package-details-dialog.tsx` - new dialog component (fields
  + Helm install info block).
- Reused unchanged: `ui/dialog.tsx` (Base UI), `ui/badge.tsx`, `ui/button.tsx`,
  and the `MarketplacePackage` / `MarketplacePackageRepository` types exported
  from `package-card.tsx`. No backend, proxy route, or plan changes.

## Data / contracts

- Rendered data is exactly the `MarketplacePackage` search envelope already
  returned by `GET /api/v1/marketplace/packages` (whitelisted in
  `backend/app/api/v1/marketplace_schemas.py`) and forwarded by
  `k8s-ui/app/api/marketplace/packages/route.ts`. No new fields, endpoints, or
  remote content beyond the existing `logo_image_id` image URL. `version` here
  is the latest released version of the package summary (unchanged from 18b).
- Helm install info is a static informational string synthesized from
  `repository.name`, `repository.url`, and `package.name`; it is never executed
  client-side, and command construction/execution belongs to 18e/18g. The
  `github.com`-style chart reference `<repo>/<name>` matches Artifact Hub Helm
  semantics.
- Authorization: the dialog only opens for packages already visible to the
  authenticated user (the search request is already authorized). No new
  client/server trust boundary.
- Rendering: publisher- and description-controlled strings render as plain
  React text - no markup, no `dangerouslySetInnerHTML`. The logo uses the
  existing `<img>` with `onError` placeholder (the 18b `no-img-element` lint
  warning is accepted baseline).

## Testing

- No frontend test runner exists (per coding standards, opt-in). This step is
  verified by `yarn lint` (0 errors) and `yarn build`, plus the manual try path
  below.
- Backend tests: untouched; baseline 173 passed (recorded in this session's
  18c Verify run).
- Manual try path: start `yarn dev`, open `/marketplace`, click a card and
  confirm all fields; try a description-less package to see the fallback; open
  and dismiss repeatedly with ESC/backdrop/close; confirm the Install buttons
  (card and dialog) do nothing.

## Notes for the AI

- Never nest the overlay button inside the Install button or vice versa: the
  overlay covers the card and the Install button sits above it via z-index so
  both remain individually focusable and clickable (Install is inert in 18d).
  Use the `focus-visible` ring on the overlay button to satisfy the keyboard
  done-when.
- Follow the existing controlled-dialog pattern from
  `k8s-ui/components/users-management.tsx:387` and
  `clusters-management.tsx:365` (`<Dialog open onOpenChange>`); the dialog
  must not fetch anything.
- Reuse `packageLogo` and the logo-fallback block from `package-card.tsx`
  rather than duplicating the URL building.
- Keep every optional field behind its hide-or-fallback rule; never block
  dialog content on a missing field.
- Do not add a Drawer/Sheet component or a new route; `ui/` only ships
  `dialog.tsx`.
- The Helm install block shows a placeholder release name (e.g. `my-release`);
  it is documentation for the human, not a form field - 18e owns release-name
  collection and validation.