# Feature 17: UI polish & design consistency

**Type:** Feature
**Status:** verified
**Branch:** `feature/ui-polish-and-design-consistency`

## Goal

Make the product feel like one coherent design system. Bring the home, login, and
change-password pages onto the dashboard's existing light palette as simple
centered forms, restructure the sidebar into grouped sections that show only
resources with working views, rework the header around the KubePilot brand and a
cluster selector, and give the shell a `clusterId` context so the future
Multi-cluster feature (13) slots in without a redesign.

## In scope

- Home (`app/page.tsx`), login (`app/login/page.tsx`), and change-password
  (`app/settings/password/page.tsx`) adopt the dashboard's light palette using
  the existing semantic tokens in `app/globals.css` (`bg-background`,
  `bg-card`, `text-foreground`, `text-muted-foreground`, `--primary` cyan
  `#0891b2`, `border-border`) — not new hardcoded hex values and not the current
  dark navy gradients.
- Login page: a single centered card containing only the sign-in form. Remove
  the marketing panel, headline, stat cards, the "Control plane" logo tile, the
  "Welcome back" header, the dead "Forgot password?" link, and the footer note.
  Keep the `invalid` / `backend` error states and the `signInAction` server
  action contract unchanged.
- Change-password page: a single centered card with brand, heading, and the
  existing `ChangePasswordForm`. Keep the forced-change intro text and the
  "Back to dashboard" link condition; drop the logo tile and redundant chrome.
- Sidebar: grouped sections with headers, per the approved structure, rendering
  only resources that have working views today:
  - OVERVIEW: Dashboard
  - WORKLOADS: Pods, Deployments, StatefulSets, DaemonSets, Jobs, CronJobs,
    Replica Sets, Replication Controllers (existing views retained in their
    natural group)
  - NETWORK: Services (Ingresses / NetworkPolicies omitted — no views)
  - CONFIGURATION: Namespaces (ConfigMaps / Secrets omitted — no views)
  - STORAGE: Persistent Volumes, Storage Classes (PVCs omitted — no views)
  - CLUSTER: Nodes, Cluster Roles (Events nav omitted — events live in detail
    tabs)
  - ADMINISTRATION: Users (admin role only), Password (all roles) — Clusters
    and Audit Logs omitted until those features exist
  - The legacy "Workloads" aggregate nav item is removed from the sidebar; the
    overview page already surfaces workload summaries and the aggregate view
    stays reachable by URL. Keep the namespace selector in the sidebar.
- Header: replace the `◈ kubernetes` mark with a `☸ KubePilot` brand; add a
  `Cluster: [<name> ▼]` selector sourced from the backend cluster status;
  keep the `+` button, notifications bell, and user menu. Remove the unused
  `theme-switcher.tsx` if nothing references it after the shell rework.
- Shell `clusterId` seam for Multi-cluster (13): the dashboard carries the
  active cluster in state and in the URL (`?cluster=<id>`), defaulting to the
  single connected cluster reported by the backend. No multi-cluster backend or
  cluster-list API is added in this feature.
- Light/dark mode keeps working on all touched pages (token-based, not
  hardcoded colors).

## Out of scope

- Building views for Ingresses, NetworkPolicies, PersistentVolumeClaims,
  ConfigMaps, Secrets, Events, Clusters, or Audit Logs.
- Any Multi-cluster backend work, cluster registration, or cluster-switching
  API (feature 13).
- Changing auth, RBAC, session, or password business logic; the API contract of
  `signInAction`, the login routes, or the change-password route.
- The resource detail pages, tables, and other component-level styling beyond
  the pages and shell listed above.

## Build loop

- Local CLI workflow. `stepReview` is `feature` (one review packet after all
  steps). No checkpoint commits; one work commit via `/complete`. Steps run on
  the `feature/ui-polish-and-design-consistency` branch.

## Build steps

- [x] 1. **Cluster context for the shell** - add `app/api/cluster/status/route.ts`
  proxying `GET /api/v1/cluster/status` to the backend (single cluster, no
  cluster id yet); thread `clusterId` through `dashboard.tsx` state and the
  dashboard URL (`?cluster=`), defaulting to the backend-reported cluster name.
  Done when the dashboard URL carries `cluster=<name>` and navigating preserves
  it, and the new proxy route returns the backend cluster name
  (`curl /api/cluster/status` through the running app).
- [x] 2. **Header rework** - in `dashboard-shell.tsx`, render the `☸ KubePilot`
  brand, a `Cluster: [<name> ▼]` selector bound to the active cluster (single
  option; "Cluster unavailable" muted fallback if the status fetch fails), and
  keep `+`, bell, user menu on the right. Done when the header matches the
  target layout in the browser and the active cluster name comes from the
  backend.
- [x] 3. **Grouped sidebar** - in `dashboard-shell.tsx`, replace the flat
  navItems/secondaryNav arrays with the grouped sections above; each section
  renders only existing resources, the active item highlights, links navigate
  to `/dashboard?resource=<id>&namespace=<ns>` preserving `cluster`. Done when
  every sidebar item maps to a working view, group headers show, and
  admin-only "Users" is hidden for non-admins.
- [x] 4. **Home page on the light palette** - rewrite `app/page.tsx` with the
  brand mark and centered card using semantic tokens and the dashboard palette
  (light), keeping "Go to login" and "Open dashboard preview". Done when `/`
  matches the dashboard look in light and dark mode and still links correctly.
- [x] 5. **Simple centered login** - rewrite `app/login/page.tsx` to a single
  centered card with brand + email/password + submit + error alert, on the
  light palette with semantic tokens. Done when `/login` shows only the form and
  both `invalid` and `backend` errors display, and `/dashboard` redirect on
  signed-in still works.
- [x] 6. **Simple centered change-password** - rewrite
  `app/settings/password/page.tsx` to a single centered card keeping the
  forced-change messaging and back link; remove logo tile chrome. Done when the
  forced-password flow (searchParam `forced=1`) still works end to end.
- [x] 7. **Final verification** - run `yarn lint`, `yarn verify` in `k8s-ui`,
  backend `pytest` (untouched, must stay green), and the project Verify command.
  Done when all pass and review begins.

## Live-review additions

Identified during browser testing of the running cluster, within the feature's
design-consistency scope; implemented and verified:

- **Settings users page in the shell** - `app/settings/users/page.tsx` and a new
  `components/user-settings-view.tsx` render `UsersManagement` inside the
  `DashboardShell` (grouped sidebar, `☸ KubePilot` header, cluster selector,
  user menu), replacing the page's standalone layout with the pre-feature `◈
  kubernetes` header. Admin gate stays server-side; "Users" added to the shell's
  sub-bar title mapping.
- **Responsive layout - no horizontal page overflow** - the shell's `main` (and
  inner card) get `min-w-0` so flex children shrink instead of expanding the
  page; the root clips horizontal overflow; the sidebar narrows on smaller
  screens (`w-56 lg:w-[286px]`); the header and all view header rows wrap
  (`flex-wrap`).

## Files / areas

- `k8s-ui/app/page.tsx` - home rewrite (step 4)
- `k8s-ui/app/login/page.tsx` - login simplification (step 5)
- `k8s-ui/app/settings/password/page.tsx` - change-password simplification (step 6)
- `k8s-ui/components/dashboard.tsx` - `clusterId` state + URL (step 1)
- `k8s-ui/components/dashboard-shell.tsx` - grouped sidebar + header rework (steps 2–3)
- `k8s-ui/app/api/cluster/status/route.ts` - new backend status proxy (step 1)
- `k8s-ui/components/theme-switcher.tsx` - remove if unreferenced after step 3
- `k8s-ui/app/globals.css` - only if a shared token needs to be exposed; no new
  hex palettes
- `k8s-ui/app/settings/users/page.tsx`,
  `k8s-ui/components/user-settings-view.tsx` - users page renders in the shell
  (live-review addition)
- `k8s-ui/components/dashboard-shell.tsx` - responsive: overflow-x-clip root,
  `min-w-0` main/card, responsive sidebar width, wrapping header (live-review
  addition)
- `k8s-ui/components/{cluster,core-resource,namespaces,overview,workloads}-view.tsx`
  - wrapping header rows (live-review addition)
- Reference (do not modify): `k8s-ui/lib/backend.ts` proxy helpers, `proxy.ts`
  route guard, `components/user-menu.tsx`, `components/notification-popover.tsx`

## Data / contracts

- Reuse backend `GET /api/v1/cluster/status` →
  `{ "status": "connected", "cluster": "<cluster_name>" }` (already served by
  `backend/app/api/v1/routes.py:241`). Proxy pattern mirrors
  `app/api/cluster/namespaces/route.ts` via `lib/backend.ts`.
- No DB or API contract changes; `signInAction` returns unchanged so the login
  proxy routes and error mapping stay intact.
- URL contract for the dashboard becomes
  `/dashboard?resource=<id>&namespace=<ns>&cluster=<id>`; `cluster` is optional
  and defaults to the sole connected cluster so hand-written links without it
  keep working.

## Testing

- Backend pytest suite must stay green (auth/session/RBAC untouched).
- Frontend: `yarn lint` and `yarn verify` in `k8s-ui`; near-dead code check via
  `rg "theme-switcher|workloads"` for leftover references after the rework.
- Manual/browser evidence from the running app (Minikube NodePort or
  `yarn dev`): the listed done-when statements are observable in the running
  UI. No automated browser suite exists; no new test runner is added.

## Notes for the AI

- The dashboard palette lives in `app/globals.css`: light `--background:
  #ebeff3`, `--card`, `--primary: #0891b2` (cyan), `--sidebar: #f8f9fb`, plus
  dark-mode tokens. Use these tokens; do not hardcode the current navy
  gradients (`#11243d`, `#0f172a`, `#020817`).
- The shadcn Base UI `DropdownMenuLabel` throws unless wrapped in a `Menu.Group`
  (`DropdownMenuGroup`) — irrelevant unless new menus are added; keep it in mind
  when reworking the header.
- Tailwind v4 preflight sets `cursor: default`; the global pointer rule in
  `app/globals.css` already restores it for buttons/menu items — keep it intact.
- `components.json` uses the `@shadcn` registry; UI components import `cn` from
  `"cn"`, not `@/lib/utils`.
- `dashboard-shell.tsx` fetches namespaces from `app/api/cluster/namespaces`;
  the cluster selector follows the same pattern against the new status route.
- Feature 13 (Multi-cluster) reads the `clusterId` seam; keep the selector
  single-entry and do not build cluster listing.

## Open questions

- None blocking. Internal choices already made: remove the "Workloads" aggregate
  sidebar link (summary stays on Overview); remove the dead "Forgot password?"
  link; the cluster selector renders one entry sourced from cluster status when
  available and a muted "Cluster unavailable" state otherwise.