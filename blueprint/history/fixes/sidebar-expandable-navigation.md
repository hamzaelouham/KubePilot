# Current Feature

**Status:** verified
**Type:** Fix
**Branch:** fix/sidebar-expandable-navigation

## The problem

The sidebar (`k8s-ui/components/dashboard-shell.tsx`) renders every Kubernetes
resource flat under a category label, so Workloads alone shows 8 children and
the sidebar is unnecessarily long. It should use **expandable/collapsible
navigation groups** with modern cloud-console feel.

## The fix

Restructure only the `<aside>` nav inside `dashboard-shell.tsx`. Everything else —
layout, routing contract (`onNavigate`), namespace/cluster selectors, dashboard
and resource pages, admin functionality, API contracts, backend — stays as-is.

- **Dashboard first.** `overview` becomes a standalone first nav item
  (`onNavigate("overview", activeNamespace)`), replacing the "Overview" group.
- **Groups.** Workloads, Network, Configuration, Storage, Cluster, and
  Administration become expandable groups. Clicking a header toggles the panel;
  child items are individual buttons that keep navigating via the existing
  `onNavigate`, and Administration keeps its existing `Link`s
  (`/settings/clusters`, `/settings/users` [admin-only], `/settings/password`).
- **Category icons + chevrons.** lucide icons per group (e.g. `LayoutDashboard`
  for Dashboard, `Layers` Workloads, `Network` Network, `SlidersHorizontal`
  Configuration, `Database` Storage, `Server` Cluster, `Shield` Administration)
  and a rotating `ChevronDown` for open groups. Subtle hover and the current
  active styling (`bg-sidebar-accent`/`text-sidebar-accent-foreground`) are kept.
- **Auto-expand active group.** Open state is controlled state seeded from
  `activeResource`: the group whose item matches the current resource starts
  open, and an effect re-opens it whenever `activeResource` changes, so the
  active item always stays visible (direct-link navigation included).
- **Component reuse.** Add `components/ui/collapsible.tsx` wrapping the already
  installed `@base-ui/react/collapsible` (same Base UI family as every existing
  ui component; the @shadcn registry `collapsible` depends on `radix-ui`, which
  this base-nova project does not use). Icons come from the installed
  `lucide-react`. No new layout system, no scroll/tooltip/separator components,
  no new breakpoints — responsive behavior is unchanged (existing `w-56` /
  `lg:w-[286px]` aside).
- **Accessibility.** Group triggers use `aria-expanded` (Base UI provides it);
  child buttons remain focusable/navigable.

Must not break: `resourceTitles`, `isActive` highlighting, cluster selector,
namespace selector, header (cluster box, +, notifications, user menu), the
namespace select below the groups, `getClusterClient` routing, or any non-shell
file.

## Implementation note

Expansion state is fully derived in render (no effects): a small
`manuallyOpened`/`manuallyClosed` intent model plus an active-resource override.
The group containing the active resource opens on load and on navigation; manual
open/close is respected; entering a group clears a stale manual close (render-phase
adjustment) so deep links always reveal the active item. This kept `yarn lint`
at 0 errors (avoids `react-hooks/set-state-in-effect`).

## Build steps

- [x] 1. **Implement the expandable sidebar.** Add `k8s-ui/components/ui/collapsible.tsx`
  (Base UI `Collapsible.Root`/`Trigger`/`Panel` wrapper in the style of
  `ui/dialog.tsx`). In `dashboard-shell.tsx`: split `navGroups` into a standalone
  Dashboard item plus the collapsible groups (Workloads, Network, Configuration,
  Storage, Cluster) and an Administration group containing the existing links;
  add an expansion-state hook seeded from `activeResource` with a re-open effect
  on `activeResource` change; render group headers (icon + label + `ChevronDown`)
  and keep child item buttons and active styling exactly as today; keep the
  namespace select and sidebar container classes.
  **Done when:** `cd k8s-ui && yarn build` and `cd k8s-ui && yarn lint` pass;
  Dashboard is the first item; groups toggle open/closed; the active resource's
  group opens automatically on load and on navigation.

- [x] 2. **Verify.** (frontend only, no test runner) `yarn build` + `yarn lint`
  clean, then manual browser check of the paths in *Verify* below.

## Verify

- `cd k8s-ui && yarn build` and `cd k8s-ui && yarn lint`.
- Manual (backend `PYTHONPATH=. uvicorn app.main:app --host 127.0.0.1 --port 8000` + `yarn dev`):
  - Dashboard is the first item; clicking it opens `?resource=overview`.
  - Clicking **Workloads** expands (Pods…ReplicationControllers), clicking again
    collapses; other groups (Network, Configuration, Storage, Cluster,
    Administration) behave the same.
  - Clicking **Deployments** opens the Deployments view and highlights it.
  - Navigating directly to `?resource=pods` auto-expands Workloads and highlights
    Pods.
  - Cluster selector, namespace selector, header cluster box/+/notifications/user
    menu, and all pages behave exactly as before.