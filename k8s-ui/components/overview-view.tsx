"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { healthTone, type Health } from "@/lib/status-tone";
import { formatLastUpdated, usePolling } from "@/lib/use-polling";
import { DataTable, type DataTableColumn } from "@/components/data-table";
import { formatMillicores, formatBytes, type NamespaceMetricSummary, type MetricsSummaryResponse } from "@/lib/metrics";

type Resource = { cluster: string; namespace: string | null; kind: string; name: string; status: string; health: Health };
type ResourceResponse = { items: Resource[]; message?: string };

type OverviewState =
  | { status: "loading" }
  | { status: "ready"; deployments: Resource[]; pods: Resource[]; namespaceSummary: NamespaceMetricSummary[]; metricsAvailable: boolean }
  | { status: "error"; message: string };

type OverviewResourceRow = Resource;

const namespaceUtilizationColumns: DataTableColumn<NamespaceMetricSummary>[] = [
  {
    accessorKey: "namespace",
    header: "Namespace",
    cell: ({ row }) => <span className="font-medium">{row.original.namespace}</span>,
  },
  {
    accessorKey: "cpu_usage_millicores",
    header: "CPU",
    cell: ({ row }) => <span className="text-sm">{formatMillicores(row.original.cpu_usage_millicores)}</span>,
  },
  {
    accessorKey: "memory_usage_bytes",
    header: "Memory",
    cell: ({ row }) => <span className="text-sm">{formatBytes(row.original.memory_usage_bytes)}</span>,
  },
  {
    accessorKey: "pod_count",
    header: "Pods",
    cell: ({ row }) => <span>{row.original.pod_count}</span>,
  },
];

const deploymentColumns: DataTableColumn<OverviewResourceRow>[] = [
  {
    accessorKey: "name",
    header: "Name",
    cell: ({ row }) => <span className="font-medium">{row.original.name}</span>,
  },
  {
    accessorKey: "namespace",
    header: "Namespace",
    cell: ({ row }) => (
      <span className="inline-flex rounded-full bg-muted px-2 py-1 text-sm text-muted-foreground">
        {row.original.namespace ?? "All namespaces"}
      </span>
    ),
  },
  {
    accessorKey: "status",
    header: "Ready",
    cell: ({ row }) => <span>{row.original.status}</span>,
  },
  {
    accessorKey: "health",
    header: "Status",
    cell: ({ row }) => (
      <span className={`inline-flex rounded-full px-2 py-1 text-sm font-medium ${healthTone(row.original.health).pill}`}>
        {healthTone(row.original.health).short}
      </span>
    ),
  },
];

function DonutChart({ values, colors }: { values: number[]; colors: string[] }) {
  const [a, b] = values;
  const total = a + b;
  const degrees = total > 0 ? (a / total) * 360 : 0;

  return (
    <div className="relative mx-auto h-28 w-28">
      <div
        className="absolute inset-0 rounded-full"
        style={{
          background: `conic-gradient(${colors[0]} 0deg ${degrees}deg, ${colors[1]} ${degrees}deg 360deg)`,
        }}
      />
      <div className="absolute inset-[18px] rounded-full bg-surface" />
      <div className="absolute inset-0 flex items-center justify-center text-sm font-medium text-foreground">
        <span>{total > 0 ? Math.round((a / total) * 100) : 0}%</span>
      </div>
    </div>
  );
}

export function OverviewView() {
  const [state, setState] = useState<OverviewState>({ status: "loading" });
  const abortRef = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
    const controller = new AbortController();
    abortRef.current?.abort();
    abortRef.current = controller;
    try {
      const [deployments, pods, summaryResponse] = await Promise.all([
        fetch("/api/cluster/resources?resource=deployments", { signal: controller.signal, cache: "no-store" }).then(async (r) => {
          const body = (await r.json()) as ResourceResponse;
          if (!r.ok) throw new Error(body.message ?? "Unable to load deployments");
          return body.items;
        }),
        fetch("/api/cluster/resources?resource=pods", { signal: controller.signal, cache: "no-store" }).then(async (r) => {
          const body = (await r.json()) as ResourceResponse;
          if (!r.ok) throw new Error(body.message ?? "Unable to load pods");
          return body.items;
        }),
        fetch("/api/cluster/metrics?type=summary", { signal: controller.signal, cache: "no-store" }).then(async (r) => {
          const body = (await r.json()) as MetricsSummaryResponse;
          return body;
        }),
      ]);
      setState({
        status: "ready",
        deployments,
        pods,
        namespaceSummary: summaryResponse.available ? summaryResponse.namespaces : [],
        metricsAvailable: summaryResponse.available,
      });
    } catch (error: unknown) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setState({ status: "error", message: error instanceof Error ? error.message : "Unable to load cluster data" });
    }
  }, []);

  useEffect(() => {
    abortRef.current?.abort();
    void Promise.resolve().then(load);
    return () => abortRef.current?.abort();
  }, [load]);

  const { refresh, lastUpdated } = usePolling(load);

  if (state.status === "loading") return <p className="rounded-lg bg-muted p-5 text-muted-foreground">Loading cluster overview...</p>;
  if (state.status === "error") return <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-5 text-red-700">{state.message}</p>;

  const { deployments, pods, namespaceSummary, metricsAvailable } = state;

  const unhealthy = [...deployments, ...pods].filter((r) => r.health === "warning" || r.health === "error");
  const deploymentsHealthy = deployments.filter((d) => d.health === "healthy").length;
  const deploymentsNotHealthy = deployments.length - deploymentsHealthy;
  const podsHealthy = pods.filter((p) => p.health === "healthy").length;
  const podsNotHealthy = pods.length - podsHealthy;

  const pieData = [
    { label: "Deployments", values: [deploymentsHealthy, deploymentsNotHealthy], color: ["#22c55e", "#e74c3c"] },
    { label: "Pods", values: [podsHealthy, podsNotHealthy], color: ["#22c55e", "#e74c3c"] },
  ];

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="text-sm font-medium uppercase tracking-[0.2em] text-muted-foreground">Live cluster data</p>
          <h2 className="text-3xl font-semibold text-foreground">Overview</h2>
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

      {unhealthy.length > 0 ? (
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
      ) : null}

      <div className="rounded-xl border border-border bg-muted p-5">
        <h3 className="mb-6 text-2xl font-semibold text-foreground">Workload Status</h3>
        <div className="grid gap-8 md:grid-cols-2">
          {pieData.map((pie) => (
            <div key={pie.label} className="text-center">
              <div className="flex justify-center">
                <DonutChart values={pie.values} colors={pie.color} />
              </div>
              <p className="mt-3 text-lg text-foreground">{pie.label}</p>
              <p className="text-sm text-muted-foreground">{pie.values[0]} healthy / {pie.values[0] + pie.values[1]} total</p>
            </div>
          ))}
        </div>
      </div>

      {namespaceSummary.length > 0 && (
        <DataTable
          title={<h3 className="text-2xl font-semibold text-foreground">Namespace Utilization</h3>}
          columns={namespaceUtilizationColumns}
          data={namespaceSummary}
          searchPlaceholder="Filter namespaces…"
        />
      )}

      {!metricsAvailable && namespaceSummary.length === 0 && (
        <p className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-700">
          Namespace metrics are unavailable. Metrics server may not be installed in this cluster.
        </p>
      )}

      <DataTable
        title={<h3 className="text-2xl font-semibold text-foreground">Deployments</h3>}
        columns={deploymentColumns}
        data={deployments}
        placeholder="No deployments found."
        searchPlaceholder="Filter deployments…"
      />
    </div>
  );
}
