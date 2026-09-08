# Current Feature

**Status:** verified
**Type:** Feature
**Branch:** feature/marketplace-navigation-and-page

## Goal

Add the Marketplace to the KubePilot application: a new `/marketplace` route
that reuses the existing application shell (header cluster selector, sidebar,
namespaces context) and shows a page header ("Marketplace — Discover and
install Kubernetes applications."), with a main-sidebar entry that looks native
and leaves every existing navigation path untouched. This is build-plan item **18a**
(first slice of feature 18, KubePilot Marketplace).

## In scope

- New protected route `app/marketplace/page.tsx` (server component) that
  authenticates via `requireUsableBackendUser()` — the exact pattern used by
  `app/dashboard/page.tsx` — and renders a client `MarketplaceView`.
- New client component `components/marketplace-view.tsx`: a `"use client"`
  view wrapping `DashboardShell` exactly like `ClusterSettingsView`:
  - `activeResource="marketplace"`, `activeNamespace="default"`,
    `useClusterSelection()`, `onSelectCluster={selectCluster}`, and an
    `onNavigate` that routes to `/dashboard?resource=…&namespace=…[&cluster=…]`
    (settings-view navigation pattern).
  - Content area shows the page header only:
    `h1` "Marketplace" (`text-2xl font-semibold text-foreground`) and
    description "Discover and install Kubernetes applications."
    (`mt-1 text-sm text-muted-foreground`). The content body stays empty —
    package discovery is 18b.
- Sidebar entry in `components/dashboard-shell.tsx`: a standalone Marketplace
  nav item (like the Dashboard item) rendered **below Dashboard and above the
  resource groups**, styled as a `Link` to `/marketplace` with the lucide
  `Store` icon (`h-4 w-4 shrink-0`), the same active/hover classes as the admin
  links (`bg-sidebar-accent font-medium text-sidebar-accent-foreground` active,
  `text-sidebar-foreground/70 hover:bg-sidebar-accent` inactive). Active state
  is driven by `activeResource === "marketplace"` so the item highlights on the
  page.
- `resourceTitles` entry `marketplace: "Marketplace"` so the shell's primary
  header bar shows "Marketplace" instead of the "Overview" fallback.

## Out of scope

- Package discovery, Artifact Hub API calls, PackageCard, skeletons, empty and
  error states (18b).
- Search/filter/debounce (18c), package details (18d).
- Installation dialog (18e), install/status/history APIs or jobs (18f-18j).
- Security & validation policies for installs (18k), UI polish pass (18l).
- Any backend change, new API, new dependency, or new stored data.
- Marketplace content in any of the WORKLOADS / NETWORK / CONFIGURATION /
  STORAGE / CLUSTER sidebar groups — the entry is a standalone top-level item.

## Build loop

- Per `workflow.stepReview` (`feature`): present one review packet after all
  steps, no per-step approval pauses.
- Per `workflow.checkpointCommits` (`disabled`): no intermediate commits;
  `/complete` makes the single feature commit. Verify runs per step's
  done-when and the full declared Verify once after all steps.

## Build steps

- [x] 1. **Add the `/marketplace` route and shell page.** Create
  `app/marketplace/page.tsx` (calls `requireUsableBackendUser()`, renders
  `<MarketplaceView user={user} />`) and `components/marketplace-view.tsx`
  (wraps `DashboardShell` with `activeResource="marketplace"` and the page
  header only). Do not touch the sidebar yet.
  **Done when:** `cd k8s-ui && yarn build` and `cd k8s-ui && yarn lint` pass;
  signed-in user visiting `/marketplace` sees the shell with header "Marketplace"
  and the content header "Marketplace" + "Discover and install Kubernetes
  applications."; the namespace dropdown and cluster selector still work;
  unauthenticated users are redirected to `/login` (existing
  `requireUsableBackendUser` behavior).

- [x] 2. **Add the sidebar Marketplace entry.** In `dashboard-shell.tsx`: import
  `Store` from `lucide-react`, add `marketplace: "Marketplace"` to
  `resourceTitles`, and render a standalone `Link` item "Marketplace" (Store
  icon) below the Dashboard button and above the nav groups, active when
  `activeResource === "marketplace"`.
  **Done when:** `cd k8s-ui && yarn build` and `cd k8s-ui && yarn lint` pass;
  the sidebar shows a Marketplace item with the Store icon that highlights on
  `/marketplace`; Dashboard, every resource group, and Administration still
  navigate and highlight exactly as before; header label stays "Marketplace".

- [x] 3. **Verify.** Run the declared Verify command once.
  **Done when:** `cd backend && .venv/bin/python3 -m pytest` passes (161 tests)
  and `cd k8s-ui && yarn verify` passes.

## Files / areas

- `k8s-ui/app/marketplace/page.tsx` (new) — protected server page.
- `k8s-ui/components/marketplace-view.tsx` (new) — shell-wrapped client view.
- `k8s-ui/components/dashboard-shell.tsx` — nav item, `resourceTitles` entry,
  `Store` import (the only existing file changed).
- No backend files. No test files (frontend has no test runner; backend
  untouched).

## Data / contracts

- No new API, data model, or stored state. The page reads only the existing
  shell `ClusterContext` (active cluster from localStorage/URL, namespaces via
  `/api/cluster/namespaces` owned by `DashboardShell`).
- Route contract: `/marketplace` is reachable for any signed-in, usable user
  (all three roles admin/operator/viewer — no install permission exists yet,
  which is correct for a pure discovery landing page).
- URL shape: fixed path `/marketplace` (no query params in 18a).

## Testing

- Verification only: `yarn build` + `yarn lint` per step; declared Verify once
  (backend tests unchanged + frontend build). No logic tests (no new logic),
  no browser harness (none configured — `/browser-tests` is a separate opt-in).

## Notes for the AI

- Follow the two existing patterns exactly: `app/dashboard/page.tsx`
  (`requireUsableBackendUser`) for the server page and
  `components/cluster-settings-view.tsx` for the shell-wrapped client view.
- There is no route middleware; page-level `requireUsableBackendUser` is the
  repo's protection mechanism — keep it that way.
- Place the sidebar item between Dashboard and the first group; do not add the
  Store icon to a `NavGroup` or to Administration.
- No package content, fetching, skeletons, or placeholders beyond the header —
  that is 18b.
- Reuse `Store` from the installed `lucide-react` (confirmed available).

## Open questions

None material for 18a. (Package/listing behavior, install policy, and data
contracts belong to 18b-18l specs.)