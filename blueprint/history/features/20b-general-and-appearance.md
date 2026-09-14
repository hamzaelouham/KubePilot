# Current Feature

**Status:** verified
**Branch:** `feature/settings-general-and-appearance`

## Goal

Implement the first real Settings subsections for the existing KubePilot Settings shell:

- `/settings/general` exposes only the repository-confirmed runtime preference for the current authenticated user: `default_namespace`.
- `/settings/appearance` manages the existing `next-themes` preference with `System`, `Light`, and `Dark` options.
- Both preferences persist through the existing PostgreSQL-backed `UserPreference` record and survive browser reloads and backend/pod restarts.
- The existing user-menu theme control and the new Appearance page use one shared theme mechanism.

The implementation must keep Kubernetes/bootstrap configuration separate from mutable KubePilot preferences. Values such as database URLs, session/authentication secrets, cluster bootstrap settings, and future encryption keys remain Kubernetes-managed and are not editable or enumerated by this UI.

## Design reference

Use the supplied KubePilot screenshots only as light visual inspiration for the Settings content. The existing KubePilot layout, sidebar, shell, responsive behavior, typography, colors, spacing, and navigation chrome remain authoritative and must not be redesigned or replaced.

- [General Settings reference](/home/devops/test-project/blueprint/reference/settings-general.png)
- [Providers and Integrations reference](/home/devops/test-project/blueprint/reference/settings-providers-integrations.png)
- [AI Agents reference](/home/devops/test-project/blueprint/reference/settings-ai-agents.png)
- [AI Agent creation reference](/home/devops/test-project/blueprint/reference/settings-ai-agents-create.png)
- [AI Agent capabilities/templates reference](/home/devops/test-project/blueprint/reference/settings-ai-agents-capabilities-templates.png)

For 20b, preserve the current layout and carry forward only compatible content patterns where they already fit: Settings title/icon/description, secondary navigation, rounded bordered cards, restrained status accents, clear form alignment, and separated read-only or destructive sections. Do not add a second header/sidebar, move existing global navigation, or force the screenshot's dimensions, chrome, or page composition. Keep the implementation responsive and consistent with the actual KubePilot shadcn/ui tokens.

The reference's application name/description, default cluster, deployment metadata, database status, reset action, provider cards, integrations, and AI-agent controls are not automatically in scope for 20b. Add only repository-confirmed behavior described below; later Settings features may use the same composition.

## In scope

- Add working General and Appearance destinations to the existing Settings secondary navigation while leaving later sections visibly planned.
- Keep both pages inside the existing protected Settings route group and preserve the 20a admin page access behavior.
- Add a narrow, typed preferences service/API that reads and updates only the current actor's preferences; do not expose raw `view_settings` JSON for arbitrary mass assignment.
- Persist `default_namespace` using the existing `user_preferences.default_namespace` column.
- Persist the supported theme value inside the existing `user_preferences.view_settings` JSON without discarding unrelated future view settings.
- Reuse the existing `ThemeProvider`, `useTheme`, theme values, shadcn/ui controls, loading/error/empty feedback, and toast conventions.
- Keep the user-menu theme selector functional and synchronize its selection with the same preference persistence used by Appearance.
- Validate preference payloads server-side, reject unknown fields, constrain writes to the authenticated actor, and avoid returning or logging any secret material.
- Add focused backend tests for preference authorization, strict payload validation, persistence/merge behavior, and safe responses, plus frontend type/build verification as supported by the repository.

## Out of scope

- A generic environment-variable editor or any UI/API for bootstrap infrastructure settings.
- Global application settings, provider credentials, AI providers/models, integrations, secrets, audit-log UI, or AI Agents; those remain the later 20c–20g work items.
- A new theme provider, a second client-side preference store, custom encryption, or a new database table/migration when the existing `UserPreference` schema is sufficient.
- User-facing self-service route changes outside the existing user-menu behavior; non-admin users must continue to be denied the administrative `/settings/*` pages by both frontend and backend authorization.
- Changing cluster selection or Kubernetes API behavior beyond applying the already-persisted default namespace preference where an existing consumer supports it.

## Build loop

1. Implement one small step.
2. Run the focused backend tests for the preference contract and the frontend verification command when the affected step is complete.
3. Review the changed diff for authorization, preference scoping, theme hydration, and preservation of existing Settings/sidebar behavior.
4. Continue only after the step's observable Done when is satisfied.

## Build steps

### 1. [x] Establish the typed preferences contract and service

Add a backend service/repository boundary around the existing `UserPreference` model. Expose a deliberately narrow read/update contract for `default_namespace` and the supported theme value, merge the theme into `view_settings` without overwriting other JSON keys, create a preference row when the current user has none, and reject unknown fields or invalid values. Use the current authenticated actor as the only writable target. Keep this preference endpoint distinct from future admin-wide Settings configuration.

Done when:

- A current authenticated user can read only their own normalized preferences and receives a safe response containing no raw secret/configuration data.
- Updates accept only the documented typed fields, preserve unrelated `view_settings`, validate `default_namespace` using the project's Kubernetes namespace rules, and persist across a new database session.
- Unauthenticated requests, malformed payloads, unknown fields, and attempts to address another user are rejected by the backend's existing error/auth conventions.
- No bootstrap environment variable is read as an editable runtime setting and no migration is added unless inspection of the existing schema proves it is required.

### 2. [x] Build the General Settings page

Create the General page under the existing admin Settings route group. Use the existing shell and shadcn/ui form patterns to load and save the current user's confirmed default namespace preference. Include concise boundary copy explaining that deployment/bootstrap configuration is managed by Kubernetes, without listing or editing arbitrary environment variables. Preserve loading, unavailable-data, validation, save-success, save-failure, and denied states.

Done when:

- An administrator can navigate to `/settings/general`, see the persisted default namespace, update it or clear it, and observe the value after reload.
- A non-admin cannot render the page through direct navigation, and the backend still enforces authentication/scoping if the API is called manually.
- The page does not present invented application settings or generic infrastructure environment variables.

### 3. [x] Build the Appearance Settings page and shared theme persistence

Create `/settings/appearance` using the existing Settings layout. Extract or share the current user-menu theme options/control so both surfaces use `System`, `Light`, and `Dark` from the existing `next-themes` provider. Load the persisted preference safely during client hydration, apply it through `useTheme`, and persist changes through the typed preference API. Keep the current local fallback behavior if persistence is temporarily unavailable and provide visible save/error feedback according to existing UI conventions.

Done when:

- The Appearance page offers exactly the existing System/Light/Dark choices, applies the selected theme immediately, and restores it after a reload/session refresh.
- Selecting a theme from the user menu remains functional and updates the same persisted preference rather than creating a second storage system.
- System theme behavior continues to respect the existing `enableSystem` configuration, and no hydration warning or theme flash regression is introduced beyond the current implementation.
- Loading, unavailable preference, save failure, and unauthorized states are handled without breaking the Settings shell.

### 4. [x] Connect navigation and verify the feature boundary

Update the Settings navigation's active-link behavior for General and Appearance, retain planned states for unimplemented sections, and verify that the new routes do not alter the existing legacy Settings routes or application layout. Add/adjust focused tests and run the supported checks.

Done when:

- General and Appearance links render with the existing Settings visual language and active state; later sections remain non-functional/planned until their feature items are implemented.
- Existing authentication/session behavior, user-menu actions, light/dark/system switching, and legacy Settings routes remain intact.
- Focused backend tests pass, frontend `yarn verify` passes, and any broader Verify limitation is recorded with the exact observed command/result.

## Files / areas

- `backend/app/api/v1/settings.py` and the existing backend settings/auth dependency conventions.
- `backend/app/models/entities.py` and the existing `UserPreference` persistence model; existing application-schema migration only if needed.
- A focused backend settings/preferences service, schemas, and tests under the project's existing module conventions.
- `k8s-ui/app/settings/(admin)/` for the General and Appearance pages, loading/error states, and route composition.
- `k8s-ui/components/settings-shell.tsx` for navigation and active-link behavior.
- `k8s-ui/components/theme-provider.tsx`, `k8s-ui/components/user-menu.tsx`, and a shared preference/theme control or hook as appropriate.
- Existing frontend API proxy/client conventions for authenticated backend calls.
- `blueprint/context/project-overview.md` only if implementation reveals a durable architecture fact that is not already documented.

## Data / contracts

The frontend may call a same-origin preferences route that proxies the backend API. The backend contract is intentionally narrow and should be represented by strict Pydantic/TypeScript types:

```text
GET   /api/v1/settings/preferences
PATCH /api/v1/settings/preferences

response:
{
  default_namespace: string | null,
  theme: "system" | "light" | "dark"
}

update body (partial):
{
  default_namespace?: string | null,
  theme?: "system" | "light" | "dark"
}
```

The API must not accept arbitrary environment names or arbitrary JSON keys. Internally, `theme` maps to the existing `UserPreference.view_settings` JSON and updates must preserve unknown/future view-settings keys. `default_namespace` maps to the existing nullable database column. The endpoint is authenticated and actor-scoped; the administrative page remains protected by the existing admin Settings guard. Preference changes are not credential changes and must not put secrets into responses, logs, or audit context.

Configuration precedence remains unchanged for this feature: Kubernetes/bootstrap configuration is resolved by the existing backend environment configuration, while these user-scoped mutable preferences come from `UserPreference`, with existing safe UI/application defaults (`system` theme and no default namespace) when no row/value exists.

## Testing

- Backend: focused pytest coverage for authenticated own-user GET/PATCH, unauthenticated access, strict/invalid payloads, namespace clearing, theme values, row creation, persistence, and preservation of unrelated `view_settings`.
- Frontend: TypeScript/build verification through `cd k8s-ui && yarn verify`; verify route generation includes `/settings/general` and `/settings/appearance`.
- Manual review: as an admin, exercise navigation, save/reload for both preferences, user-menu theme switching, system theme behavior, and error/empty states; as a non-admin, confirm direct `/settings/general` and `/settings/appearance` navigation is denied.
- Existing evidence at planning time: `cd k8s-ui && yarn verify` passed on the current `master` tree (Next.js 16.3.3, TypeScript, static generation, exit code 0). The repository-wide backend Verify remains slow in `tests/test_assistant.py`; do not use that known limitation to weaken focused 20b tests.

## Notes for the AI

- Inspect and reuse existing auth, session, SQLAlchemy, schema, API proxy, toast, form, and theme conventions before adding helpers.
- Keep the Settings shell's current layout, typography, colors, spacing, sidebar, and dark/light behavior. This is an incremental settings surface, not a visual redesign.
- Treat `UserPreference` as user-scoped because the existing schema has a unique `user_id`; do not silently turn it into global application configuration. Global runtime settings belong in the planned centralized settings service work.
- Never return existing secrets, expose raw `view_settings` for client mutation, or accept an arbitrary provider/URL/environment identifier in this feature.
- Preserve unknown JSON preference keys when updating the known theme key so later Settings features can extend the record safely.
