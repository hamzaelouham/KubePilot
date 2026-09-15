# Current Feature: Marketplace UI polish and responsive

**Type:** Feature 18l

**Status:** verified

**Branch:** `feature/marketplace-ui-polish-responsive`

## Goal

Polish the existing `/marketplace` experience so package discovery, package cards,
loading and error states, package details, and installation feedback remain clear
and usable from mobile through desktop. Preserve the current Artifact Hub search,
pagination, install, and background-job behavior while aligning the UI with the
existing KubePilot light/dark theme and installed shadcn/ui components.

## In scope

- Responsive Marketplace page header, search/sort controls, package grid, and pagination.
- A reusable package-card loading skeleton for initial package loading and refresh states.
- Consistent empty, error, retry, and partial-refresh presentation using the existing shadcn primitives.
- Package card hierarchy, metadata wrapping, logo fallback, full-card details activation, and Install action behavior.
- Responsive package details and installation dialogs, including long descriptions, metadata, Helm information, validation feedback, and narrow-screen scrolling.
- Existing install progress and failure feedback where it is rendered by the Marketplace flow.
- Existing dialog animation behavior and reduced-motion support; no new animation library.
- Accessible labels, focus states, live status announcements, and touch-sized controls at narrow viewports.

## Out of scope

- Artifact Hub API shape, search semantics, debounce timing, pagination contract, caching, or backend routes.
- Installation jobs, Helm commands, status polling, authorization, validation rules, release actions, or audit behavior.
- Background-jobs history redesign outside the Marketplace install flow.
- New routes, persisted data, database migrations, new dependencies, or a new visual theme.
- Broad dashboard-shell redesign or changes to Marketplace release management.

## Build loop

Implement one small step at a time. The configured workflow uses feature-level
review (`workflow.stepReview: "feature"`) and checkpoint commits are disabled;
present one review packet after all steps pass. `/complete` owns the final feature
commit and merge flow.

## Build steps

- [x] **1. Establish the responsive Marketplace layout.** Update the Marketplace page/browser composition and package-card layout to use the existing semantic Tailwind tokens and shadcn controls. Stack the search and sort controls cleanly on narrow screens, keep the grid at one column on mobile with denser tablet/desktop columns, and prevent package metadata or actions from clipping or colliding.

  **Done when:** `/marketplace` retains its current search, sort, pagination, package-detail, and Install actions; the toolbar and package grid are usable at mobile, tablet, and desktop widths; no horizontal overflow is introduced; `yarn verify` passes.

- [x] **2. Add complete discovery-state presentation.** Replace the browser’s generic loading spinner with reusable `Skeleton`-based package placeholders that match the final card geometry. Preserve the existing `Empty` and retry behavior for no results and initial failures, and make refresh failures visible without losing already-rendered package results when possible. Keep loading and pagination controls disabled while their request is active.

  **Done when:** initial loading, successful results, no-match results, initial API failure, retry, and refresh-failure states are visually distinct and accessible; package skeletons do not shift the finished grid substantially; errors remain concise and actionable; `yarn verify` passes.

- [x] **3. Polish package details and installation feedback responsively.** Make the details and install dialogs fit narrow viewports, keep their content scrollable without clipping the title or actions, and allow metadata, descriptions, repository names, validation messages, and job status text to wrap safely. Reuse the installed `Dialog`, `Button`, `Badge`, `Alert`/existing alert treatment, `Select`, and `Skeleton` primitives and their existing animation behavior. Preserve explicit Install confirmation, validation, queued/running/succeeded/failed/cancelled states, retry behavior for status-fetch errors, and the rule that closing progress UI does not cancel an installation.

  **Done when:** package details and install/progress dialogs can be opened, read, submitted, closed, and retried at narrow and wide widths without clipped content or inaccessible controls; status changes remain announced through the existing live regions; reduced-motion users do not receive forced animation; `yarn verify` passes.

- [x] **4. Complete responsive and accessibility proof.** Review the finished Marketplace flow in the deployed Minikube UI at representative mobile, tablet, and desktop viewport sizes, including long package names/descriptions, missing logos, no results, API errors, and an active installation. Check keyboard focus order, visible focus rings, labels, dialog focus management, semantic status/error announcements, and touch target usability. Record any browser-observable limitation without changing unrelated routes.

  **Done when:** manual browser review confirms the responsive package discovery and install flow at the required viewport classes, with no new overflow, clipped dialogs, unreachable actions, or missing applicable states; the final declared Verify command has been run and its result recorded for `/complete`.

## Files / areas

- `k8s-ui/components/marketplace-view.tsx` — Marketplace page heading and shell content spacing.
- `k8s-ui/components/marketplace-browser.tsx` — search/sort toolbar, loading/error/empty states, package grid, pagination, and dialog orchestration.
- `k8s-ui/components/package-card.tsx` — responsive card structure, metadata, logo fallback, details activation, and Install action.
- `k8s-ui/components/package-details-dialog.tsx` — responsive package metadata and Helm information dialog.
- `k8s-ui/components/install-dialog.tsx` — responsive installation form and installation progress states.
- `k8s-ui/components/ui/skeleton.tsx`, `empty.tsx`, `alert.tsx`, `dialog.tsx`, `button.tsx`, `select.tsx`, and `badge.tsx` — reuse existing primitives; edit a primitive only if its current API or animation classes require a minimal compatible adjustment.
- `k8s-ui/app/globals.css` — use existing theme tokens and reduced-motion rules; change only if a shared, repository-native rule is required by this feature.

No changes are expected in `k8s-ui/app/api/marketplace/**`, backend Marketplace services, or persistence files.

## Data / contracts

- No new models, fields, routes, query parameters, or persisted state.
- Keep the existing package response fields and `MarketplacePackage` type unchanged.
- Keep the existing package search request, Artifact Hub filtering, debounce, pagination, cache, and abort behavior unchanged.
- Keep package-card detail selection and Install callbacks unchanged; clicking Install must not also open package details.
- Keep installation requests and job polling unchanged. A queued installation remains queued/running until the backend reports a terminal state; the UI must never infer success from closing a dialog.
- Render package and server error text as text only. Do not interpret Artifact Hub descriptions, repository metadata, Helm commands, or error strings as HTML or executable input.
- Use semantic theme tokens (`bg-card`, `bg-muted`, `text-foreground`, `text-muted-foreground`, `border-border`, and component variants), not hard-coded light/dark colors.
- Use `gap-*` layout utilities, `size-*` for equal dimensions, `truncate` where a single-line label is intended, and `cn()` for conditional class composition in line with the shadcn project rules.
- Loading placeholders use the installed `Skeleton`; empty results use `Empty`; actionable failures use the existing alert treatment; statuses use `Badge`.
- Preserve keyboard-accessible full-card details activation, a separately reachable Install button, visible focus treatment, dialog titles, labelled search/sort controls, and `aria-live`/`role="status"` or `role="alert"` semantics already used by the flow.

## Testing

- Automated gate: run the exact project Verify command before completion:
  `cd backend && .venv/bin/python3 -m pytest && cd ../k8s-ui && yarn verify`.
- The first planning pass attempted this command and collected 536 backend tests, but it remained silent for roughly two minutes and was interrupted before completion; this is not passing evidence. Implementation must rerun it and record the actual result.
- The corrected combined command completed the backend portion with `536 passed in 328.39s`; the frontend `yarn verify` then reached Turbopack but was blocked by the managed environment’s process/port permission error. The final fallback gates passed in the completion session: `.venv/bin/python3 -m pytest` completed with `536 passed in 380.96s`, and `yarn next build --webpack` completed successfully with TypeScript and all 37 generated pages. Touched-file ESLint also passed with two existing image warnings. The declared Verify command remains environment-blocked, while its fallback build and tests pass.
- Manual Minikube validation: user confirmed the deployed Marketplace flow passes the responsive and accessibility review against the live cluster environment.
- No browser test runner is configured. Use direct browser review against the deployed Minikube UI/image for responsive behavior and state coverage; do not add a browser harness as part of this feature. The local `yarn dev` runtime is not authoritative because it cannot access the live cluster context used for this feature.
- If pure state/formatting helpers are extracted, add focused tests only if they can use the project’s existing test setup without introducing a new runner.

## Notes for the AI

- The current app is a Next.js 16 App Router frontend with Tailwind v4 and shadcn components on the existing Base UI setup. Keep client directives where state/effects/event handlers require them.
- The project’s shipped UI direction is the light palette with optional dark mode from feature 16/17. Preserve both themes through semantic tokens even though the older project plan contains dark-first wording.
- The Marketplace backend and job flow are already shipped. Treat this as a presentation and responsive-composition feature, not an opportunity to repair or reinterpret API behavior.
- Follow the installed shadcn composition rules: compose existing primitives, use `Skeleton`/`Empty`/`Badge`/`Alert` where applicable, keep Dialog titles, avoid custom animation systems, and do not add dependencies without a separately approved scope.
- Do not start a local development server for proof. The authoritative manual check is the branch image rebuilt through the existing GitHub Actions flow and redeployed to Minikube, where the UI can access live cluster data.
