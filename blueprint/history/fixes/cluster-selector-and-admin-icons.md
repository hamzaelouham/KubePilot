# Current Feature

**Status:** verified
**Type:** Fix
**Branch:** fix/cluster-selector-and-admin-icons

## The problem

1. The **header** cluster selector (`k8s-ui/components/dashboard-shell.tsx`,
   top bar, not the sidebar) is a native `<select>` and reads as a browser
   dropdown next to an otherwise styled header. It should look finished, **in
   the same pattern and colors** already used (no new color/style direction).
2. The **Administration** sidebar group shows tabs (Clusters, Users, Password)
   without icons; each tab should carry a Lucide icon so the section reads like
   the rest of the sidebar.

## The fix

Reverse the transport decision from the pasted brief: rebuild the cluster
dropdown with the installed shadcn `Select` (Base UI, `k8s-ui/components/ui/select.tsx`),
keeping the exact container pattern and colors currently in the header.

- **Container (unchanged pattern).** Keep the current box: `rounded-xl border
  border-border bg-header-control px-3 py-2` inside the `flex min-w-0 items-center
  gap-2` header group. The "Cluster" micro label stays `text-xs font-medium
  uppercase tracking-wide text-muted-foreground`.
- **Trigger.** Replace the native `<select>` with
  `<Select>` + `<SelectTrigger>` + `<SelectValue>`:
  - Leading `Server` icon (`size-4 text-muted-foreground`) as the new affordance
    next to the label.
  - Selected name rendered by `SelectValue` with the current typography
    (`text-sm font-medium text-foreground`).
  - The shadcn `SelectTrigger` already renders its chevron; match trigger
    height/radius to the box (`h-10`, transparent bg, no double border — the
    outer box stays the visual container).
  - Controlled with `value={activeCluster}` and
    `onValueChange={(value) => onSelectCluster(value)}` so selection still flows
    through `useClusterSelection`/`selectCluster` (localStorage + URL sync
    unchanged). Item list = the current source
    `(clusters && clusters.length > 0 ? clusters : [activeCluster])`.
  - When `activeCluster` is empty, keep the existing "Cluster unavailable"
    `<span>` fallback.
- **Dropdown.** `SelectContent` (defaults are fine: `rounded-lg bg-popover
  text-popover-foreground shadow-md ring-1 ring-foreground/10`). Each cluster
  item shows: a green status dot (`size-2 shrink-0 rounded-full bg-emerald-500`),
  a `Server` icon (`size-4 text-muted-foreground`), and the cluster name;
  selected item gets the built-in checked indicator plus a `text-primary`
  tint. No custom CSS, no inline styles — Tailwind utilities only.
- **Administration icons.** Add a leading Lucide icon to each admin tab using
  the existing link classes (keep `pl-10`, hover, and active
  `bg-sidebar-accent … text-sidebar-accent-foreground` text styling): Clusters →
  `Server`, Users → `Users`, Password → `KeyRound`. Icons are `size-4` and use
  `currentColor` (inherit the link's foreground, so hover/active colors follow
  automatically). Group header icon swaps `Shield` → `ShieldCog` (same size,
  same color). Note: `ServerStack` is **not** available in the installed
  `lucide-react`; `Server` is the closest.

Must not break: cluster switching behavior (read-only change to the dropdown
surface; the native select is the only thing replaced), the namespace selector,
all navigation, header layout wrap, `UserMenu`, `NotificationPopover`, `+`
button, backend, API contracts, other views.

## Build steps

- [x] 1. **Replace the header cluster select.** In `dashboard-shell.tsx`, swap
  the native `<select>` inside the header cluster box for the shadcn `Select`
  family with a `Server` leading icon, micro label, and the dropdown items
  (green dot + `Server` icon + name). Keep the outer container classes/colors,
  the controlled `activeCluster`/`onSelectCluster` contract, the item source,
  and the "Cluster unavailable" fallback.
  **Done when:** `cd k8s-ui && yarn build` and `cd k8s-ui && yarn lint` pass;
  the dropdown opens a styled menu, selecting a cluster still switches and
  persists (`localStorage` key unchanged).

- [x] 2. **Add Administration icons.** Give the Administration group header the
  `ShieldCog` icon and each tab (Clusters/Users/Password) a leading icon
  (`Server`/`Users`/`KeyRound`) with `currentColor` inheritance; keep the
  existing layout, admin-only gating, active/hover styling, and links.
  **Done when:** `cd k8s-ui && yarn build` and `cd k8s-ui && yarn lint` pass;
  all three tabs render icons, active tab highlight unchanged, Users still hidden
  for non-admins.

- [x] 3. **Verify.** (frontend only, no test runner) `yarn build` + `yarn lint`
  clean, then the manual browser checks below.

## Verify

- `cd k8s-ui && yarn build` and `cd k8s-ui && yarn lint`.
- Manual (backend `PYTHONPATH=. uvicorn app.main:app --host 127.0.0.1 --port 8000` + `yarn dev`):
  - Header cluster box shows the `Server` icon, "Cluster" label, selected *active*
    cluster name, and chevron; opening it lists each active cluster with a green
    dot + name; switching clusters still changes the active context everywhere
    (URL `?cluster=`), persists across reload, and deactivated clusters do not
    appear.
  - Administration group shows icons on Clusters / Users (admin only) / Password;
    hovering and the active page keep the current colors; other sidebar groups
    and the namespace selector look exactly as before.