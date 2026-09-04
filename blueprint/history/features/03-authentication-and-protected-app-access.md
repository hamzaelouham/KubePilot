# Authentication and protected app access

**Branch:** feature/authentication-and-protected-app-access

## Goal

Add a real authentication layer to the KubePilot app so the dashboard is no longer reachable by a demo link alone. The feature should protect sensitive operational views behind local sign-in, maintain a session for signed-in users, and route unauthenticated users back to the login screen with a clear redirect flow.

## Design reference

The current app already establishes the visual direction for the product and gives an obvious place to wire in access control:

- Login screen: `k8s-ui/app/login/page.tsx`
- Dashboard shell: `k8s-ui/components/dashboard-shell.tsx`
- Dashboard route: `k8s-ui/app/dashboard/page.tsx`
- Landing page: `k8s-ui/app/page.tsx`

The current implementation is intentionally demo-like: the login page accepts a mocked email/password pair and links directly into the dashboard. This feature replaces that demo behavior with an authenticated app shell and a protected route model.

## In scope

- Local sign-in flow for the app using a lightweight, repository-native session model
- Session creation and validation for authenticated users
- Redirect from protected pages to the login page when no valid session exists
- Redirect from login to the dashboard when a user is already signed in
- Session expiry and sign-out behavior for the app shell
- Guarding the dashboard route and any future protected cluster pages behind server-side checks
- Clear error handling for invalid credentials, expired sessions, and missing auth state

## Out of scope

- Multi-user RBAC or role-based permissions beyond a simple admin/operator model
- Real Kubernetes RBAC synchronization
- OAuth providers, SSO, or external identity integrations
- AI Copilot features or advanced cluster actions
- Database-backed user management beyond a minimal local admin account configuration for the next implementation phase
- Multi-cluster support or cluster-level authorization logic

## Build loop

This feature follows the existing workflow configuration:

- `workflow.stepReview: "feature"` means one feature-level review packet, not a per-step approval loop.
- `workflow.checkpointCommits: "disabled"` means optional checkpoint commits are off for this feature.

The implementation should stay small, reviewable, and end with observable auth behavior rather than a broad backend expansion.

## Build steps

- [x] 1. **Add auth primitives and session state** - create the minimal server-side authentication helpers, session cookie handling, and access checks needed to protect authenticated routes.
  - Done when: a signed-in user receives a valid session token or cookie, an unauthenticated user does not, and the access rules are enforced from one shared auth helper.

- [x] 2. **Replace the demo login flow with real local sign-in** - connect the login page to the auth checks and validate credentials against the configured local admin value instead of the static demo route.
  - Done when: entering the configured admin credentials signs in the user and redirects to `/dashboard`, while invalid credentials show a user-facing error and keep the user on the login screen.

- [x] 3. **Protect dashboard routes and app shell access** - ensure the dashboard and any future protected route require a valid session before rendering content.
  - Done when: opening `/dashboard` without a valid session redirects to `/login`, and opening `/login` with a valid session redirects to `/dashboard`.

- [x] 4. **Add sign-out and session expiry behavior** - give the app a clear sign-out path and clean session invalidation when a session expires or is manually cleared.
  - Done when: signing out removes the session and requires a fresh sign-in to revisit protected pages, and an expired session is rejected instead of granting dashboard access.

## Files / areas

- `k8s-ui/app/login/page.tsx`
- `k8s-ui/app/dashboard/page.tsx`
- `k8s-ui/components/dashboard-shell.tsx`
- `k8s-ui/app/layout.tsx`
- `k8s-ui/app/page.tsx`
- new or updated auth helpers under `k8s-ui/lib/` or a small `k8s-ui/auth/` area if needed
- route guard logic in the Next.js app shell, middleware, or server component checks that align with the current app router setup

The current app is a small front-end project with no backend or auth library. The simplest repository-native path is a local cookie/session-based auth layer implemented in the Next.js app itself, not a broad multi-service setup.

## Data / contracts

The feature will introduce a minimal local auth contract for v1:

- Credential source: a local admin user or environment-backed admin credentials for the app
- Session payload: user identifier, role, and expiry timestamp stored in a secure cookie or server-side session value
- Auth rule: a protected route is accessible only when a valid session exists
- Sign-out rule: clearing the session invalidates access immediately
- Redirect rule: unauthenticated users return to `/login` and authenticated users are redirected away from `/login` to `/dashboard`

For the initial phase, the app should prefer a single admin/operator identity instead of a multi-user or tenant model. This keeps the scope aligned with the current codebase and the product direction without overbuilding RBAC.

## Testing

There is no project-level test runner configured yet, so this feature should rely on the real app behavior and build evidence instead of inventing a test harness mid-feature.

Recommended verification before approval:

- run the app build to confirm the route and auth code compiles cleanly
- verify the login flow manually in the browser against the auth rules
- confirm protected routes redirect when unauthenticated and allow access when signed in

No browser test command is configured, so browser-level evidence remains the correct check for this feature.

## Notes for the AI

- Preserve the current polished Kubernetes UI design while making it protected and operationally realistic.
- Keep the auth flow minimal and explicit; do not add broad user-management architecture to this feature.
- Use server-side checks for route access instead of only hiding UI controls in the client.
- Do not allow access to `/dashboard` through a client-only condition; the server or route guard must be the enforcement boundary.
- The app already has a login experience and dashboard shell. The auth work should make those existing pathways reflect real access control rather than a mock demo flow.

## Open questions

- Should the first admin credential be sourced from environment variables or from a minimal local user record in a future backend?
- Is the v1 product expected to support only one admin/operator identity, or should the app be designed for multi-user access immediately?
- Should a sign-out route or a session expiry warning be surfaced in the UI before redirecting?

These are implementation-level product decisions that affect how the auth layer is persisted and presented, but they do not change the core requirement that the dashboard be protected and session-aware.
