# Feature 22d6 - AI Agents UI polish

**Type:** Feature
**Build plan:** 22d6
**Branch:** `feature/ai-agents-ui-polish`
**Status:** verified

## Goal

Make the existing `/assistant/agents` management experience easier to scan, safer to edit, and usable at narrow widths without changing agent behavior, backend contracts, permissions, or automation execution. The page should retain its calm operational visual language while reducing the long-form density visible in the current AI Agents screenshot.

## Design reference

- [Current AI Agents management screenshot](../reference/127.0.0.1_36801_assistant_agents.png) - baseline evidence for the excessive vertical length, narrow content column, repeated cards, small status text, and bottom-only actions that this feature addresses.
- The target is a responsive refinement of the existing KubePilot shell and shadcn/ui language, not a visual clone or a new design system.

## In scope

- Responsive AI Agents layout:
  - preserve a two-pane library/editor experience at wide desktop widths;
  - stack or transition between the agent library and editor at narrow widths so the selected agent is readable and the user can return to the list without horizontal overflow;
  - keep the existing dashboard shell, navigation labels, cluster selection, route, and namespace context intact;
  - make the shared sidebar usable at the narrow widths relevant to this screen without redesigning navigation for unrelated routes.
- Clearer page hierarchy:
  - distinguish page header, agent library, selected-agent summary, basic configuration, model state, capabilities, notifications, and automation;
  - reduce unnecessary nested cards and use consistent section containers or collapsible sections;
  - keep the existing Agents, Skills, and Templates navigation understandable and keyboard usable.
- Capability management that scales:
  - group the existing tool assignments by operational purpose in the UI, with a safe `Other` group for an unknown future tool ID;
  - keep skill and tool selection semantics, IDs, descriptions, and server validation unchanged;
  - make long capability groups collapsible and expose selected counts or equivalent summary text without hiding unavailable selections.
- Model and status clarity:
  - show the model friendly name and provider as the primary identity, never an opaque model ID in the visible summary;
  - present missing, disabled, unavailable, conversational-only, and tool-supported states with plain-language explanations and an actionable Settings link where one already exists;
  - explain why enabling an agent is unavailable when its model or effective tool configuration cannot support it;
  - preserve stored disabled assignments visibly so the UI does not silently rewrite configuration.
- Editing confidence:
  - provide a sticky or otherwise persistently reachable action area for Save, Discard/Cancel, Run where available, and Delete where authorized;
  - make dirty, saving, uncertain, denied, success, and deletion-confirmation states explicit;
  - preserve the existing refresh-before-retry behavior for uncertain mutations and the existing destructive deletion confirmation.
- Accessible states and interaction:
  - retain or improve labels, descriptions, error associations, live status announcements, keyboard focus treatment, and focus movement to the first invalid field;
  - ensure controls have usable hit areas and visible selected, disabled, focused, and pending states;
  - cover loading, empty library, no search results, catalog metadata failure, access denied, missing model, unavailable model, disabled agent, and unexpected save/delete failure states with concise actionable copy.

## Out of scope

- Backend, database, migration, API route, response schema, RBAC, audit, notification, scheduler, or agent execution changes.
- New agent tools, skills, templates, model capabilities, integrations, automation triggers, or Background Jobs behavior.
- Changes to the Assistant conversation experience or to manual approval semantics.
- A global navigation information-architecture redesign; shared shell changes are limited to making this existing screen usable at narrow widths and must not alter unrelated route behavior.
- A new component library, dependency, design-token system, or visual clone of the supplied reference.
- Browser-test harness setup. Manual browser review is expected when a running app is available; repeatable browser automation remains a separate task.

## Build loop

Implement on `feature/ai-agents-ui-polish`. Keep each step small and leave the page buildable after every step. Because `workflow.stepReview` is `feature` and checkpoint commits are disabled, run the focused checks during implementation and stop for one feature-level review packet before `/complete`. Do not commit, merge, push, or deploy during `/implement`.

## Build steps

1. [x] **Define presentation states and responsive page structure**

   Extract or add focused frontend-only helpers for model/status summaries, tool grouping, selected-count summaries, and the dirty/uncertain editing state where that keeps `view.tsx` and `editor.tsx` readable. Reshape the Agents page so wide screens retain library-plus-editor hierarchy while narrow screens present one clear pane at a time with a visible return path. Preserve the existing route, data loading, and API contracts.

   **Done when:** the existing agent list, selection, search, loading, empty, denied, and catalog-error flows render through the new hierarchy without horizontal overflow at narrow widths; friendly model/provider identity and safe fallback states are available to the editor; `yarn test:assistant` and `yarn verify` pass.

2. [x] **Reduce configuration density and group capabilities**

   Rework the editor’s basic information, model, skills, tools, notifications, and automation sections into a scannable section hierarchy. Replace the flat tool wall with stable client-side operational groups and collapsible sections, preserve unknown tools under `Other`, and show selected/unavailable counts or equivalent summaries. Keep selected unavailable assignments visible and editable rather than silently removing them.

   **Done when:** an administrator can find and change identity, model, skills, tools, notifications, and automation without scanning one uninterrupted card; tool selection still submits the same IDs and existing agent API behavior is unchanged; empty catalogs and metadata failures remain understandable; the Assistant test suite and production build pass.

3. [x] **Add persistent actions and clear model/editing states**

   Add a sticky or persistently visible action treatment for save/discard/run/delete that works on long forms and narrow screens. Add a clear dirty-state indicator, explicit discard/reset behavior, saving/saved feedback, and actionable model/enablement explanations. Keep delete confirmation, access-denied handling, uncertain mutation reconciliation, and existing navigation guards intact.

   **Done when:** users can save or discard a long edit without returning to the bottom of the page; unavailable or missing models explain the blocking condition and link to model management when authorized; keyboard users receive equivalent action and status feedback; existing API bridge tests and `yarn verify` pass.

4. [x] **Polish visual consistency and verify the UI states**

   Apply the existing Tailwind/shadcn visual language with fewer competing borders, readable helper/status text, consistent status badges, visible focus rings, and appropriately sized controls. Review the current screenshot’s narrow layout and a wide desktop layout, then verify all applicable loading, empty, error, disabled, denied, pending, and success states without changing backend behavior.

   **Done when:** the AI Agents screen is visually scannable at narrow and wide widths, the supplied baseline problems are addressed, no new horizontal scroll or clipped action state appears, and the final `./scripts/verify-feature.sh` passes. Record any browser/runtime limitation rather than claiming visual evidence that was not captured.

## Files / areas

- `k8s-ui/components/assistant/agents/view.tsx` - page header, library/editor relationship, responsive pane behavior, tabs, loading, empty, and route-level error states.
- `k8s-ui/components/assistant/agents/editor.tsx` - configuration hierarchy, model/enablement state, capability presentation, dirty actions, and accessibility behavior.
- `k8s-ui/components/assistant/agents/automation.tsx` and `notifications.tsx` - consistent section density, status summaries, and long-form panel treatment without changing their API behavior.
- `k8s-ui/components/assistant/agents/catalog.tsx` - only where the shared Agents/Skills/Templates presentation needs matching hierarchy or empty/error treatment.
- `k8s-ui/components/dashboard-shell.tsx` - only the minimum responsive shell/sidebar adjustment needed for the AI Agents screen; preserve unrelated route layout.
- `k8s-ui/lib/assistant/agents.ts` or a focused adjacent UI helper - only for pure presentation-state/grouping contracts that should not remain embedded in large JSX blocks.
- `k8s-ui/tests/agents.test.mjs` - focused assertions for any pure state/grouping/serialization helper added during the implementation; do not add brittle snapshot tests for visual layout.
- `blueprint/reference/127.0.0.1_36801_assistant_agents.png` - supplied before-state reference for manual comparison.

## Data / contracts

- The existing `AgentDefinition`, `AgentModel`, `AgentSkill`, `AgentTool`, notification, and automation response schemas remain unchanged. No new server fields or endpoints are required.
- Visible model identity uses `friendly_name` and `provider_name`; internal model IDs remain transport values only.
- The UI derives safe model state from existing fields: missing model, disabled model, unavailable model, available conversational model, or available tool-capable model. The derivation must be deterministic and covered if extracted as a helper.
- Tool groups are presentation-only. The grouping map keys known existing tool IDs, places unknown IDs in `Other`, and never changes the submitted `tool_ids` array or backend authorization.
- Selected capability assignments remain visible even when their effective status is unavailable. The UI may disable interaction that the current model cannot support, but must explain the reason and must not silently mutate stored selections.
- Dirty state is based on the existing draft/baseline comparison. Save sends the existing agent write payload; discard restores the last persisted baseline; uncertain failures retain the draft and offer the existing refresh/reconciliation path.
- Authorization remains server-authoritative. Admin-only controls stay hidden or disabled according to the existing `editable`/denied contract; visual changes must not imply permissions that the backend does not grant.
- User-controlled names, descriptions, instructions, tool descriptions, and status/error messages continue to use the existing safe React rendering and bounded field validation. No raw provider payload, credential, prompt, or tool result is added to the UI.

## Testing

- Preserve and run the existing Assistant/agent Node test suite through `yarn test:assistant` and the repository gate `./scripts/verify-feature.sh`.
- Add focused Node assertions only for new pure presentation helpers or state contracts; do not test Tailwind class strings as a substitute for visual review.
- Run `yarn verify`/Next production build after the UI changes and confirm the existing Agent routes compile without backend changes.
- Manually review `/assistant/agents` at a wide desktop viewport and a narrow/mobile-width viewport when a running app is available: list-to-editor navigation, sticky actions, grouped capabilities, model-unavailable state, dirty/discard flow, loading/empty/error states, keyboard focus, and no horizontal overflow.
- Browser automation is not configured and remains out of scope. Screenshot evidence must be identified as manual evidence only when it is actually captured.
- Planning baseline observed before implementation: `./scripts/verify-feature.sh` skipped backend tests because no backend changes were present, passed all 28 frontend Assistant tests, and passed the Next production build. This is baseline evidence, not feature completion evidence.

## Notes for the AI

- Start from the supplied screenshot’s problems: the page is too tall, the narrow layout leaves too little content width, repeated cards create noise, the tool wall is difficult to scan, and Save/Delete are too far away.
- Prefer existing shadcn/ui primitives, Tailwind breakpoints, `cn`, `Card`, `Alert`, `Badge`, `Button`, `Field`, `Separator`, and existing loading/empty patterns before introducing new primitives.
- Keep the calm light operational palette and strong status emphasis. Improve hierarchy and density through grouping and spacing rather than decorative redesign.
- Do not rewrite backend contracts to add categories, friendly model fields, or UI-only status values. Derive these from existing data and keep server validation authoritative.
- Treat the current screenshot as a before-state reference. The desired result is a responsive, readable management workflow, not a pixel-perfect recreation of another product.
