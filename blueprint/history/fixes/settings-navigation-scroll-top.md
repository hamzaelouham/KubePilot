# Settings navigation scrolls to top

**Type:** Fix

**Status:** verified

**Branch:** `fix/settings-navigation-scroll-top`

## The problem

Navigating from a scrolled dashboard to Settings, or between Settings sections,
could preserve the previous document scroll position and open the destination in
the middle of the page.

## The fix

Add a shared browser helper that scrolls the document to the top when the
dashboard Administration links and Settings section links are activated. Keep
route targets, active states, permissions, cluster context, mobile navigation,
and inner scroll areas unchanged.

## Build steps

- [x] Add the shared page-scroll helper and apply it to dashboard Administration
  links and Settings section links.
  - **Done when:** navigating to Settings or between Settings sections resets
    the document position to the top without changing route behavior or inner
    scrollable panels.

## Verify

- `./scripts/verify-feature.sh`: focused tests passed; its Turbopack build is
  blocked by the environment's `Operation not permitted` process-port error.
- `yarn next build --webpack`: passed outside the sandbox with successful
  production compilation, TypeScript, static generation, and route generation.
- Manual review path: scroll down on `/dashboard`, open Administration →
  Settings, and confirm the destination starts at the top. Scroll within
  Settings, switch sections, and confirm the page resets without changing
  inner scrollable panels.
