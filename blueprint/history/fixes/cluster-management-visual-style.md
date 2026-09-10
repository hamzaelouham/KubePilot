# Refine Cluster Management visual style

**Type:** Fix

**Status:** verified

**Branch:** `fix/cluster-management-visual-style`

## The problem

The Cluster Management table presents cluster metadata and operational status
without the compact, clearly connected information treatment shown in the
reference. It is less scannable than the rest of the operational UI.

## The fix

Apply the reference's calm card styling, icon-led information hierarchy, and
connected-status cue to the existing cluster-management presentation. Preserve
the current page layout and every existing capability: create, edit,
activate/deactivate, connection status, and admin-only deletion.

Keep KubePilot's current dashboard shell, sidebar, header, layout, spacing, and
color tokens unchanged; the reference informs only the cluster-row information
hierarchy and status presentation.

## Build steps

- [x] Refine the existing cluster table/card presentation with compact cluster
  information styling and semantic status treatment, without changing its
  data flow, actions, dialogs, permissions, or responsive layout.
  - **Done when:** registered clusters remain readable with name, endpoint,
    status, and creation information; active clusters show a clear connected
    cue; and Create, Edit, Activate/Deactivate, and Delete continue to be
    available according to the current permissions.

## Verify

- `yarn verify` passed.
- The combined project Verify command was retried twice but stalled in the
  backend suite without reporting a failure; the backend source is unchanged
  by this frontend-only fix.
- After deploying the UI image, review an active and inactive cluster at
  `/settings/clusters` and confirm the existing action dialogs remain available.
