# Feature 22b - Integrations catalog UI foundation

**Type:** Feature

**Branch:** `feature/integrations-catalog-ui-foundation`

**Status:** verified

## Goal

Give administrators a clear, searchable Integrations catalog inside the protected Settings area. The page should make connected versus available services easy to scan and establish the visual and interaction foundation for later backend connector work without pretending that local preview state is a real external connection.

## Design reference

The layout follows the selected catalog direction from the approved visual exploration, grounded in the supplied KubePilot reference: [settings-providers-integrations.png](../reference/settings-providers-integrations.png). Preserve the existing light operational shell, teal header, left navigation, blue/teal accents, readable typography, compact status badges, and responsive desktop-first spacing.

## In scope

- Add the protected `/settings/integrations` page inside the existing admin Settings route group.
- Replace the inert planned Integrations label in `SettingsShell` with a real active link and active-page state.
- Present catalog entries for Slack, Microsoft Teams, Gmail, Microsoft Outlook, GitHub, and Webhooks.
- Group entries into Connected and Available integrations with initial local preview state showing Slack and GitHub as connected.
- Show service name, purpose, connection status, security hint, and one primary action per catalog entry.
- Add category filters for All, Notifications, Communication, Source Control, and Automation.
- Add case-insensitive search across service name, category, and description with a clear no-match state.
- Add local preview feedback for Connect, Manage, Learn more, documentation, and request-an-integration actions; clearly explain that these actions are not persisted or authorized against an external service yet.
- Preserve inherited admin authorization, loading, and unexpected-error behavior from the existing Settings route group and keep the page usable at narrow widths and in supported themes.

## Out of scope

- OAuth, API-key entry, webhook secret entry, connection testing, provider callbacks, delivery execution, or external-service API calls.
- Backend routes, database records, encrypted credential changes, audit events, or persistence for integrations.
- Real connection health, delivery history, permissions negotiation, or notification routing.
- Configurable Kubernetes AI agent workflows; those remain feature 22d under `/assistant` and must not add an AI Agents item to Settings.
- New browser-test infrastructure or a new visual asset pipeline. Use the existing Lucide icon library for this foundation rather than adding unapproved brand-logo assets.

## Build loop

Configuration uses feature-level review (`workflow.stepReview: "feature"`) with checkpoint commits disabled. Keep the page buildable after each step. `/complete` owns the final feature commit and plan archival.

## Build steps

- [x] **1. Activate the protected Integrations route and navigation.** Add the page entry under `app/settings/(admin)/integrations/page.tsx` and make Integrations a real SettingsShell link without changing the separate clusters, users, or password routes.

  **Done when:** an authenticated admin can resolve `/settings/integrations` through the existing admin layout; the Integrations link is active only on that path; the existing route boundary continues to handle anonymous and non-admin access; `yarn verify` passes.

- [x] **2. Build the catalog model and connected/available cards.** Add a focused client component with the six planned catalog entries, their categories, descriptions, security hints, icons, initial local connection state, status badges, and responsive card layout.

  **Done when:** the default page visibly shows two connected entries and four available entries; each card has an actionable primary button; no credential, cookie, environment value, or fake backend response is rendered; the existing Settings visual tokens and primitives are reused.

- [x] **3. Add search, category filtering, and preview feedback.** Implement the category button group, search field, filtered counts, no-match messaging, and local-only action feedback for Connect, Manage, Learn more, documentation, and request actions.

  **Done when:** category changes and search update both sections without navigation or network calls; no-match results are announced clearly; Connect changes only local preview state and explicitly says backend authorization is not implemented; controls expose labels, pressed state, and live status feedback.

- [x] **4. Preserve states, responsive behavior, and scope boundaries.** Verify that the page composes with the existing Settings loading/error route boundaries, remains readable at narrow widths, and does not pull forward backend connector or AI-agent behavior.

  **Done when:** loading, denied, unexpected-error, normal, empty-filter, and local-feedback outcomes have an observable treatment using the existing route/component patterns; Settings navigation outside Integrations remains unchanged; no unsupported connector claim appears in the UI.

- [x] **5. Run the verification gate and review the diff.** Run the documented frontend Verify command, lint, and diff checks, then record any unavailable browser evidence separately.

  **Done when:** `cd k8s-ui && yarn verify`, `cd k8s-ui && yarn lint`, and `git diff --check` pass; the changed-file set is limited to the Integrations catalog, Settings navigation, and required generated workflow context; no visual/browser pass is claimed unless a rendered implementation can be captured.

## Files / areas

- `k8s-ui/app/settings/(admin)/integrations/page.tsx` - protected page entry.
- `k8s-ui/components/settings-shell.tsx` - real Integrations link and active state.
- `k8s-ui/components/settings-integrations-view.tsx` - catalog data, layout, filters, search, local preview actions, and accessible feedback.
- `k8s-ui/app/settings/(admin)/layout.tsx`, `loading.tsx`, and `error.tsx` - existing authorization and route-state boundaries to preserve.
- `k8s-ui/components/ui/{card,button,badge,input}.tsx` - existing primitives and styling contracts.

## Data / contracts

- No backend or persistence contract is introduced in 22b.
- The client-only catalog model contains `id`, `name`, `category`, `description`, `securityHint`, icon metadata, and presentation classes.
- Categories are the stable UI values `All`, `Notifications`, `Communication`, `Source Control`, and `Automation`.
- Local preview connection state starts with `slack` and `github` connected and all other entries not connected. Refreshing the page resets this state.
- Connect, Manage, Learn more, documentation, and request actions produce safe local status text only. They must not call an API or imply that an external account was authorized.
- Settings authorization remains server-side through the existing `requireAdminSettingsUser` route-group layout. This feature does not trust browser role claims or add a new permission.
- User-controlled search text is rendered only as input state and used for in-memory filtering; it is never injected as HTML or sent to a backend.

## Testing

- `cd k8s-ui && yarn verify` - required production build and TypeScript/static route verification.
- `cd k8s-ui && yarn lint` - required lint check; pre-existing warnings remain non-blocking unless new findings appear in the feature files.
- `git diff --check` - whitespace and patch sanity.
- No browser test command is configured. Manual/browser visual evidence is optional under `verification.uiEvidence: "when-available"`; do not report it as completed when the runtime or browser surface is unavailable.
- Verification evidence: the user-provided final `./scripts/verify-feature.sh` run passed the 13-test Assistant suite and the declared Turbopack production build, generating `/settings/integrations`. `yarn lint` passed with 13 pre-existing warnings, and `git diff --check` passed. A restricted local rerun intermittently hit an environment-only Turbopack worker/port-binding `Operation not permitted` error; no feature-specific compile or TypeScript error was observed. Browser visual evidence remains unavailable because the dev server cannot bind in this environment.

## Notes for the AI

- Keep this slice honest and frontend-only. The page is a catalog foundation, not a mock integration backend.
- Preserve the distinction between Settings-managed credentials and future connector authorization. Never add secret fields or environment-variable reads here.
- Keep AI agent workflows under the existing Assistant surface; do not reintroduce an AI Agents Settings entry.
- Reuse the current DashboardShell, SettingsShell, Tailwind tokens, Base UI/shadcn primitives, and Lucide icons. Avoid broad shell refactors.
- If real connector behavior is requested later, plan it as feature 22c with explicit backend contracts, authorization, encrypted credential references, connection lifecycle, delivery semantics, and audit coverage.
