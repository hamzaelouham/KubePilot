"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { healthTone, type Health } from "@/lib/status-tone";
import { formatLastUpdated, usePolling } from "@/lib/use-polling";
import { useCluster } from "@/lib/cluster-context";
import { withCluster } from "@/lib/cluster-query";
import { DataTable, type DataTableColumn } from "@/components/data-table";
import {
  formatMillicores,
  formatBytes,
  utilizationPercent,
  utilizationToneClasses,
  type NodeMetricItem,
  type WorkloadMetricItem,
  type StorageMetricsItem,
  type NodesMetricsResponse,
  type NamespaceMetricsResponse,
  type StorageMetricsResponse,
} from "@/lib/metrics";

type Resource = {
  cluster: string;
  namespace: string | null;
  kind: string;
  name: string;
  status: string;
  health: Health;
};

type ResourceResponse = { items: Resource[] };
type ResourceState =
  | { status: "loading" }
  | { status: "ready"; items: Resource[] }
  | { status: "error"; message: string };

type MetricsState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; available: boolean; nodeItems: NodeMetricItem[]; workloadItems: WorkloadMetricItem[]; storageItems: StorageMetricsItem[] }
  | { status: "error"; message: string };

const clusterScoped = new Set(["nodes", "persistent-volumes", "cluster-roles", "storage-classes"]);
const nodeMetricsResources = new Set(["nodes"]);
const workloadMetricsResources = new Set(["pods", "deployments", "daemon-sets", "stateful-sets"]);
const storageMetricsResources = new Set(["persistent-volumes", "persistent-volume-claims"]);
const metricsEnabledResources = new Set([...nodeMetricsResources, ...workloadMetricsResources, ...storageMetricsResources]);

type ResourceRow = Resource;

function nameColumn(resource: string): DataTableColumn<ResourceRow> {
  return {
    accessorKey: "name",
    header: "Name",
    cell: ({ row }) => {
      const item = row.original;
      const detailParams = new URLSearchParams({
        resourceType: resource,
        name: item.name,
      });
      if (item.namespace) detailParams.set("namespace", item.namespace);
      return (
        <Link
          href={`/dashboard/detail?${detailParams}`}
          className="font-medium text-cyan-600 hover:underline"
        >
          {item.name}
        </Link>
      );
    },
  };
}

const namespaceColumn: DataTableColumn<ResourceRow> = {
  accessorKey: "namespace",
  header: "Namespace",
  cell: ({ row }) => row.original.namespace ?? "All namespaces",
};

const clusterColumn: DataTableColumn<ResourceRow> = {
  accessorKey: "cluster",
  header: "Cluster",
};

function nodeCpuColumn(metrics: Map<string, NodeMetricItem>): DataTableColumn<ResourceRow> {
  return {
    id: "cpu",
    header: "CPU",
    cell: ({ row }) => {
      const metric = metrics.get(row.original.name);
      if (!metric) return <span className="text-muted-foreground">—</span>;
      const cpuPercent = utilizationPercent(metric.cpu_usage_millicores, metric.cpu_allocatable_millicores);
      return (
        <span className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${utilizationToneClasses(cpuPercent !== null && cpuPercent >= 90 ? "critical" : cpuPercent !== null && cpuPercent >= 70 ? "warning" : "good")}`}>
          {formatMillicores(metric.cpu_usage_millicores)} / {metric.cpu_allocatable_millicores !== null ? formatMillicores(metric.cpu_allocatable_millicores) : "—"}
          {cpuPercent !== null ? ` (${cpuPercent}%)` : ""}
        </span>
      );
    },
  };
}

function nodeMemoryColumn(metrics: Map<string, NodeMetricItem>): DataTableColumn<ResourceRow> {
  return {
    id: "memory",
    header: "Memory",
    cell: ({ row }) => {
      const metric = metrics.get(row.original.name);
      if (!metric) return <span className="text-muted-foreground">—</span>;
      const memPercent = utilizationPercent(metric.memory_usage_bytes, metric.memory_allocatable_bytes);
      return (
        <span className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${utilizationToneClasses(memPercent !== null && memPercent >= 90 ? "critical" : memPercent !== null && memPercent >= 70 ? "warning" : "good")}`}>
          {formatBytes(metric.memory_usage_bytes)} / {metric.memory_allocatable_bytes !== null ? formatBytes(metric.memory_allocatable_bytes) : "—"}
          {memPercent !== null ? ` (${memPercent}%)` : ""}
        </span>
      );
    },
  };
}

function workloadCpuColumn(metrics: Map<string, WorkloadMetricItem>): DataTableColumn<ResourceRow> {
  return {
    id: "cpu",
    header: "CPU",
    cell: ({ row }) => {
      const metric = metrics.get(row.original.name);
      return metric ? (
        <span className="text-sm">{formatMillicores(metric.cpu_usage_millicores)}</span>
      ) : (
        <span className="text-muted-foreground">—</span>
      );
    },
  };
}

function workloadMemoryColumn(metrics: Map<string, WorkloadMetricItem>): DataTableColumn<ResourceRow> {
  return {
    id: "memory",
    header: "Memory",
    cell: ({ row }) => {
      const metric = metrics.get(row.original.name);
      return metric ? (
        <span className="text-sm">{formatBytes(metric.memory_usage_bytes)}</span>
      ) : (
        <span className="text-muted-foreground">—</span>
      );
    },
  };
}

function capacityColumn(metrics: Map<string, StorageMetricsItem>): DataTableColumn<ResourceRow> {
  return {
    id: "capacity",
    header: "Capacity",
    cell: ({ row }) => {
      const capacityBytes = metrics.get(row.original.name)?.capacity_bytes;
      return capacityBytes != null ? (
        <span className="text-sm">{formatBytes(capacityBytes)}</span>
      ) : (
        <span className="text-muted-foreground">—</span>
      );
    },
  };
}

const statusColumn: DataTableColumn<ResourceRow> = {
  accessorKey: "status",
  header: "Status",
  cell: ({ row }) => (
    <span className={`inline-flex rounded-full px-2 py-1 text-sm font-medium ${healthTone(row.original.health).pill}`}>
      {row.original.status}
    </span>
  ),
};

export function CoreResourceView({ resource, namespace }: { resource: string; namespace: string }) {
  const [state, setState] = useState<ResourceState>({ status: "loading" });
  const [metricsState, setMetricsState] = useState<MetricsState>({ status: "idle" });
  const abortRef = useRef<AbortController | null>(null);
  const metricsAbortRef = useRef<AbortController | null>(null);
  const cluster = useCluster();

  const load = useCallback(async () => {
    const controller = new AbortController();
    abortRef.current?.abort();
    abortRef.current = controller;
    try {
      const response = await fetch(
        withCluster(`/api/cluster/resources?resource=${encodeURIComponent(resource)}&namespace=${encodeURIComponent(namespace)}`, cluster),
        { signal: controller.signal, cache: "no-store" },
      );
      const body = (await response.json()) as ResourceResponse & { message?: string };
      if (!response.ok) throw new Error(body.message ?? "Unable to load resources");
      setState({ status: "ready", items: body.items });
    } catch (error: unknown) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setState({ status: "error", message: error instanceof Error ? error.message : "Unable to load resources" });
    }
  }, [cluster, namespace, resource]);

  const loadMetrics = useCallback(async () => {
    if (!metricsEnabledResources.has(resource)) return;
    const controller = new AbortController();
    metricsAbortRef.current?.abort();
    metricsAbortRef.current = controller;
    setMetricsState({ status: "loading" });
    try {
      if (nodeMetricsResources.has(resource)) {
        const response = await fetch(withCluster("/api/cluster/metrics?type=nodes", cluster), {
          signal: controller.signal,
          cache: "no-store",
        });
        const body = (await response.json()) as NodesMetricsResponse & { message?: string };
        if (!response.ok) throw new Error(body.message ?? "Unable to load metrics");
        setMetricsState({ status: "ready", available: body.available, nodeItems: body.items, workloadItems: [], storageItems: [] });
      } else if (workloadMetricsResources.has(resource)) {
        const targetNs = namespace && namespace !== "All namespaces" ? namespace : "default";
        const response = await fetch(withCluster(`/api/cluster/metrics?type=namespaces&namespace=${encodeURIComponent(targetNs)}`, cluster), {
          signal: controller.signal,
          cache: "no-store",
        });
        const body = (await response.json()) as NamespaceMetricsResponse & { message?: string };
        if (!response.ok) throw new Error(body.message ?? "Unable to load metrics");
        setMetricsState({ status: "ready", available: body.available, nodeItems: [], workloadItems: body.workloads, storageItems: [] });
      } else if (storageMetricsResources.has(resource)) {
        const response = await fetch(withCluster("/api/cluster/metrics?type=storage", cluster), {
          signal: controller.signal,
          cache: "no-store",
        });
        const body = (await response.json()) as StorageMetricsResponse & { message?: string };
        if (!response.ok) throw new Error(body.message ?? "Unable to load metrics");
        setMetricsState({ status: "ready", available: body.available, nodeItems: [], workloadItems: [], storageItems: body.items });
      }
    } catch (error: unknown) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setMetricsState({ status: "error", message: error instanceof Error ? error.message : "Unable to load metrics" });
    }
  }, [cluster, resource, namespace]);

  const requestKey = `${resource}\0${namespace}`;
  const [prevRequestKey, setPrevRequestKey] = useState(requestKey);
  if (prevRequestKey !== requestKey) {
    setPrevRequestKey(requestKey);
    setState({ status: "loading" });
    setMetricsState({ status: "idle" });
  }

  useEffect(() => {
    abortRef.current?.abort();
    metricsAbortRef.current?.abort();
    void Promise.resolve().then(load);
    if (metricsEnabledResources.has(resource)) void Promise.resolve().then(loadMetrics);
    return () => {
      abortRef.current?.abort();
      metricsAbortRef.current?.abort();
    };
  }, [load, loadMetrics, resource]);

  const { refresh, lastUpdated } = usePolling(async () => {
    await Promise.all([
      load(),
      metricsEnabledResources.has(resource) ? loadMetrics() : Promise.resolve(),
    ]);
  });

  const title = resource.charAt(0).toUpperCase() + resource.slice(1);

  const nodeMetricsByName = new Map<string, NodeMetricItem>();
  const workloadMetricsByName = new Map<string, WorkloadMetricItem>();
  const storageMetricsByName = new Map<string, StorageMetricsItem>();
  if (metricsState.status === "ready" && metricsState.available) {
    for (const item of metricsState.nodeItems) nodeMetricsByName.set(item.name, item);
    for (const item of metricsState.workloadItems) workloadMetricsByName.set(item.name, item);
    for (const item of metricsState.storageItems) storageMetricsByName.set(item.name, item);
  }

  const tableColumns: DataTableColumn<ResourceRow>[] = [
    nameColumn(resource),
    ...(clusterScoped.has(resource) ? [] : [namespaceColumn]),
    ...(nodeMetricsResources.has(resource)
      ? [nodeCpuColumn(nodeMetricsByName), nodeMemoryColumn(nodeMetricsByName)]
      : []),
    ...(workloadMetricsResources.has(resource)
      ? [workloadCpuColumn(workloadMetricsByName), workloadMemoryColumn(workloadMetricsByName)]
      : []),
    ...(storageMetricsResources.has(resource) ? [capacityColumn(storageMetricsByName)] : []),
    statusColumn,
    ...(resource === "nodes" ? [clusterColumn] : []),
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-2">
        <div>
          <p className="text-sm font-medium uppercase tracking-[0.2em] text-muted-foreground">Live cluster data</p>
          <h2 className="text-3xl font-semibold text-foreground">{title}</h2>
        </div>
        <div className="flex items-center gap-3">
          <span className="rounded-full bg-cyan-100 px-3 py-1 text-sm font-medium text-cyan-800">FastAPI</span>
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

      {state.status === "loading" ? <p className="rounded-lg bg-muted p-5 text-muted-foreground">Loading {title.toLowerCase()}...</p> : null}
      {state.status === "error" ? <p role="alert" className="rounded-lg border border-destructive/40 bg-destructive/10 p-5 text-destructive">{state.message}</p> : null}

      {metricsEnabledResources.has(resource) && metricsState.status === "ready" && !metricsState.available && (
        <p className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-700">
          Metrics are unavailable. Metrics server may not be installed in this cluster.
        </p>
      )}

      {state.status === "ready" && state.items.length === 0 ? <p className="rounded-lg bg-muted p-5 text-muted-foreground">No {title.toLowerCase()} found for this scope.</p> : null}
      {state.status === "ready" && state.items.length > 0 ? (
        <DataTable
          columns={tableColumns}
          data={state.items}
          placeholder={`No ${title.toLowerCase()} found for this scope.`}
          searchPlaceholder={`Filter ${title.toLowerCase()}…`}
        />
      ) : null}
    </div>
  );
}
