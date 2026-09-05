# Current Feature

**Status:** verified (complete)
**Type:** Feature
**Branch:** feature/shadcn-ui-data-tables

> **Completion note (2026-09-05):** All seven build steps implemented on this
> branch (work commit `6a44b75`). Frontend Verify `cd k8s-ui && yarn build`
> passes. The user previewed the UI on a local frontend run and confirmed the
> tables look good; the planned Minikube redeploy was not needed for sign-off.
> The `k8s-ui/Dockerfile` build workaround (local-network slowness during
> `yarn install`) was tried and reverted, never committed.

## Goal

Feature 15 — **shadcn/ui integration and table migration.** Integrate
shadcn/ui into the existing Next.js app and migrate the current resource tables
to reusable, typed shadcn Data Table components, while **preserving the existing
visual design** (layout, colors, typography, spacing, borders, radius, status
badges, row height, hover, responsive behavior) and improving table
functionality. The new Data Tables add column **sorting**, a **filter/search**
box, and **pagination** that were not present before. This is the user-owned,
explicit scope that installed the `shadcn` and `migrate-radix-to-base` skills;
the skill install files become part of this feature's work.

## In scope

- **shadcn/ui install + config (Task 1).** Initialize shadcn/ui in `k8s-ui/`
  with the project's Yarn package runner, on **Base UI** (the CLI default; no
  Radix dependency is introduced). Creates `k8s-ui/components.json`,
  `k8s-ui/components/ui/*` primitives, `k8s-ui/lib/utils.ts` (`cn`), the
  `@/*`-aliased Tailwind v4 integration, and a `data-table` building block. Keep
  the existing Tailwind v4 styling system (`app/globals.css`, `@theme inline`)
  and do not replace or needlessly restyle it.
- **MCP server config (Task 2).** Configure the shadcn MCP server for:
  - **GitHub Copilot:** project `.vscode/mcp.json` with the official
    `servers` VSCode format (`"shadcn": { "command": "npx", "args":
    ["shadcn@latest", "mcp"] }`).
  - **OpenCode:** project `.opencode/opencode.jsonc` with OpenCode V2 local
    server shape (`mcp.servers.shadcn` → `type: "local"`, `command: ["npx",
    "shadcn@latest", "mcp"]`). Do not touch the user global
    `~/.config/opencode/opencode.jsonc` or unrelated server configs, and expose
    no secrets.
- **Inspected tables → Data Table migration (Tasks 3–4).** Migrate every
  existing `<table>` data surface in `k8s-ui/components/` and the events table
  in `resource-detail-view.tsx` to a **single reusable** `DataTable` component
  backed by TanStack Table column definitions. Reuse one table implementation
  across pages; no duplicated table logic. Tables in scope by file:
  - `components/core-resource-view.tsx` — dynamic resource table (nodes, pods,
    deployments, replica sets, services, daemon sets, stateful sets, jobs,
    cron jobs, replication controllers, persistent volumes, persistent volume
    claims, cluster roles, storage classes) with variable columns
    (Name/Namespace/CPU/Memory/Status/Cluster/Capacity).
  - `components/workloads-view.tsx` — unified workloads table (Pod, Deployment,
    StatefulSet, DaemonSet, Job).
  - `components/namespaces-view.tsx` — Name/Status table.
  - `components/overview-view.tsx` — Namespace Utilization and Deployments
    tables.
  - `components/cluster-view.tsx` — nodes / persistent volumes / storage
    classes tables (per-column CPU/memory/capacity cells).
  - `components/resource-detail-view.tsx` — events table (Type, Reason,
    Message, Source, Time).
- **Functionality (Task 4).** Data Tables support column sorting, a text
  filter/search control, and prior/next pagination, styled to match the current
  slate/cyan design (optional checkbox row selection only if a current table
  already has it — none do today). Preserve existing loading, empty, and error
  states and responsive horizontal scroll.

## Out of scope

- **Restyling / design change.** The migration must not change the current look:
  overall layout, navigation, colors (`slate-*`/`cyan-*`), typography, font
  sizes, spacing (`px-4 py-3` cells, `bg-slate-100` headers), borders, radius
  (`rounded-xl`), background, status pills, button, row height, hover, or
  responsive behavior. No default shadcn appearance that conflicts with the
  current design.
- **Backend changes.** This is a frontend-only feature; no FastAPI route,
  schema, or query changes. The metrics/resource endpoint contracts are
  unchanged.
- **Radix / Base migration mechanics.** No existing code is on Radix, so the
  `migrate-radix-to-base` skill is reserved but not required for this work; the
  CLI generates Base UI components directly.
- **New pages, routes, tabs, or user-visible navigation.**
- **Data-layer changes** (sorting/filtering/pagination are client-side over the
  already-fetched in-memory item list; no new backend paging).
- Anything beyond shadcn components needed for Data Tables (charting, forms,
  theming, navigation primitives).

## Build loop

- Create branch `feature/shadcn-ui-data-tables` (exact `Branch` value).
- `workflow.stepReview: feature` → build all small steps, then one review packet.
- `workflow.checkpointCommits: disabled` → no per-step checkpoint commits.
- Frontend Verify is the build: `cd k8s-ui && yarn build` (no project `test`
  command; frontend `lint` is `eslint` — run `yarn lint` on changed files where
  clean). There is no frontend test runner; the coding-standard browser
  verification path applies.
- The skill-install files (`skills-lock.json`, `.agents/skills/shadcn/`,
  `.agents/skills/migrate-radix-to-base/`) already exist in the working tree
  from the install; they are staged with this feature's commit, not left as
  stray dirty work.

## Build steps

- [ ] 1. **Install + initialize shadcn/ui (Base UI) and refresh `cn` path.**
  Run the CLI init in `k8s-ui/` with the Yarn runner (no interactive prompts,
  Base UI default, Tailwind v4). Confirm `k8s-ui/components.json`,
  `k8s-ui/components/ui/`, `k8s-ui/lib/utils.ts`, and the Tailwind/alias wiring
  exist. Then `npx shadcn@latest add table pagination input button badge
  dropdown-menu` (plus any primitive the generated `data-table` requires) using
  the project runner. Do not alter `app/globals.css` existing tokens; add
  shadcn CSS variables only as the CLI requires and keep `@theme inline`
  intact.
  **Done when:** `components.json`, `components/ui/*`, `lib/utils.ts` exist,
  the components resolve under `@/components/ui/*` and `@/lib/utils`, and a
  clean baseline `yarn build` still passes (record any pre-feature
  failures as pre-existing).

- [ ] 2. **Configure MCP servers for Copilot and OpenCode.**
  Create `.vscode/mcp.json` (GitHub Copilot) with the official `servers`
  shadcn entry, and `.opencode/opencode.jsonc` with the OpenCode V2 local
  server for `shadcn`. Keep both minimal, secret-free, and scoped to this
  project; do not modify the user global OpenCode config or any other server.
  **Done when:** both files exist with valid JSON/JSONC and a `shadcn` server,
  `yarn build`/`yarn lint` ignore them, and each config can be verified by
  running `npx shadcn@latest mcp` (stdio server starts).

- [ ] 3. **Create one reusable `DataTable` component with TanStack.**
  Add `k8s-ui/components/data-table.tsx` (and colocation primitives under
  `components/ui/` as needed) typed with TanStack Table: column defs,
  `getSortedRowModel`, a text filter (via `globalFilter` or a dedicated column
  filter), `getPaginationRowModel`, responsive `overflow-x-auto` wrapper, and
  empty/loading states. Style it to the current slate/cyan look (white
  `rounded-xl` bordered container, `bg-slate-100` header, `px-4 py-3` cells,
  `text-base`, status-pill cells remain as the existing formatters supply
  them). Export typed helpers so views pass a generic row type.
  **Done when:** `yarn build` passes and the component renders a sortable,
  filterable, paginated table with the existing look.

- [ ] 4. **Migrate `core-resource-view` dynamic table.**
  Replace the `<table>` in `core-resource-view.tsx` with the `DataTable`,
  building column defs per resource type from the existing `columns` map and
  the per-cell metric/status renderers (utilization pills, CPU/memory, storage
  capacity, health pills, detail links) unchanged. Preserve the metrics-
  unavailable notice and loading/empty/error states.
  **Done when:** `yarn build` passes and nodes/pods/deployments/etc. render via
  the DataTable with identical cells and values; sorting/filter/pager work.

- [ ] 5. **Migrate `workloads-view` and `namespaces-view` tables.**
  Replace both `<table>`s with the `DataTable` (name detail links, kind/
  namespace/status/health cells). Preserve the per-kind count cards and the
  attention alert above the table.
  **Done when:** `yarn build` passes and both surfaces show the same columns,
  values, and styling via DataTable; sorting/filter/pager work.

- [ ] 6. **Migrate `overview-view` and `cluster-view` tables.**
  Replace the Namespace Utilization and Deployments tables in `overview-view`
  and the nodes / persistent-volumes / storage-classes tables in `cluster-view`
  with `DataTable` column defs, keeping the CPU/memory/capacity/status cell
  renderers and the health pills.
  **Done when:** `yarn build` passes and all these tables match the prior
  markup's values and styling; sorting/filter/pager work.

- [ ] 7. **Migrate events table in `resource-detail-view` and final clean build.**
  Replace the events `<table>` (Type, Reason, Message, Source, Time) with the
  `DataTable`. Run the full `yarn build` (and `yarn lint` on touched files) for
  the whole app and confirm no remaining hand-rolled data `<table>` in
  `components/` or `app/` is left except non-data layout tables. Review the
  `DataTable` for duplicated-table-logic adherence and repository convention
  (typed, `lib/`-based helpers, no new dependencies beyond shadcn/TanStack).
  **Done when:** `yarn build` passes cleanly, `yarn lint` is clean on changed
  files, and every in-scope data table uses the shared `DataTable`.

## Files / areas

- `k8s-ui/components.json` (new) — shadcn config; `base` = `ui-primitive/base-ui
  (base)` (-like), `style`, Tailwind v4, `@/*` aliases.
- `k8s-ui/components/ui/*` (new) — shadcn primitives (table, button, input,
  pagination, badge, dropdown-menu, and the resolved `data-table` building
  block).
- `k8s-ui/lib/utils.ts` (new) — `cn()` helper (CLI-provided).
- `k8s-ui/components/data-table.tsx` (new) — reusable typed TanStack Table
  component with sorting, filtering, pagination.
- `k8s-ui/components/core-resource-view.tsx` — migrate dynamic table.
- `k8s-ui/components/workloads-view.tsx` — migrate workloads table.
- `k8s-ui/components/namespaces-view.tsx` — migrate namespaces table.
- `k8s-ui/components/overview-view.tsx` — migrate utilization + deployments.
- `k8s-ui/components/cluster-view.tsx` — migrate nodes/PV/storage tables.
- `k8s-ui/components/resource-detail-view.tsx` — migrate events table.
- `.vscode/mcp.json` (new) — GitHub Copilot shadcn MCP server.
- `.opencode/opencode.jsonc` (new) — OpenCode shadcn MCP server.
- `skills-lock.json`, `.agents/skills/shadcn/`, `.agents/skills/
  migrate-radix-to-base/` — already-installed skill files folded into this
  feature's commit.
- Potential `k8s-ui/package.json` / `yarn.lock` — TanStack and any shadcn
  runtime deps; `@tanstack/react-table` is required for Data Table.

## Data / contracts

- No backend or API contract changes. Data Table consumes the exact same
  fetched `items` arrays (`Resource`, `Namespace`, `NamespaceMetricSummary`,
  events) already produced by the existing BFF routes; client-side sorting,
  filtering, and pagination only.
- Frontend-only convention: one `DataTable<T>` component + per-view column
  definitions; table logic is not duplicated across pages. Reuse existing
  formatters in `lib/metrics.ts` and `lib/status-tone.ts` for unit/pill
  rendering.

## Testing

- **Build/lint (`uiEvidence: when-available`):** no frontend test runner is
  configured. Verify with `cd k8s-ui && yarn build` (clean) and `yarn lint`
  (clean on changed files). Browser-verify against the running app: each table
  still shows the correct columns and values; sorting arrow works; the filter
  narrows rows; pager moves pages; loading/empty (e.g. no resources in a
  namespace) and metrics-unavailable notice still render; layout, spacing,
  colors, and pills match the prior design.
- **Backend:** not touched; the documented backend syntax check/tests are not
  required for this feature (no backend changes).

## Notes for the AI

- Use the installed `shadcn` skill rules (semantic tokens where the new
  components touch color, `gap-*` not `space-*`, `cn()`, `size-*`, `data-icon`,
  `asChild`/`render` per Base UI). Prefer shadcn primitives over hand-rolled
  table markup, but apply the project's existing slate classes at the cell/
  container level to preserve the current design.
- The migration is design-preserving: do not let default shadcn styling replace
  the current slate/cyan look. Where a shadcn primitive's default differs, pass
  the existing classes or `breakpoints`/`className` to match the current UI.
- Do not re-derive or re-fetch anything; the fetch/polling logic in each view
  stays untouched, only the `<table>` render is replaced.
- Keep the fetch/AbortController/`usePolling` patterns in each view unchanged.
- Do not add TanStack Pagination/Sorting features that require backend paging;
  everything is client-side over the in-memory list.
- Re-run `yarn build` after each migration step; the build is the final gate.

## Open questions

- **Data Table enhancement scope.** The user approved enabling sorting,
  filtering, and pagination "now" on the migrated tables (none existed). Beyond
  a single text filter, the exact filter placement (header vs toolbar) is a
  reversible presentation choice defaulting to a toolbar search box above each
  table; pagination defaults to prior/next controls with a per-page count. No
  product decision remains open for implementation.
