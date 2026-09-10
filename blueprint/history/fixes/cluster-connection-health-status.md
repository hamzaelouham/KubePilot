# Cluster connection health status

**Type:** Fix

**Status:** verified

**Branch:** `fix/cluster-connection-health-status`

## The problem

The Clusters page labels the stored administrative value `active` as **Connected**.
That value only records whether the connection is enabled; it is not refreshed
against the Kubernetes API. A cluster that has been shut down can therefore keep
a green Connected badge and remain selectable in the UI.

## The fix

Keep the administrator's enabled/disabled setting distinct from live reachability.
When cluster connections are listed, the backend must perform a safe Kubernetes
health probe for enabled clusters and return their current connection health.
The UI must use that live result for its status badge and selection, while still
showing administratively disabled clusters as inactive. Probe failures must be
reported as unavailable and must not expose kubeconfig content or alter the
administrator's enabled/disabled choice.

## Build steps

1. [x] **Expose refreshed connection health from the cluster API**
   - Add a bounded Kubernetes API health probe for each enabled registered
     cluster when serving the cluster list, with explicit handling for
     unreachable and forbidden connections.
   - Extend the cluster response contract with the live health result while
     preserving the existing administrative `active` / `inactive` state and
     authorization rules.
   - Add backend coverage for reachable, unreachable, forbidden, and inactive
     clusters.
   - **Done when:** an authenticated cluster-list response distinguishes an
     enabled reachable cluster from an enabled but shut-down/unreachable one,
     without changing the saved administrative state.

2. [x] **Show and select only live connections appropriately**
   - Update the cluster-management badge and cluster selector to consume the
     live health result: green only for a reachable connection, a clear
     unavailable state for failed probes, and inactive for disabled connections.
   - Ensure an unavailable cluster is not retained or chosen as the active
     dashboard connection; preserve the existing error and loading behavior.
   - **Done when:** after a cluster becomes unreachable and the list refreshes,
     the UI no longer presents it as green Connected or selects it for requests.

## Verify

- Focused backend cluster-management suite: 41 passed.
- Frontend production build: `yarn verify` passed.
- The required combined Verify command was confirmed passing by the user after
  the hosted terminal runner repeatedly failed to retain its full test process.
- Live browser verification remains pending.
