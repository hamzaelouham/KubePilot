# Resource Detail Sidebar User Context

**Type:** Fix

**Status:** verified

**Branch:** `fix/resource-detail-sidebar-user-context`

## The problem

Resource detail routes such as pod details and workload details render the
shared `DashboardShell` without the authenticated `BackendUser`. The detail
page does authenticate the request, but it discards the returned user before
rendering `ResourceDetailView`, so the sidebar hides the logged-in profile menu
and the Administration section on those pages.

## The fix

Pass the authenticated user from `/dashboard/detail` into `ResourceDetailView`
and then into `DashboardShell` for both the Suspense fallback and the loaded
detail view. Keep the existing shared sidebar styling, cluster selection,
resource navigation, and authorization behavior unchanged.

## Build steps

1. [x] Thread the `BackendUser` prop through the resource-detail page and view into
   the shared shell.

   **Done when:** opening a resource detail route while signed in shows the
   same logged-in profile control and role-appropriate Administration links as
   the dashboard, including during the loading fallback, without changing the
   detail data requests or back-navigation behavior.

## Verify

- Run `./scripts/verify-feature.sh`.
- From the dashboard, open a workload or pod **View details** link and confirm
  the sidebar shows the logged-in profile menu and Administration section.
- Confirm the same controls remain present while detail data is loading and
  after the detail view resolves.
- Confirm the detail tabs, cluster selector, namespace selector, and **Back to
  resources** navigation still work.
- Confirm a non-admin user sees only the Administration links allowed by the
  existing role filter.

## Verification evidence

- `yarn lint app/dashboard/detail/page.tsx components/resource-detail-view.tsx`
  passed.
- `./scripts/verify-feature.sh`: assistant tests passed (13/13); the Next.js
  Turbopack build is blocked in this environment by `Operation not permitted`
  while binding a process port.
- `yarn next build --webpack` passed, including TypeScript and production route
  generation.
