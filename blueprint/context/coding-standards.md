# Coding Standards

These conventions reflect the current project reality: a Next.js + TypeScript frontend with a future FastAPI + PostgreSQL backend and Kubernetes integration. They are intended to guide future implementation without forcing the project into a template that does not match the intended architecture.

## Frontend

- Next.js 16 with TypeScript and Tailwind CSS for the app shell and dashboard views
- Prefer component-driven UI design with reusable presentational pieces
- Keep dashboard and resource views readable, focused, and operationally clear
- Use client-side interactivity only where UI state or browser-driven actions require it
- Use server components by default for data-driven pages and fetch-heavy presentation
- Keep selectors, filters, and route parameters organized around real Kubernetes concepts like namespace, resource type, and cluster context

## Backend

- FastAPI is the expected backend layer for application APIs, data access, and Kubernetes integration
- Keep API boundaries explicit between frontend presentation, auth/session logic, and Kubernetes access code
- Model resource responses around cluster, namespace, workload, pod, event, and log concepts
- Validate request and response payloads with typed Python models or Pydantic schemas
- Keep backend actions narrow and operationally safe; avoid broad destructive actions without confirmation

## Data and persistence

- PostgreSQL is the likely persistence layer for application data and operational metadata
- Use explicit schemas for users, clusters, authentication state, namespaces, and audit records
- Keep Kubernetes as the system of record for live resource state; store only the data needed for local UI, user access, and operational history
- Preserve the distinction between live cluster data and application-owned configuration metadata

## Kubernetes integration

- Connect to Kubernetes via the Kubernetes Python client and cluster credentials or configured kubeconfig data
- Structure resource access around namespaces, workloads, pods, events, logs, and deployment health
- Treat cluster objects as read-heavy operational data and keep action flows explicit and permission-aware
- Surface clear error handling for unreachable clusters, permission failures, and missing resource state

## Authentication and access

- Use local app authentication for admin and operator access to the platform
- Protect operational routes and resource actions behind session checks
- Keep permission boundaries clear between app users and cluster-level operations
- Avoid exposing cluster endpoints or sensitive actions without explicit authorization

## File organization

- Frontend components: `components/`
- Route pages: `app/`
- Shared UI and data helpers: `lib/`
- Future backend service code: `backend/` or an adjacent Python service directory
- Future API schemas and models: a dedicated `schemas/` or `models/` area in the backend

## Naming and structure

- Components and route modules use descriptive PascalCase or kebab-case naming that matches the resource being represented
- Prefer clear domain naming for Kubernetes concepts such as clusters, namespaces, workloads, and nodes
- Keep functions and modules focused on one operational concern rather than creating a single large app-level file

## Styling

- Use Tailwind CSS for layout, spacing, color, and state treatment
- Preserve the mature operational aesthetic: calm surfaces, readable hierarchy, and strong status emphasis
- Keep forms and tables easy to scan under operational load
- Prefer reusable status styles for healthy, warning, and error states

## Error handling

- Fail gracefully when the cluster is unreachable or authentication is missing
- Show user-facing messages for permission issues, missing resources, and transient backend failures
- Log operational failures at the backend boundary and keep front-end messages concise and actionable

## Testing

Testing is opt-in for this project. At the moment there is no configured test runner, so the project should continue to verify frontend changes through the real app build and manual proof in the browser until a test command is added intentionally.

When a runner is added, the project should follow the same stack-native pattern it chooses for the rest of the app and update the Commands section in `AGENTS.md` to include the real `test` command. This is the single signal that turns tests into a gate for logic-bearing work.

- Test pure logic such as parsers, formatters, validators, and operational helpers when the behavior can be asserted exactly
- Do not add brittle tests for purely visual layouts or dashboards unless the behavior is stable and inspectable
- Prefer browser-level verification and a successful build for UI-heavy changes until a formal test harness is introduced

## Browser verification

- Use the running app and browser review for dashboard flows, navigation, resource layout, and user experience
- Capture actual behavior in the browser when verifying operational UI changes, especially route changes, filters, and status displays
- Do not assume a page works from code inspection alone when a real browser check can confirm the effect

## Build and deployment

- Build Docker images through `.github/workflows/docker-build-push.yml`. PR builds skip login and publishing. Trusted push/manual builds publish tags containing the branch and commit when no tag is supplied; only manual stable-version builds on master also publish `latest`. Use an explicitly dispatched preview build for live feature testing.
- The workflow requires the repo secrets `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` and the expected Docker Hub repos under the `hamzaelouham` namespace.
- Prefer the published images over local `docker build`; local `yarn install` can hang on slow egress. The local build commands stay documented for offline or image-customizing setups but are commented out in `deploy.sh`.
- Deploy to a running Minikube cluster with `./deploy.sh` (pull from Docker Hub, `minikube image load`, `kubectl apply`) or the manual commands in the AGENTS.md Commands section. `./deploy.sh --no-build` applies workloads without pulling or reloading images.
- The Kubernetes manifests in `backend/deploy/kubernetes/` reference the Docker Hub image names (`hamzaelouham/kubepilot-*:latest`) with `imagePullPolicy: IfNotPresent`, so a loaded image is used and the public repo acts as a fallback.

## Writing

- Prefer clear, concise operational language over marketing phrasing
- Use plain, direct wording for system states, errors, and workflows
- Keep documentation and comments practical, especially around Kubernetes resource semantics or safety-sensitive actions
- Avoid AI-style filler language or generic platitudes in docs and code comments
