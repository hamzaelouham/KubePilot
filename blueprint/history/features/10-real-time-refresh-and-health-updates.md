# Current Feature

**Status:** verified (incl. folded-in bug fixes)
**Type:** Feature
**Branch:** feature/real-time-refresh-and-health-updates

## Goal

Feature 10 — **Real-time refresh and health updates**. The dashboard currently
fetches every resource view once on mount; there is no polling, no refresh
control, and status is shown either as plain text or via a fragile boolean
(`status === "1"` for deployments). This feature adds live refresh behavior,
reliable operational status classification, and alerting cues so operators can
see at a glance which workloads need attention and keep the views current.

## In scope

- **Live refresh (real-time).** Client-side auto-refresh polling of the dashboard
  data views, a manual Refresh control, and a visible "last updated" timestamp.
- **Operational status updates.** A single additive backend `health` field on each
  resource summary, classifying the resource as `healthy` / `warning` / `error` /
  `unknown`, computed from the real Kubernetes status objects (not the lossy
  `status` string).
- **Alerting cues.** Color-coded status pills (healthy/warning/error/unknown)
  across all resource views, plus an alert banner on the Overview that counts and
  names unhealthy workloads.
- Focused backend unit tests for the health-classification logic.

## Out of scope

- WebSocket / server-push real-time transport (polling is the minimal native
  approach). Reversible internal detail; no user-visible, STORED, or external
  compatibility consequence that requires the heavier approach.
- A persistent alert center / notification history, the placeholder bell badge,
  or email/notification delivery. (Later observability feature.)
- Any change to the existing `status` / `name` / `namespace` / `kind` / `cluster`
  fields or removal of the `extra="forbid"` schemas. The `health` field is purely
  additive and `status` keeps its current meaning.
- Multi-cluster, RBAC/permissions, scale/restart actions, metrics/trends charts,
  and AI copilot. All remain later features.
- Adding a frontend test runner or any new runtime dependency.

## Build loop

- Create branch `feature/real-time-refresh-and-health-updates` (exact `Branch`).
- `workflow.stepReview: feature` → build all small steps, then one review packet.
- `workflow.checkpointCommits: disabled` → no checkpoint commits during steps.
- Do not run the full Verify after every step; run it once after all steps pass.

## Build steps

- [x] 1. **Backend: add computed `health` to resource summaries.**
  Add a `health` field to `ResourceSummary` and compute it in `resources()` /
  `_summary_status` from the live Kubernetes objects. Add `health` to the
  `ResourceItem` Pydantic schema as `Literal["healthy","warning","error","unknown"]`.
  Add focused unit tests in `backend/tests/test_kubernetes.py` covering realistic
  fixtures (see Data / contracts for the exact rule set).
  **Done when:** `backend/tests` passes with the new health assertions, and the
  schema field is enforced (`extra="forbid"` still holds).
- [x] 2. **Frontend: health-aware status rendering and overview alerting.**
  Update `Resource` types and `CoreResourceView` to render a color-coded status
  pill from `health` (healthy=green, warning=amber, error=red, unknown=slate) via
  a shared helper in `k8s-ui/lib/`. Update `OverviewView` to compute counts from
  `health` (replacing the `status === "1"` heuristic) and to show an alert banner
  that names unhealthy (warning/error) workloads when any exist.
  **Done when:** `yarn build` passes; unhealthy rows show distinct amber/red pills
  and the Overview shows an alert banner when any workload is not healthy.
- [x] 3. **Frontend: auto-refresh polling + Refresh control + last-updated.**
  Add a small reusable client hook in `k8s-ui/lib/` that polls each data view on a
  module-level interval (default 15 000 ms), skips overlapping in-flight fetches,
  aborts on unmount, suspends while the tab is hidden, and exposes a manual
  refresh plus a "last updated HH:MM:SS" timestamp and a Refresh button in the
  view header. Wire it into `OverviewView`, `CoreResourceView`, and
  `NamespacesView`.
  **Done when:** `yarn build` passes; views refetch on the interval and on Refresh,
  last-updated advances, and no overlapping requests are issued for the same view.

## Folded-in bug fixes (per user direction, completed with this feature)

Two defects found against the live Feature 10 dashboard after deploying to
Minikube were treated as part of this feature per explicit user direction, so
the whole branch lands as one work commit.

- [x] 4. **Fix: nav tabs caused a full page reload.**
  Root cause: the dashboard was a server component that re-rendered on every
  `searchParams` change, plus `useSearchParams` outside a `Suspense` boundary, plus
  no `loading.tsx` — so every tab click triggered a server round-trip / remount /
  polling reset that looked like a full reload.
  Fix: converted the dashboard to a client-driven SPA view switcher (server
  `app/dashboard/page.tsx` renders once and passes `initResource`/`initNamespace`;
  new `components/dashboard.tsx` holds `useState` and switches views via
  `window.history.replaceState`; `components/dashboard-shell.tsx` is now a
  controlled component driven by `{ activeResource, activeNamespace, onNavigate }`;
  `route`-detail now routes via `router.push("/dashboard?resource=...")`).
  **Done when:** clicking any nav tab switches views with no full page reload,
  no server round-trip, and no polling reset; `yarn build` passes.
- [x] 5. **Fix: all healthy pods showed "warning / need attention".**
  Root cause: `_pod_health` flagged **any** pod with `restart_count > 0` as
  warning, so nearly every pod (restartCount 2–6) was reported unhealthy.
  Fix: removed the blanket restart-count rule. Health now reflects current state:
  `phase != Running` → error; container not ready → warning; a waiting reason of
  crash/crashloop/imagepullbackoff/createcontainererror/invalidimagename → error,
  other waiting → warning; else healthy.
  **Done when:** all 11 live cluster pods report `healthy` via the backend API;
  50 backend tests pass.

## Files / areas

- `backend/app/kubernetes/client.py` — add `ResourceSummary.health` and a
  `_summary_status` / health helper; wire into `resources()`.
- `backend/app/api/v1/discovery_schemas.py` — add `health` to `ResourceItem`
  (keep `extra="forbid"`).
- `backend/app/api/v1/routes.py` — include `health` in the manual
  `ResourceItem(...)` mapping so the field is reachable through the HTTP boundary.
- `backend/tests/test_kubernetes.py` — new health-classification tests + a
  route-level test asserting `health` is returned.
- `k8s-ui/lib/status-tone.ts` (new) — shared `health` → Tailwind tone mapping.
- `k8s-ui/lib/use-polling.ts` (new) — auto-refresh hook + refresh() + lastUpdated.
- `k8s-ui/components/core-resource-view.tsx` — health pill + polling.
- `k8s-ui/components/overview-view.tsx` — health-based counts, alert banner, polling.
- `k8s-ui/components/namespaces-view.tsx` — polling (align with the hook).
- `k8s-ui/app/api/cluster/resources/route.ts` — pass-through only; no change
  required (the `health` field flows through the existing JSON proxy).

No DB migration, no new environment variables, no Docker/k8s manifest changes.

## Data / contracts

The `ResourceItem` response gains one additive field:

```
health: "healthy" | "warning" | "error" | "unknown"
```

`status` keeps its current meaning and value. Existing fields
(`cluster`, `namespace`, `kind`, `name`, `status`) are unchanged. The frontend
BFF proxy (`/api/cluster/resources`) forwards the payload unchanged.

Health classification (computed server-side from live Kubernetes objects;
`unknown` when no reliable signal):

- **deployments** (and replica-sets, stateful-sets, daemon-sets, jobs): compare
  `spec.replicas` against `status.readyReplicas` /
  `status.availableReplicas` / `status.unavailableReplicas`:
  healthy iff `spec.replicas > 0` and all replicas ready/available and no
  `unavailableReplicas`; warning iff `0 < readyReplicas < spec.replicas`; error iff
  `readyReplicas == 0` while `spec.replicas > 0`.
- **pods**: healthy iff `status.phase == "Running"` and every container in
  `status.containerStatuses` is `ready` with `restartCount == 0`; warning iff
  `phase == "Running"` but a container is waiting (e.g. `CrashLoopBackOff`,
  `ImagePullBackOff`, `ErrImagePull`, `CreateContainerConfigError`) or any
  `restartCount > 0`; error iff `phase` is `Pending`, `Failed`, or `Unknown`.
- **nodes**: healthy iff the last `Ready` condition `status == "True"`; error iff
  `"False"`; warning iff `"Unknown"`.
- **persistent-volumes**: healthy iff phase is `Bound` or `Available`; error iff
  `Released` or `Failed`; warning iff `Pending`.
- **Other types** (services, endpoints, cluster-roles, storage-classes,
  cron-jobs, replication-controllers): `unknown`.

The weight/threshold for pod "many restarts" and job completion is deliberately a
`warning`/`error` boundary; keep the exact edge cases in the unit test fixtures so
later work cannot silently reinterpret the boundaries.

## Testing

- **Backend (`logicTests: when-configured`):** pytest exists (23 tests today).
  Add focused unit tests in `backend/tests/test_kubernetes.py` using the existing
  fake/object fixtures to assert each health branch (deployment ready/partial/zero,
  pod running-ready / running-restarts / pending-failed, node ready/not-ready,
  pv bound-failed, and unknown for a type with no signal). Verify command:
  `cd backend && .venv/bin/pytest` and `python3 -m compileall -q app`.
- **Frontend (`uiEvidence: when-available`):** no test runner is configured. Proof
  is the build (`cd k8s-ui && yarn build`) plus manual browser verification against
  the running app (start the dev servers, view Overview/Workloads/Namespaces,
  confirm pills, alert banner, auto-refresh, last-updated). Do not add brittle UI
  tests or install a runner.

## Notes for the AI

- The backend already owns Kubernetes health semantics (it has the real objects);
  keep classification server-side. The frontend only maps the returned `health` to
  tones — do not re-derive health from the lossy `status` string.
- Preserve the existing `"use client"` + `useEffect`/`fetch` + `AbortController`
  pattern in the views. Reuse the `lib/` convention already used for shared helpers.
- Polling must not issue overlapping requests for the same view and must abort on
  unmount (match the existing cleanup pattern). Pause when the document is hidden.
- Keep unexpected failures flowing to the existing `error` render path
  (`role="alert"`), not swallowed.
- The `🔔` bell in `DashboardShell` stays a placeholder; do not wire it.

## Open questions

- **Backend contract addition is acceptable?** Adding `health` to `ResourceItem`
  is a new public API field. It is additive and the existing fields are untouched,
  but it is the one contract change in this feature. The recommended,
  repository-native choice is to keep health computed backend-side. Confirm during
  review; this does not block implementation.
- **Default refresh interval.** 15 000 ms is chosen as a sensible operations
  default and exposed as one module-level constant. Any value is a reversible
  internal detail (no stored/config contract), so it does not block.

## Fold-in file changes (bug fixes)

Fix 4 (SPA nav, no full reload):
- `k8s-ui/app/dashboard/page.tsx` — becomes async server component, reads
  `searchParams`, passes `initResource`/`initNamespace` to the client switcher.
- `k8s-ui/components/dashboard.tsx` (new) — `useState` view switcher, shallow
  nav via `window.history.replaceState`, no `router.push` on tab clicks.
- `k8s-ui/components/dashboard-shell.tsx` — refactored to controlled
  `{ activeResource, activeNamespace, onNavigate }`; no `useSearchParams`/
  `useRouter`.
- `k8s-ui/components/resource-detail-view.tsx` — routes to the dashboard view via
  `router.push` and passes the controlled shell props.

Fix 5 (pod health false positives):
- `backend/app/kubernetes/client.py` — reworked `_pod_health` (removed
  `restart_count > 0` → warning; added wait-reason based error classification).
- `backend/tests/test_kubernetes.py` — `_container` helper now takes a `waiting`
  reason; `restart_count=2` moved `warning` → `healthy`; added CrashLoopBackOff /
  ImagePullBackOff / ContainerCreating cases.

Deploy helper (user-owned, committed with this work):
- `deploy.sh` (new, repo root) — sets explicit `BACKEND_DEPLOYMENT`/`
  FRONTEND_DEPLOYMENT` names distinct from image/service names; previously
  restarted `deployment/kubepilot-ui` but the real Deployment is `frontend`.

The `nextjs-agent-rules` block re-added to `AGENTS.md` by `next dev`/`next build`
is committed with this work to keep the tree clean.
