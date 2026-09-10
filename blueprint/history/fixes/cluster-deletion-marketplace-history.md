# Fix cluster deletion with Marketplace history

**Type:** Fix

**Status:** verified

**Branch:** `fix/cluster-deletion-marketplace-history`

## The problem

Deleting a registered cluster from `/settings/clusters` returns HTTP 500 when
Marketplace installation jobs reference that cluster. The database schema
declares `installation_jobs.cluster_id` as `ON DELETE CASCADE`, but SQLAlchemy
attempts to set the non-null foreign key to `NULL` before deleting the parent.

## The fix

Configure the ORM relationship to honor the existing database cascade when a
cluster is deleted. The delete must remove dependent Marketplace job records,
retain the existing audit entry, and leave unrelated clusters unchanged.

## Build steps

- [x] Configure the cluster-to-installation relationship for database-managed
  deletion, and add focused backend coverage for deleting a cluster with
  Marketplace jobs.
  - **Done when:** an authorized cluster deletion returns 204, the deleted
    cluster and its jobs are absent, and other clusters and jobs remain.

## Verify

- Focused cluster-deletion tests: 4 passed.
- Full backend suite: 247 passed.
- `yarn verify`: passed.
- Live reproduction before the repair: Azure-k8s deletion returned HTTP 500 and
  the cluster remained present. Live retesting awaits deployment of this fix.
