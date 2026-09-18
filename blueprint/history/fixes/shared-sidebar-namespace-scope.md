# Shared Sidebar Namespace Scope

**Type:** Fix

**Status:** verified

**Branch:** `fix/shared-sidebar-namespace-scope`

## The problem

The shared app sidebar does not show the **All namespaces** option when
`DashboardShell` discovers namespace options itself. The option is currently
rendered only when a page passes `namespaceOptions`, so the dashboard and other
pages using the shell's built-in namespace request expose inconsistent choices.

App pages should continue to use the same shared `DashboardShell` navigation,
namespace selector, and visual styling rather than introducing page-specific
sidebars.

## The fix

Make the cluster-wide **All namespaces** choice part of the shared namespace
selector regardless of whether its namespace list is supplied by a page or
discovered by `DashboardShell`.

Keep namespace discovery cluster-scoped, preserve the selected namespace and
the existing unavailable-namespace fallback, and route the all-namespaces
choice through the existing empty namespace value. Do not duplicate or restyle
the sidebar in individual app pages.

## Build steps

1. [x] Update the shared sidebar namespace selector in `DashboardShell` so fetched
   and supplied namespace lists have the same cluster-wide option and selection
   behavior.

   **Done when:** **All namespaces** appears exactly once on the dashboard and
   other pages using the shared shell, selecting it sends an empty namespace to
   the existing navigation handler, discovered namespace choices still appear
   for the active cluster, and an unavailable active namespace remains visible
   and understandable.

## Verify

- Run `./scripts/verify-feature.sh`.
- In the running UI, open the namespace selector on `/dashboard` and confirm
  **All namespaces** plus every discovered namespace is shown.
- Select **All namespaces** and confirm the dashboard URL and resource view use
  cluster-wide scope without a duplicate or stale selected item.
- Open another app page that uses `DashboardShell` (for example `/marketplace`
  or `/settings`) and confirm the sidebar keeps the same styling and namespace
  options.
- Switch clusters and confirm the namespace selector reflects the newly active
  cluster without retaining invalid options from the previous cluster.

## Verification evidence

- `yarn lint components/dashboard-shell.tsx` passed.
- `./scripts/verify-feature.sh`: assistant tests passed (13/13); the Next.js
  Turbopack build is blocked in this environment by `Operation not permitted`
  while binding a process port.
- `yarn next build --webpack` passed, including TypeScript and production route
  generation.
