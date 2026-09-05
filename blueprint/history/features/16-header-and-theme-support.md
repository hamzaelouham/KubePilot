# Current Feature

**Status:** verified (complete)
**Type:** Feature
**Branch:** feature/header-and-theme-support

## Goal

Feature 16 — **Header components and theme support.** Remove the non-functional
header search box, migrate the remaining header controls (notification, logout)
to shadcn/ui components, and add light/dark theme support with a theme switcher,
while **preserving the existing design exactly** (layout, header height, sidebar,
colors, typography, spacing, borders, radius, icons, button sizes, responsive
behavior, visual identity). This is an incremental UI enhancement, not a
redesign: adopt shadcn/ui components into the existing design, never the default
shadcn look over it.

## In scope

- **Remove the non-functional search box (Task 1).** Delete the `div` search
  placeholder (`w-[520px] ... "Search"`) in the header of
  `components/dashboard-shell.tsx`. It has no state, handler, import, or logic of
  its own to remove — it is a static `div`. Adjust header spacing only if needed
  to avoid empty space. Do not replace it with another search.
- **Migration of existing header controls (Task 2).**
  - **Notification.** Replace the static `🔔` `<button>` with a shadcn `Button`
    (icon-only) wrapping a `Popover` showing a clean empty state — "No
    notifications" (no fake backend, no procurement of real notification data).
    Preserve icon, size (`h-11 w-11`), spacing, border, and visual style.
  - **Logout.** Replace the "Sign out" `<button>` with a shadcn `Button`,
    preserving its appearance, position, and the existing
    `signOut()` → `POST /api/logout` → redirect `/login` behavior. Keep it as a
    standalone button (matches the current design; no profile menu exists).
  - **User/profile.** None exists today, so nothing is added; logout stays
    standalone. Do not invent a profile menu or avatar.
- **Theme support (Tasks 3–4).** Add light/dark/system theme support via
  `next-themes`:
  - Add a `ThemeProvider` (wrapped in a `theme-provider.tsx`) with
    `attribute="class"` around the app in `app/layout.tsx`.
  - Add a **theme switcher** on the right side of the header using shadcn
    `Button` + `DropdownMenu` (Light / Dark / System). Selected theme persists
    after refresh (localStorage).
  - The selected `class` toggles the existing `.dark` variant and shadcn semantic
    CSS variables already in `app/globals.css`.
- **Preserve the existing design while applying themes (Task 5).** Map the current
  colors to shadcn semantic tokens so light mode is byte-identical to today's
  slate/cyan design, and add corresponding dark values — without changing layout,
  structure, typography, spacing, or sizing. Do not adopt default shadcn colors.
- **Header control order (Task 6).** Keep the current structure and alignment.
  Right side, in order: theme switcher, notification, logout (there is no
  profile control; leave the pre-existing "+" button untouched as it predates
  this feature and is not in scope to remove).
- **Build/validation (Task 7).** Run `yarn build` and fix errors; confirm the
  search is gone, notification shows an empty state, logout works, light/dark
  switching works and persists, and the design is unaltered in light mode.

## Out of scope

- **Redesign / design change.** No changes to overall layout, header height,
  sidebar, colors (light mode), typography, font sizes, spacing, padding,
  margins, borders, radius, background, status pills, button sizes, tables,
  cards, responsive behavior, or icons. No new navigation or tabs.
- **Backend changes.** `/api/logout` and the auth/session flow are unchanged.
  No new notification API or any invented/fake backend functionality.
- **A user/profile menu or avatar** (none exists today).
- **Converting every hardcoded `slate-*`/hex utility across all view components**
  to tokens. Only the app surface/chrome needed for meaningful light/dark theming
  (shell, sidebar, header, main/card surfaces, borders, text) is converted; deep
  per-cell/status styling in view internals is left as-is unless trivially
  required for dark readability. Anything that would change the light-mode look is
  excluded.
- **Adding new notifications infrastructure or a data layer.**

## Build loop

- Create branch `feature/header-and-theme-support` (exact `Branch` value).
- `workflow.stepReview: feature` — build all small steps, then one review packet.
- `workflow.checkpointCommits: disabled` — no per-step checkpoint commits.
- Frontend Verify is the build: `cd k8s-ui && yarn build` (no project `test`
  command; `yarn lint` is eslint on changed files — the pre-existing 9
  `react-hooks/set-state-in-effect` warnings on data-loading effects may remain
  but must not grow).
- shadcn components are added with the CLI using the project's Yarn runner /
  `npx shadcn@latest` (per the installed `shadcn` skill rules: semantic tokens,
  `gap-*`, `cn()`, `size-*`, `data-icon`, Base UI `render`/`asChild`).

## Build steps

- [ ] 1. **Install theme deps and add needed shadcn components.** In `k8s-ui/`
  add `next-themes` via Yarn, and `npx shadcn@latest add popover dropdown-menu
  button` (add only what is missing; `dropdown-menu` and `button` already exist —
  add `popover`). Confirm `components.json` still resolves and Token/tailwind
  wiring is intact.
  **Done when:** `next-themes` is in `package.json`, `components/ui/popover.tsx`
  exists, and a baseline `yarn build` passes.

- [ ] 2. **Add the theme provider and wire it into the layout.** Create
  `components/theme-provider.tsx` (ThemeProvider passthrough with
  `attribute="class" defaultTheme="system" enableSystem`). Wrap children in
  `app/layout.tsx`. Confirm globals.css already exposes `:root` light tokens and
  a `.dark` block plus `@custom-variant dark` (present — verify, don't break).
  **Done when:** provider is mounted, `yarn build` passes, and adding
  `class="dark"` to `<html>` visibly toggles the app to the dark palette.

- [ ] 3. **Build the theme switcher.** Add a small `theme-switcher.tsx` (client)
  using shadcn `Button` (icon) + `DropdownMenu` with Light / Dark / System items
  and `Sun`/`Moon`/`Monitor` lucide icons, wired to `next-themes`
  `useTheme`/`setTheme`. Rendered on the right of the header before the
  notification control.
  **Done when:** the switcher toggles light/dark/system, persists across refresh,
  and stays styled to the existing icon-button look (`h-11 w-11 rounded-xl border
  border-slate-200 bg-[#f3f4f6]` in light).

- [ ] 4. **Migrate the notification control.** Replace the static `🔔` button in
  `components/dashboard-shell.tsx` with a shadcn `Button` (icon-only, `Bell`
  lucide icon) inside a `Popover` whose content shows a clean empty state ("No
  notifications"). Preserve size, spacing, border, and position.
  **Done when:** the control renders with the same look, opens an empty-state
  popover on click, and `yarn build` passes.

- [ ] 5. **Migrate the logout button.** Replace the "Sign out" `<button>` with a
  shadcn `Button`, keeping `signOut()` (POST `/api/logout` → redirect `/login`)
  and its current appearance/position.
  **Done when:** the shadcn button renders identically, logout still clears the
  session and redirects to `/login`, and `yarn build` passes.

- [ ] 6. **Make the app surface theme-aware.** Convert `components/dashboard-shell.tsx`
  hardcoded hex/slate surface classes to shadcn semantic tokens so light-mode
  values equal today's design and dark values are provided in `globals.css`:
  - App container `bg-[#ebeff3] text-slate-800` → `bg-background text-foreground`
  - Header bar `bg-white border-slate-200` → `bg-card border-border`
  - Sub-header band `bg-[#4a5ee7] text-white` → keep as a custom brand token or
    `bg-primary text-primary-foreground` if primary becomes the indigo
  - Sidebar `bg-[#f8f9fb] border-slate-200` → sidebar tokens + `border-border`
  - Main `bg-[#f5f7f9]`, content card `bg-[#f9fafb] border-slate-200` → surface/
    card tokens + `border-border`
  - Add corresponding `.dark` values in globals.css for these surfaces.
  Preserve every light-mode value exactly. Do not change layout/spacing.
  **Done when:** light mode is visually unchanged, dark mode renders a coherent
  dark surface set, and `yarn build` passes.

- [ ] 7. **Remove the non-functional search box and final validation.** Delete
  the `w-[520px]` "Search" `div` from the header (and any now-unused imports).
  Adjust only if spacing leaves a gap. Then run `yarn build` (and eslint on
  changed files). Manually verify: search gone; notification empty state; logout
  redirects to `/login`; light/dark/system switching works and persists; side by
  side the light design is unchanged.
  **Done when:** `yarn build` passes, lint has no new errors, and every
  validation item above is confirmed.

## Files / areas

- `k8s-ui/package.json`, `k8s-ui/yarn.lock` — add `next-themes`.
- `k8s-ui/components/theme-provider.tsx` (new) — next-themes provider wrapper.
- `k8s-ui/components/theme-switcher.tsx` (new) — header theme control.
- `k8s-ui/app/layout.tsx` — mount `ThemeProvider`.
- `k8s-ui/components/dashboard-shell.tsx` — remove search; migrate notification
  + logout; add theme switcher; convert surfaces to semantic tokens.
- `k8s-ui/components/ui/popover.tsx` (new) — notification popover primitive.
- `k8s-ui/app/globals.css` — confirm/add `.dark` surface values; do not change
  light values or layout tokens.

## Data / contracts

- `POST /api/logout` → `{ ok: true }`, clears session, client redirects to
  `/login`. Unchanged from current behavior.
- No new backend route, schema, or API. No notification data source.
- Theme persistence: `next-themes` stores the choice in `localStorage` and toggles
  `class="dark"` on `<html>`, reading the existing `@custom-variant dark` and
  `.dark` CSS variables.

## Testing

- **Build/lint (`uiEvidence: when-available`):** no frontend test runner
  configured. Verify with `cd k8s-ui && yarn build` (clean) and `yarn lint`
  (no new errors on changed files; the pre-existing 9 `set-state-in-effect`
  warnings are out of scope).
- **Manual:** search box absent; notification button opens an empty-state popover;
  Sign out redirects to `/login` and clears the session; theme switcher cycles
  Light/Dark/System and persists after refresh; light mode matches the previous
  design (colors, typography, spacing, layout, positioning); responsive header
  still behaves (controls wrap/retain spacing) on narrow widths.

## Notes for the AI

- **Design is the source of truth.** Preserve the existing design; only replace
  underlying components and add the requested functionality. Compare against the
  prior look and confirm colors/typography/spacing/layout/positioning are
  unchanged in light mode. Never let shadcn defaults override the current UI.
- Follow the installed `shadcn` skill rules for new components (semantic tokens,
  `gap-*` not `space-*`, `cn()`, `size-*` for equal dims, `data-icon`, Base UI
  `render`/`asChild`). Use lucide icons (project's icon library).
- `dashboard-shell.tsx` is a client component already (`"use client"`); the theme
  switcher and notification need client rendering, and next-themes uses the
  `useTheme` hook — keep those boundaries correct for RSC (provider in the root
  layout, hooks in client components).
- The surface conversion (step 6) must keep light values byte-identical to the
  current design. Where a view-internal `slate-*` class
  would be illegible in dark (rare, deep in status cells), leave it; do not
  expand scope into view redesign.
- Do not remove or alter the pre-existing "+" header button; it is out of scope
  but must not be broken.
- Run `yarn build` after each step; the build is the final gate.

## Open questions

- None. The packet is explicit; the only material choice — representative dark
  `.dark` values for the indigo brand band and surfaces — is a reversible
  presentation decision with light mode pinned to the current design.

## Completion note

- Merged to `master` and pushed by `/complete`; the PR on GitHub
  (`feature/header-and-theme-support`) was the CI vehicle for Docker image build
  and push and was closed without merging.
- Work commits squashed into the master merge: feature work, two `ci(docker)`
  commits (manual workflow + PR trigger), the deploy/docs commit, and the
  dark-mode/cursor fix commit.