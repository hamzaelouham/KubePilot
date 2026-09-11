# Current Feature

> **Generated file.** Holds the one feature, fix, or rollback being built right now. Run
> `/feature <number-or-name>` to spec a build-plan feature, or `/fix "<bug>"` for
> an ad-hoc fix. Use `/rollback <completed-feature>` to plan a safe reversal.
> Build one thing at a time; `/complete` archives it under
> `blueprint/history/` and resets this file.

## Fix: protect the local cluster and make delete refresh the list

**Type:** Fix
**Status:** verified
**Branch:** `fix/local-cluster-delete-guard-and-refresh`
**Fixes:** —
**Parent item:** —

### The problem

Two distinct bugs on `Settings → Clusters`:

1. **The local (in-cluster) cluster can be deleted.** The backend seeds one
   cluster at startup (`_seed_default_cluster` in `backend/app/main.py:30`) with
   `endpoint="in-cluster"`, `kubeconfig_ref="in-cluster"`, default name
   `primary`. `cluster_delete` (`backend/app/api/v1/routes.py:879`) has no
   guard, and the UI renders a Delete button for every row. Deleting this row
   removes the connection the backend itself runs in, breaking the app.

2. **Deleting any cluster does not update the list until a full page reload.**
   The DELETE proxy route (`k8s-ui/app/api/clusters/[id]/route.ts:34-38`)
   forwards the backend's `204 No Content` with
   `new NextResponse(body, { status: 204 })` where `body === ""`. In Next.js
   16.3.3 an empty-string body on status 204 throws
   (`Response constructor: Invalid response status code 204`). The route's
   `catch` turns that into a `503`, so `doDelete` in
   `k8s-ui/components/clusters-management.tsx:310` sees
   `response.status === 503`, shows "The cluster management service is currently
   unavailable.", and returns **without** calling `refresh()` while leaving the
   dialog open. The backend already deleted the row, so it only disappears after
   the page is reloaded. The same latent bug exists in the users proxy
   (`k8s-ui/app/api/users/[id]/route.ts:34-38`).

### The fix

**Backend:**

- In `cluster_delete` (`backend/app/api/v1/routes.py:879`), reject deletion of
  the in-cluster connection before touching the database: when
  `row.endpoint == "in-cluster"`, raise `HTTPException(409)` with
  `detail={"code": "local_cluster_protected", "message": ...}` explaining the
  local cluster cannot be removed. Registered clusters keep the existing 204 +
  cascade + audit behavior.

**Frontend:**

- Fix the DELETE proxy to never pass a body with a null-body status. In both
  `k8s-ui/app/api/clusters/[id]/route.ts` and
  `k8s-ui/app/api/users/[id]/route.ts`, forward `null` when the backend response
  is empty (204) and keep the JSON body otherwise, so `doDelete` receives a real
  204 and runs `refresh()`, dropping the row immediately.
- Hide the per-row Delete button for the local cluster. Add an `isLocal`
  helper (`cluster.endpoint === "in-cluster"`) in
  `clusters-management.tsx` and render an inert "Local" indicator instead of the
  Delete button, so the protection is clear and the backend guard is a
  backstop. Edit/Deactivate behavior is unchanged.

**What the fix must not break:**

- Deleting a registered (non-local) cluster still returns 204 and cascades its
  namespaces, workloads, pods, deployments, services, nodes, events, and
  installation jobs, and still records the `cluster.delete` audit event.
- Rename, kubeconfig replacement, activate/deactivate, and create flows are
  unchanged.
- Viewer/operator RBAC (`CLUSTERS_DELETE` is admin-only) is unchanged.

### Build steps

- [ ] **Step 1 — Backend: guard the local cluster and cover it**
  - Add the `endpoint == "in-cluster"` 409 guard to `cluster_delete`; leave the
    204 path untouched for registered clusters.
  - Add a focused test asserting the local cluster delete returns 409 with
    `local_cluster_protected` and the row still exists, alongside the existing
    registered-cluster delete test.
  - **Done when:** `cd backend && .venv/bin/python3 -m pytest` passes; deleting
    the in-cluster cluster returns 409 and the row survives.

- [ ] **Step 2 — Frontend: fix the 204 proxy and hide the Delete action**
  - Pass a `null` body through the DELETE proxy when the backend response is
    empty, in both the clusters and users routes.
  - Add `isLocal` and render a "Local" indicator instead of Delete for the
    in-cluster cluster in `clusters-management.tsx`.
  - **Done when:** deleting a registered cluster removes its row without a page
    reload and no error is shown; the local cluster has no Delete button;
    `cd k8s-ui && yarn build` passes.

### Verify

- `cd backend && .venv/bin/python3 -m pytest` — including the new local-cluster
  guard test.
- `cd k8s-ui && yarn build`; `yarn lint` → 0 errors.
- Manual (admin, Settings → Clusters): the `primary` local cluster shows a
  "Local" indicator and no Delete button; deleting a registered cluster removes
  it from the table immediately, no reload and no "service unavailable" callout.
