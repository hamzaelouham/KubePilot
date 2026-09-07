# Cluster management edit and delete

> **Type:** Fix
> **Status:** verified
> **Branch:** `fix/cluster-management-edit-delete`

## The problem

The cluster management page (`k8s-ui/components/clusters-management.tsx`) only
offers **create** and **Reactivate/Deactivate** per row. There is no way to
rename a registered cluster, change its endpoint (replace its kubeconfig), or
delete it.

The backend is equally limited:

- `PATCH /api/v1/clusters/{cluster_id}`
  (`backend/app/api/v1/routes.py:731`, `cluster_update_status`) accepts only
  `status` via `ClusterStatusUpdateRequest`
  (`backend/app/api/v1/cluster_schemas.py:30`), so name and endpoint are
  immutable after creation.
- There is **no** `DELETE /clusters/{cluster_id}` route at all.
- `Permission.CLUSTERS_DELETE` (`backend/app/core/rbac.py:19`) and its audit
  infra exist but are unused. `ClusterConnection` children
  (namespaces/workloads/pods/deployments/services/nodes/events) all cascade on
  `ondelete="CASCADE"` (`backend/app/models/entities.py`), so row deletion is
  safe.
- Cluster endpoints are derived from stored `kubeconfig_content` at create
  (`routes.py:683-692`); the same parse+probe path must run on endpoint change.

## The fix

Make registered clusters editable and deletable, backend first then UI.

**Backend:**

1. Replace `ClusterStatusUpdateRequest` with `ClusterUpdateRequest`:
   optional `name`, `kubeconfig_content`, `status` (any subset; at least one).
2. Generalize `cluster_update_status` → `cluster_update`:
   - `status` — same active/inactive validation and
     `cluster.status_change` audit as today (no behavior change).
   - `name` — strip, require non-empty; duplicate → `409 duplicate_cluster_name`.
   - `kubeconfig_content` — when provided, run `_parse_kubeconfig` +
     `_probe_kubeconfig` (reuse probe so unreachable/TLS/bad-credential configs
     fail with the same 502/422 and the row is left unchanged), then update
     `endpoint`, `kubeconfig_ref=""`, `kubeconfig_content`.
   - Audit `CLUSTER_UPDATED = "cluster.update"` when name or kubeconfig changed.
3. Add `DELETE /api/v1/clusters/{cluster_id}` → `204`, requiring
   `CLUSTERS_DELETE` (admin-only; OPERATOR has `CLUSTERS_UPDATE`, not delete).
   Record `CLUSTER_DELETED = "cluster.delete"` with the deleted name in context,
   then delete the row (children cascade).
4. New audit events appended to `AuditEvent` in `app/core/audit.py`.

**Frontend:**

1. Add a `DELETE` handler to `k8s-ui/app/api/clusters/[id]/route.ts` mirroring
   the users proxy (`app/api/users/[id]/route.ts`).
2. `components/clusters-management.tsx`: per-row **Edit** (rename + optional
   kubeconfig replacement to change the endpoint; prefill name, show current
   endpoint, keep list response free of secret kubeconfig content) and **Delete**
   (confirmation dialog). Delete visible only when the current role can delete;
   thread `canDelete` (`user.role === "admin"`) through
   `app/settings/clusters/page.tsx` and `cluster-settings-view.tsx`. Viewers
   still see no action column; operators get Edit + toggle only.
3. Error handling reuses the existing `extractError` path (502/422 messages,
   401 → login, 503 → unavailable).

Must not break: create flow, status toggle, viewer/operator/delete RBAC
(`tests/test_rbac_permissions.py`), or the `primary` in-cluster seed row
(renames/deletes apply to registered clusters by id).

## Build steps

- **Step 1 — backend update + delete.** `ClusterUpdateRequest` schema; extended
  PATCH (name/kubeconfig/status); DELETE endpoint; `cluster.update` /
  `cluster.delete` audit events.
  Done when: pytest passes, including new tests — rename persists, kubeconfig
  replacement re-derives endpoint and re-probes, unreachable replace → 502 and
  unchanged row, duplicate name → 409, delete removes row + cascades +
  records audit, viewer PATCH/DELETE → 403, operator DELETE → 403, operator
  rename → 200.
  **Status: done** (`161 passed`, incl. new update/delete coverage).
- **Step 2 — frontend edit + delete.** DELETE proxy handler; Edit and Delete
  actions + dialogs in `clusters-management.tsx`; `canDelete` threading.
  Done when: `cd k8s-ui && yarn verify` builds, and the live UI (Minikube
  deploy) lets an admin rename kind, replace its kubeconfig (unreachable →
  clear error), and delete with confirmation; viewers/operators see only
  permitted actions.
  **Status: done** (`yarn verify` builds, `yarn lint` 0 errors; live UI path is
  for the check/try gates after the fixed backend image is deployed).

## Verify

- `cd backend && .venv/bin/python3 -m pytest`
- `cd k8s-ui && yarn verify`
- Live (admin, Settings → Clusters): register kind → rename it → replace its
  kubeconfig with an unreachable server (clear rejection, unchanged) → re-register
  reachable config → delete with confirmation → gone from the list, dashboard
  selector no longer offers it. Operator: can rename, no Delete button.

## Verification evidence

- `cd backend && .venv/bin/python3 -m pytest` → **161 passed** (13 new tests:
  rename persists, operator rename → 200, viewer PATCH → 403, duplicate → 409,
  rename-to-self ok, empty name/body → 422, endpoint replace re-derives +
  re-probes, unreachable replace → 502 unchanged, rejected creds → 422, delete
  cascades + audits, viewer/operator DELETE → 403, unknown → 404).
- `cd k8s-ui && yarn verify` → builds clean; `yarn lint` → 0 errors.
- Ledgers `findings.md` / `review.md`: clean canonical stubs (no P0/P1).