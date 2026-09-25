# Remove obsolete Settings sections

**Type:** Fix

**Status:** verified

**Branch:** `fix/remove-obsolete-settings-sections`

## The problem

The protected Settings area still presents `Overview`, `General`, and
`Appearance`, but these sections are no longer needed. It also presents a
planned `AI Agents` item even though future agent workflows belong with the
existing AI Assistant experience. These entries leave an outdated information
architecture in Settings.

## The fix

Remove `Overview`, `General`, and `Appearance` from the Settings navigation and
retire their dedicated pages and form components. Keep `/settings` as a valid
entry point by redirecting it to the first retained section, AI Providers. Keep
planned Integrations in Settings, but remove the planned AI Agents item and
record future agent workflows under the existing Assistant area. Do not change
the remaining Settings sections or the separate user, password, and cluster
settings routes.

## Build steps

- [x] Remove the obsolete Settings navigation entries and surfaces, and make
  `/settings` redirect to `/settings/providers`.
  - **Done when:** the Settings section navigation starts with `AI Providers`;
    `Overview`, `General`, `Appearance`, and `AI Agents` are absent; their
    obsolete dedicated routes and components are removed; `Integrations`
    remains planned in Settings; and the remaining navigation behaves as
    before.

## Verify

- Run `./scripts/verify-feature.sh`.
- Confirm `/settings` redirects to `/settings/providers`.
- Confirm the Settings navigation contains no `Overview`, `General`, or
  `Appearance` entries, contains no planned `AI Agents` entry, and still shows
  planned `Integrations` alongside all retained section links.

**Verification result:** `./scripts/verify-feature.sh` passes. It skips backend
pytest because this fix has no backend changes, passes all 13 Assistant tests,
and completes the Next.js 16.3.3 Turbopack production build, TypeScript check,
and static page generation with only the retained Settings routes.
