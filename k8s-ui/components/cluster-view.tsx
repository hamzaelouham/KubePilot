"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { healthTone, type Health } from "@/lib/status-tone";
import { formatLastUpdated, usePolling } from "@/lib/use-polling";
import { MetricBar } from "@/components/metric-bar";
import { DataTable, type DataTableColumn } from "@/components/data-table";
import {
  formatMillicores,
  formatBytes,
  utilizationPercent,
  type NodeMetricItem,
  type StorageMetricsItem,
  type NodesMetricsResponse,
  type StorageMetricsResponse,
} from "@/lib/metrics";

type Resource = { cluster: string; namespace: string | null; kind: string; name: string; status: string; health: Health };
type ResourceResponse = { items: Resource[]; message?: string };

type Namespace = { name: string; status: string };
type NamespaceResponse = { items: Namespace[] };

type ClusterState =
  | { status: "loading" }
  | {
      status: "ready";
      namespaces: Namespace[];
      nodes: Resource[];
      storageClasses: Resource[];
      persistentVolumes: Resource[];
      nodeMetrics: NodeMetricItem[];
      storageMetrics: StorageMetricsItem[];
      metricsAvailable: boolean;
    }
  | { status: "error"; message: string };

type ClusterResourceRow = Resource;

function nodeNameColumn(): DataTableColumn<ClusterResourceRow> {
  return {
    accessorKey: "name",
    header: "Name",
    cell: ({ row }) => (
      <Link
        href={`/dashboard/detail?resourceType=nodes&name=${encodeURIComponent(row.original.name)}`}
        className="font-medium text-cyan-600 hover:underline"
      >
        {row.original.name}
      </Link>
    ),
  };
}

function nodeUtilizationColumn(
  kind: "cpu" | "memory",
  metrics: Map<string, NodeMetricItem>,
): DataTableColumn<ClusterResourceRow> {
  const header = kind === "cpu" ? "CPU" : "Memory";
  const label = header;
  const usage = (metric: NodeMetricItem) =>
    kind === "cpu" ? metric.cpu_usage_millicores : metric.memory_usage_bytes;
  const allocatable = (metric: NodeMetricItem) =>
    kind === "cpu" ? metric.cpu_allocatable_millicores : metric.memory_allocatable_bytes;
  const format = (value: number) => (kind === "cpu" ? formatMillicores(value) : formatBytes(value));
  return {
    id: kind,
    header,
    cell: ({ row }) => {
      const metric = metrics.get(row.original.name);
      const percent = metric ? utilizationPercent(usage(metric), allocatable(metric)) : null;
      return (
        <MetricBar
          label={label}
          value={metric ? `${format(usage(metric))}${percent !== null ? ` (${percent}%)` : ""}` : "—"}
          percent={percent}
          toneClass="text-foreground"
        />
      );
    },
  };
}

const clusterStatusColumn: DataTableColumn<ClusterResourceRow> = {
  accessorKey: "health",
  header: "Status",
  cell: ({ row }) => (
    <span className={`inline-flex rounded-full px-2 py-1 text-sm font-medium ${healthTone(row.original.health).pill}`}>
      {healthTone(row.original.health).short}
    </span>
  ),
};

function pvNameColumn(): DataTableColumn<ClusterResourceRow> {
  return {
    accessorKey: "name",
    header: "Name",
    cell: ({ row }) => <span className="font-medium">{row.original.name}</span>,
  };
}

function pvCapacityColumn(metrics: Map<string, StorageMetricsItem>): DataTableColumn<ClusterResourceRow> {
  return {
    id: "capacity",
    header: "Capacity",
    cell: ({ row }) => {
      const capacityBytes = metrics.get(row.original.name)?.capacity_bytes;
      return <span className="text-sm">{capacityBytes != null ? formatBytes(capacityBytes) : "—"}</span>;
    },
  };
}

const storageClassNameColumn: DataTableColumn<ClusterResourceRow> = {
  accessorKey: "name",
  header: "Name",
  cell: ({ row }) => <span className="font-medium">{row.original.name}</span>,
};

export function ClusterView() {
  const [state, setState] = useState<ClusterState>({ status: "loading" });
  const abortRef = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
    const controller = new AbortController();
    abortRef.current?.abort();
    abortRef.current = controller;
    try {
      const [namespaces, nodes, storageClasses, persistentVolumes, nodesMetrics, storageMetrics] = await Promise.all([
        fetch("/api/cluster/namespaces", { signal: controller.signal, cache: "no-store" }).then(async (r) => {
          const body = (await r.json()) as NamespaceResponse;
          if (!r.ok) throw new Error("Unable to load namespaces");
          return body.items;
        }),
        fetch("/api/cluster/resources?resource=nodes", { signal: controller.signal, cache: "no-store" }).then(async (r) => {
          const body = (await r.json()) as ResourceResponse;
          if (!r.ok) throw new Error(body.message ?? "Unable to load nodes");
          return body.items;
        }),
        fetch("/api/cluster/resources?resource=storage-classes", { signal: controller.signal, cache: "no-store" }).then(async (r) => {
          const body = (await r.json()) as ResourceResponse;
          if (!r.ok) throw new Error(body.message ?? "Unable to load storage classes");
          return body.items;
        }),
        fetch("/api/cluster/resources?resource=persistent-volumes", { signal: controller.signal, cache: "no-store" }).then(async (r) => {
          const body = (await r.json()) as ResourceResponse;
          if (!r.ok) throw new Error(body.message ?? "Unable to load persistent volumes");
          return body.items;
        }),
        fetch("/api/cluster/metrics?type=nodes", { signal: controller.signal, cache: "no-store" }).then(async (r) => {
          const body = (await r.json()) as NodesMetricsResponse;
          return body;
        }),
        fetch("/api/cluster/metrics?type=storage", { signal: controller.signal, cache: "no-store" }).then(async (r) => {
          const body = (await r.json()) as StorageMetricsResponse;
          return body;
        }),
      ]);
      setState({
        status: "ready",
        namespaces,
        nodes,
        storageClasses,
        persistentVolumes,
        nodeMetrics: nodesMetrics.available ? nodesMetrics.items : [],
        storageMetrics: storageMetrics.available ? storageMetrics.items : [],
        metricsAvailable: nodesMetrics.available && storageMetrics.available,
      });
    } catch (error: unknown) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setState({ status: "error", message: error instanceof Error ? error.message : "Unable to load cluster data" });
    }
  }, []);

  useEffect(() => {
    abortRef.current?.abort();
    setState({ status: "loading" });
    load();
    return () => abortRef.current?.abort();
  }, [load]);

  const { refresh, lastUpdated } = usePolling(load);

  if (state.status === "loading") return <p className="rounded-lg bg-muted p-5 text-muted-foreground">Loading cluster data...</p>;
  if (state.status === "error") return <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-5 text-red-700">{state.message}</p>;

  const { namespaces, nodes, storageClasses, persistentVolumes, nodeMetrics, storageMetrics, metricsAvailable } = state;
  const nodeMetricsByName = new Map(nodeMetrics.map((n) => [n.name, n]));
  const storageMetricsByName = new Map(storageMetrics.map((s) => [s.name, s]));

  const nodeColumns: DataTableColumn<ClusterResourceRow>[] = [
    nodeNameColumn(),
    nodeUtilizationColumn("cpu", nodeMetricsByName),
    nodeUtilizationColumn("memory", nodeMetricsByName),
    clusterStatusColumn,
  ];
  const pvColumns: DataTableColumn<ClusterResourceRow>[] = [
    pvNameColumn(),
    pvCapacityColumn(storageMetricsByName),
    {
      accessorKey: "status",
      header: "Status",
      cell: ({ row }) => <span className="text-sm">{row.original.status}</span>,
    },
  ];
  const storageClassColumns: DataTableColumn<ClusterResourceRow>[] = [storageClassNameColumn];

  const totalCpu = nodeMetrics.reduce((sum, n) => sum + (n.cpu_usage_millicores ?? 0), 0);
  const totalMemory = nodeMetrics.reduce((sum, n) => sum + (n.memory_usage_bytes ?? 0), 0);
  const unhealthyNodes = nodes.filter((n) => n.health === "warning" || n.health === "error").length;

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="text-sm font-medium uppercase tracking-[0.2em] text-muted-foreground">Live cluster data</p>
          <h2 className="text-3xl font-semibold text-foreground">Cluster</h2>
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

      <div className="grid gap-4 md:grid-cols-4">
        <div className="rounded-xl border border-border bg-card p-5">
          <p className="text-sm text-muted-foreground">Namespaces</p>
          <p className="mt-1 text-3xl font-semibold text-foreground">{namespaces.length}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-5">
          <p className="text-sm text-muted-foreground">Nodes</p>
          <p className="mt-1 text-3xl font-semibold text-foreground">{nodes.length}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-5">
          <p className="text-sm text-muted-foreground">Aggregate CPU</p>
          <p className="mt-1 text-3xl font-semibold text-foreground">{metricsAvailable ? formatMillicores(totalCpu) : "—"}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-5">
          <p className="text-sm text-muted-foreground">Aggregate Memory</p>
          <p className="mt-1 text-3xl font-semibold text-foreground">{metricsAvailable ? formatBytes(totalMemory) : "—"}</p>
        </div>
      </div>

      {unhealthyNodes > 0 && (
        <div role="alert" className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-amber-800">
          <p className="font-medium">{unhealthyNodes} node{unhealthyNodes === 1 ? "" : "s"} need attention</p>
        </div>
      )}

      <DataTable
        title={<h3 className="text-2xl font-semibold text-foreground">Node Utilization</h3>}
        columns={nodeColumns}
        data={nodes}
        placeholder="No nodes found."
        searchPlaceholder="Filter nodes…"
      />
      {!metricsAvailable && (
        <p className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-700">
          Node metrics are unavailable. Metrics server may not be installed in this cluster.
        </p>
      )}

      <DataTable
        title={<h3 className="text-2xl font-semibold text-foreground">Persistent Volumes</h3>}
        columns={pvColumns}
        data={persistentVolumes}
        placeholder="No persistent volumes found."
        searchPlaceholder="Filter persistent volumes…"
      />

      <DataTable
        title={<h3 className="text-2xl font-semibold text-foreground">Storage Classes</h3>}
        columns={storageClassColumns}
        data={storageClasses}
        placeholder="No storage classes found."
        searchPlaceholder="Filter storage classes…"
      />
    </div>
  );
}
