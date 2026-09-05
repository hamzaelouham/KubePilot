"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { healthTone, type Health } from "@/lib/status-tone";
import { formatLastUpdated, usePolling } from "@/lib/use-polling";
import { DataTable, type DataTableColumn } from "@/components/data-table";

type Resource = { cluster: string; namespace: string | null; kind: string; name: string; status: string; health: Health };
type ResourceResponse = { items: Resource[]; message?: string };

type WorkloadsState =
  | { status: "loading" }
  | { status: "ready"; items: Resource[] }
  | { status: "error"; message: string };

const workloadKinds: { resource: string; kind: string; label: string }[] = [
  { resource: "pods", kind: "Pod", label: "Pods" },
  { resource: "deployments", kind: "Deployment", label: "Deployments" },
  { resource: "stateful-sets", kind: "StatefulSet", label: "Stateful Sets" },
  { resource: "daemon-sets", kind: "DaemonSet", label: "Daemon Sets" },
  { resource: "jobs", kind: "Job", label: "Jobs" },
];

const resourceTypeByKind = new Map(workloadKinds.map(({ kind, resource }) => [kind, resource]));

type WorkloadRow = Resource;

const tableColumns: DataTableColumn<WorkloadRow>[] = [
  {
    accessorKey: "name",
    header: "Name",
    cell: ({ row }) => {
      const item = row.original;
      return (
        <Link
          href={`/dashboard/detail?resourceType=${resourceTypeByKind.get(item.kind) ?? "pods"}&name=${encodeURIComponent(item.name)}${item.namespace ? `&namespace=${encodeURIComponent(item.namespace)}` : ""}`}
          className="font-medium text-cyan-600 hover:underline"
        >
          {item.name}
        </Link>
      );
    },
  },
  {
    accessorKey: "kind",
    header: "Kind",
    cell: ({ row }) => <span className="text-sm">{row.original.kind}</span>,
  },
  {
    accessorKey: "namespace",
    header: "Namespace",
    cell: ({ row }) => <span className="text-sm">{row.original.namespace ?? "All namespaces"}</span>,
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => <span className="text-sm">{row.original.status}</span>,
  },
  {
    accessorKey: "health",
    header: "Health",
    cell: ({ row }) => (
      <span className={`inline-flex rounded-full px-2 py-1 text-sm font-medium ${healthTone(row.original.health).pill}`}>
        {healthTone(row.original.health).short}
      </span>
    ),
  },
];

export function WorkloadsView() {
  const [state, setState] = useState<WorkloadsState>({ status: "loading" });
  const abortRef = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
    const controller = new AbortController();
    abortRef.current?.abort();
    abortRef.current = controller;
    try {
      const responses = await Promise.all(
        workloadKinds.map(({ resource }) =>
          fetch(`/api/cluster/resources?resource=${resource}`, { signal: controller.signal, cache: "no-store" }).then(async (r) => {
            const body = (await r.json()) as ResourceResponse;
            if (!r.ok) throw new Error(body.message ?? `Unable to load ${resource}`);
            return body.items;
          }),
        ),
      );
      const items = responses.flat();
      setState({ status: "ready", items });
    } catch (error: unknown) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setState({ status: "error", message: error instanceof Error ? error.message : "Unable to load workloads" });
    }
  }, []);

  useEffect(() => {
    abortRef.current?.abort();
    setState({ status: "loading" });
    load();
    return () => abortRef.current?.abort();
  }, [load]);

  const { refresh, lastUpdated } = usePolling(load);

  if (state.status === "loading") return <p className="rounded-lg bg-muted p-5 text-muted-foreground">Loading workloads...</p>;
  if (state.status === "error") return <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-5 text-red-700">{state.message}</p>;

  const { items } = state;
  const unhealthy = items.filter((r) => r.health === "warning" || r.health === "error");
  const counts = new Map<string, number>();
  for (const { label, kind } of workloadKinds) counts.set(label, items.filter((i) => i.kind === kind).length);

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="text-sm font-medium uppercase tracking-[0.2em] text-muted-foreground">Live cluster data</p>
          <h2 className="text-3xl font-semibold text-foreground">Workloads</h2>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={refresh}
            className="cursor-pointer rounded-xl border border-border bg-card px-3 py-2 text-sm font-medium text-foreground transition hover:bg-muted"
          >
            Refresh
          </button>
          <span className="text-sm text-muted-foreground">Updated {formatLastUpdated(lastUpdated)}</span>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-5">
        {workloadKinds.map(({ label, resource }) => (
          <div key={resource} className="rounded-xl border border-border bg-card p-5">
            <p className="text-sm text-muted-foreground">{label}</p>
            <p className="mt-1 text-3xl font-semibold text-foreground">{counts.get(label) ?? 0}</p>
          </div>
        ))}
      </div>

      {unhealthy.length > 0 && (
        <div role="alert" className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-amber-800">
          <p className="font-medium">{unhealthy.length} workload{unhealthy.length === 1 ? "" : "s"} need attention</p>
          <ul className="mt-2 list-inside list-disc space-y-1 text-sm">
            {unhealthy.map((r) => (
              <li key={`${r.kind}-${r.namespace ?? "cluster"}-${r.name}`}>
                {r.kind} <span className="font-medium">{r.name}</span>
                {r.namespace ? ` (${r.namespace})` : ""} — {r.health}
              </li>
            ))}
          </ul>
        </div>
      )}

      <DataTable columns={tableColumns} data={items} placeholder="No workloads found." />
    </div>
  );
}
