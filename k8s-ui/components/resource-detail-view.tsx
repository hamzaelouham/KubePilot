"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { DashboardShell } from "@/components/dashboard-shell";
import { useClusterStatus } from "@/lib/use-cluster-status";
import { MetricBar } from "@/components/metric-bar";
import { usePolling } from "@/lib/use-polling";
import { DataTable, type DataTableColumn } from "@/components/data-table";
import {
  formatMillicores,
  formatBytes,
  utilizationPercent,
  type NodeMetricItem,
  type WorkloadMetricItem,
  type StorageMetricsItem,
} from "@/lib/metrics";

type DetailData = {
  cluster: string;
  resource_type: string;
  name: string;
  namespace: string | null;
  kind: string;
  status: string;
  metadata: Record<string, string>;
  source: string;
};

type YamlData = {
  content: string;
  truncated: boolean;
};

type LogData = {
  lines: string[];
  container: string | null;
  truncated: boolean;
};

type EventItem = {
  type: string;
  reason: string;
  message: string;
  source: string;
  created_at: string | null;
};

type EventData = {
  items: EventItem[];
  truncated: boolean;
};

const eventColumns: DataTableColumn<EventItem>[] = [
  {
    accessorKey: "type",
    header: "Type",
    cell: ({ row }) => {
      const warning = row.original.type === "Warning";
      return (
        <span className={`rounded-full px-2 py-1 text-xs font-medium ${warning ? "bg-amber-100 text-amber-700" : "bg-green-100 text-green-700"}`}>
          {row.original.type}
        </span>
      );
    },
  },
  {
    accessorKey: "reason",
    header: "Reason",
    cell: ({ row }) => <span className="font-medium">{row.original.reason}</span>,
  },
  {
    accessorKey: "message",
    header: "Message",
    cell: ({ row }) => <span className="block max-w-md truncate">{row.original.message}</span>,
  },
  {
    accessorKey: "source",
    header: "Source",
    cell: ({ row }) => <span>{row.original.source}</span>,
  },
  {
    accessorKey: "created_at",
    header: "Time",
    cell: ({ row }) => <span className="text-sm text-muted-foreground">{row.original.created_at ?? "Unknown"}</span>,
  },
];

type Tab = "status" | "yaml" | "logs" | "events";

type DetailState =
  | { status: "loading" }
  | { status: "ready"; data: DetailData }
  | { status: "error"; message: string };

type YamlState =
  | { status: "loading" }
  | { status: "ready"; data: YamlData }
  | { status: "error"; message: string };

type LogState =
  | { status: "loading" }
  | { status: "ready"; data: LogData }
  | { status: "error"; message: string };

type EventState =
  | { status: "loading" }
  | { status: "ready"; data: EventData }
  | { status: "error"; message: string };

type MetricsState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; available: boolean; nodeItem: NodeMetricItem | null; workloadItem: WorkloadMetricItem | null; storageItem: StorageMetricsItem | null }
  | { status: "error"; message: string };

const nodeMetricTypes = new Set(["nodes"]);
const workloadMetricTypes = new Set(["pods", "deployments", "daemon-sets", "stateful-sets"]);
const storageMetricTypes = new Set(["persistent-volumes", "persistent-volume-claims"]);

function StatusPanel({
  data,
  resourceType,
  name,
  namespace,
}: {
  data: DetailData;
  resourceType: string;
  name: string;
  namespace: string | null;
}) {
  const metricsEnabled = nodeMetricTypes.has(resourceType) || workloadMetricTypes.has(resourceType) || storageMetricTypes.has(resourceType);
  const [metricsState, setMetricsState] = useState<MetricsState>({ status: "idle" });
  const metricsAbortRef = useRef<AbortController | null>(null);

  const loadMetrics = useCallback(async () => {
    if (!metricsEnabled) return;
    const controller = new AbortController();
    metricsAbortRef.current?.abort();
    metricsAbortRef.current = controller;
    setMetricsState({ status: "loading" });
    try {
      if (nodeMetricTypes.has(resourceType)) {
        const response = await fetch("/api/cluster/metrics?type=nodes", { signal: controller.signal, cache: "no-store" });
        const body = (await response.json()) as { available: boolean; items: NodeMetricItem[]; message?: string };
        if (!response.ok) throw new Error(body.message ?? "Unable to load metrics");
        const item = body.items.find((i) => i.name === name) ?? null;
        setMetricsState({ status: "ready", available: body.available, nodeItem: item, workloadItem: null, storageItem: null });
      } else if (workloadMetricTypes.has(resourceType)) {
        const targetNs = namespace ?? "default";
        const response = await fetch(`/api/cluster/metrics?type=namespaces&namespace=${encodeURIComponent(targetNs)}`, { signal: controller.signal, cache: "no-store" });
        const body = (await response.json()) as { available: boolean; workloads: WorkloadMetricItem[]; message?: string };
        if (!response.ok) throw new Error(body.message ?? "Unable to load metrics");
        const item = body.workloads.find((w) => w.name === name) ?? null;
        setMetricsState({ status: "ready", available: body.available, nodeItem: null, workloadItem: item, storageItem: null });
      } else if (storageMetricTypes.has(resourceType)) {
        const response = await fetch("/api/cluster/metrics?type=storage", { signal: controller.signal, cache: "no-store" });
        const body = (await response.json()) as { available: boolean; items: StorageMetricsItem[]; message?: string };
        if (!response.ok) throw new Error(body.message ?? "Unable to load metrics");
        const item = body.items.find((i) => i.name === name) ?? null;
        setMetricsState({ status: "ready", available: body.available, nodeItem: null, workloadItem: null, storageItem: item });
      }
    } catch (error: unknown) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setMetricsState({ status: "error", message: error instanceof Error ? error.message : "Unable to load metrics" });
    }
  }, [resourceType, name, namespace, metricsEnabled]);

  usePolling(loadMetrics, metricsEnabled);

  useEffect(() => {
    return () => { metricsAbortRef.current?.abort(); };
  }, []);

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-border bg-card p-6">
        <h3 className="mb-4 text-lg font-semibold text-foreground">Resource Information</h3>
        <dl className="grid grid-cols-2 gap-4">
          <div>
            <dt className="text-sm text-muted-foreground">Name</dt>
            <dd className="font-medium text-foreground">{data.name}</dd>
          </div>
          <div>
            <dt className="text-sm text-muted-foreground">Kind</dt>
            <dd className="font-medium text-foreground">{data.kind}</dd>
          </div>
          <div>
            <dt className="text-sm text-muted-foreground">Namespace</dt>
            <dd className="font-medium text-foreground">{data.namespace ?? "Cluster-scoped"}</dd>
          </div>
          <div>
            <dt className="text-sm text-muted-foreground">Status</dt>
            <dd className="font-medium text-foreground">{data.status}</dd>
          </div>
          <div>
            <dt className="text-sm text-muted-foreground">Cluster</dt>
            <dd className="font-medium text-foreground">{data.cluster}</dd>
          </div>
          <div>
            <dt className="text-sm text-muted-foreground">Source</dt>
            <dd className="font-medium text-foreground">{data.source}</dd>
          </div>
        </dl>
      </div>

      {metricsState.status === "ready" && metricsState.available && (metricsState.nodeItem || metricsState.workloadItem || metricsState.storageItem) && (
        <div className="rounded-xl border border-border bg-card p-6">
          <h3 className="mb-4 text-lg font-semibold text-foreground">Live Metrics</h3>
          {metricsState.nodeItem && (() => {
            const m = metricsState.nodeItem;
            const cpuPct = utilizationPercent(m.cpu_usage_millicores, m.cpu_allocatable_millicores);
            const memPct = utilizationPercent(m.memory_usage_bytes, m.memory_allocatable_bytes);
            return (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <MetricBar
                  label="CPU"
                  value={`${formatMillicores(m.cpu_usage_millicores)} / ${m.cpu_allocatable_millicores !== null ? formatMillicores(m.cpu_allocatable_millicores) : "—"}${cpuPct !== null ? ` (${cpuPct}%)` : ""}`}
                  percent={cpuPct}
                  toneClass={cpuPct !== null && cpuPct >= 90 ? "text-red-600 font-medium" : cpuPct !== null && cpuPct >= 70 ? "text-amber-600 font-medium" : "text-foreground"}
                />
                <MetricBar
                  label="Memory"
                  value={`${formatBytes(m.memory_usage_bytes)} / ${m.memory_allocatable_bytes !== null ? formatBytes(m.memory_allocatable_bytes) : "—"}${memPct !== null ? ` (${memPct}%)` : ""}`}
                  percent={memPct}
                  toneClass={memPct !== null && memPct >= 90 ? "text-red-600 font-medium" : memPct !== null && memPct >= 70 ? "text-amber-600 font-medium" : "text-foreground"}
                />
              </div>
            );
          })()}
          {metricsState.workloadItem && (() => {
            const m = metricsState.workloadItem;
            return (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <MetricBar label="CPU" value={formatMillicores(m.cpu_usage_millicores)} percent={null} toneClass="text-foreground" />
                <MetricBar label="Memory" value={formatBytes(m.memory_usage_bytes)} percent={null} toneClass="text-foreground" />
              </div>
            );
          })()}
          {metricsState.storageItem && (() => {
            const m = metricsState.storageItem;
            return (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <MetricBar label="Capacity" value={m.capacity_bytes != null ? formatBytes(m.capacity_bytes) : "—"} percent={null} toneClass="text-foreground" />
                <MetricBar label="Utilization" value={m.utilization ?? "—"} percent={null} toneClass="text-foreground" />
              </div>
            );
          })()}
        </div>
      )}

      {Object.keys(data.metadata).length > 0 && (
        <div className="rounded-xl border border-border bg-card p-6">
          <h3 className="mb-4 text-lg font-semibold text-foreground">Labels & Annotations</h3>
          <dl className="space-y-2">
            {Object.entries(data.metadata).map(([key, value]) => (
              <div key={key} className="flex justify-between border-b border-border py-2">
                <dt className="text-sm text-muted-foreground">{key}</dt>
                <dd className="font-mono text-sm text-foreground">{value}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </div>
  );
}

function YamlPanel({ state }: { state: YamlState }) {
  if (state.status === "loading") {
    return <p className="rounded-lg bg-muted p-5 text-muted-foreground">Loading YAML...</p>;
  }
  if (state.status === "error") {
    return <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-5 text-red-700">{state.message}</p>;
  }
  return (
    <div className="space-y-4">
      {state.data.truncated && (
        <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-700">
          YAML output was truncated due to size limits.
        </p>
      )}
      <div className="rounded-xl border border-border bg-card">
        <pre className="overflow-x-auto p-6 font-mono text-sm text-foreground">{state.data.content}</pre>
      </div>
    </div>
  );
}

function LogsPanel({ state }: { state: LogState }) {
  if (state.status === "loading") {
    return <p className="rounded-lg bg-muted p-5 text-muted-foreground">Loading logs...</p>;
  }
  if (state.status === "error") {
    return <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-5 text-red-700">{state.message}</p>;
  }
  if (state.data.lines.length === 0) {
    return <p className="rounded-lg bg-muted p-5 text-muted-foreground">No logs available for this resource.</p>;
  }
  return (
    <div className="space-y-4">
      {state.data.container && (
        <p className="text-sm text-muted-foreground">Container: {state.data.container}</p>
      )}
      {state.data.truncated && (
        <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-700">
          Logs were truncated due to size limits.
        </p>
      )}
      <div className="rounded-xl border border-border bg-card">
        <pre className="overflow-x-auto p-6 font-mono text-sm text-foreground whitespace-pre-wrap">
          {state.data.lines.join("\n")}
        </pre>
      </div>
    </div>
  );
}

function EventsPanel({ state }: { state: EventState }) {
  if (state.status === "loading") {
    return <p className="rounded-lg bg-muted p-5 text-muted-foreground">Loading events...</p>;
  }
  if (state.status === "error") {
    return <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-5 text-red-700">{state.message}</p>;
  }
  if (state.data.items.length === 0) {
    return <p className="rounded-lg bg-muted p-5 text-muted-foreground">No events found for this resource.</p>;
  }
  return (
    <div className="space-y-4">
      {state.data.truncated && (
        <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-700">
          Events were truncated. Showing most recent entries.
        </p>
      )}
      <DataTable
        columns={eventColumns}
        data={state.data.items}
        placeholder="No events found for this resource."
        searchPlaceholder="Filter events…"
      />
    </div>
  );
}

export default function ResourceDetailView({
  resourceType,
  name,
  namespace,
  cluster: initialCluster,
}: {
  resourceType: string;
  name: string;
  namespace: string | null;
  cluster?: string;
}) {
  const activeCluster = useClusterStatus(initialCluster);
  const [activeTab, setActiveTab] = useState<Tab>("status");
  const [detailState, setDetailState] = useState<DetailState>({ status: "loading" });
  const [yamlState, setYamlState] = useState<YamlState>({ status: "loading" });
  const [logState, setLogState] = useState<LogState>({ status: "loading" });
  const [eventState, setEventState] = useState<EventState>({ status: "loading" });
  const router = useRouter();

  const requestKey = `${resourceType}\0${name}\0${namespace ?? ""}`;
  const [prevRequestKey, setPrevRequestKey] = useState(requestKey);
  if (prevRequestKey !== requestKey) {
    setPrevRequestKey(requestKey);
    setDetailState({ status: "loading" });
    setYamlState({ status: "loading" });
    setLogState({ status: "loading" });
    setEventState({ status: "loading" });
  }
  const [prevActiveTab, setPrevActiveTab] = useState(activeTab);
  if (prevActiveTab !== activeTab) {
    setPrevActiveTab(activeTab);
    if (activeTab === "yaml") setYamlState({ status: "loading" });
    if (activeTab === "logs") setLogState({ status: "loading" });
    if (activeTab === "events") setEventState({ status: "loading" });
  }

  const handleNav = (resource: string, ns: string) => {
    const params = new URLSearchParams({ resource, namespace: ns });
    router.push(`/dashboard?${params.toString()}`);
  };

  useEffect(() => {
    if (!name) return;

    const controller = new AbortController();

    const params = new URLSearchParams({ tab: "detail" });
    if (namespace) params.set("namespace", namespace);

    fetch(`/api/cluster/details/${resourceType}/${encodeURIComponent(name)}?${params}`, {
      signal: controller.signal,
      cache: "no-store",
    })
      .then(async (response) => {
        const body = (await response.json()) as DetailData & { message?: string };
        if (!response.ok) throw new Error(body.message ?? "Unable to load resource details");
        setDetailState({ status: "ready", data: body });
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setDetailState({ status: "error", message: error instanceof Error ? error.message : "Unable to load resource details" });
      });

    return () => controller.abort();
  }, [resourceType, name, namespace]);

  useEffect(() => {
    if (!name || activeTab !== "yaml") return;

    const controller = new AbortController();

    const params = new URLSearchParams({ tab: "yaml" });
    if (namespace) params.set("namespace", namespace);

    fetch(`/api/cluster/details/${resourceType}/${encodeURIComponent(name)}?${params}`, {
      signal: controller.signal,
      cache: "no-store",
    })
      .then(async (response) => {
        const body = (await response.json()) as YamlData & { message?: string };
        if (!response.ok) throw new Error(body.message ?? "Unable to load YAML");
        setYamlState({ status: "ready", data: body });
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setYamlState({ status: "error", message: error instanceof Error ? error.message : "Unable to load YAML" });
      });

    return () => controller.abort();
  }, [activeTab, resourceType, name, namespace]);

  useEffect(() => {
    if (!name || activeTab !== "logs") return;

    const controller = new AbortController();

    const params = new URLSearchParams({ tab: "logs" });
    if (namespace) params.set("namespace", namespace);

    fetch(`/api/cluster/details/${resourceType}/${encodeURIComponent(name)}?${params}`, {
      signal: controller.signal,
      cache: "no-store",
    })
      .then(async (response) => {
        const body = (await response.json()) as LogData & { message?: string };
        if (!response.ok) throw new Error(body.message ?? "Unable to load logs");
        setLogState({ status: "ready", data: body });
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setLogState({ status: "error", message: error instanceof Error ? error.message : "Unable to load logs" });
      });

    return () => controller.abort();
  }, [activeTab, resourceType, name, namespace]);

  useEffect(() => {
    if (!name || activeTab !== "events") return;

    const controller = new AbortController();

    const params = new URLSearchParams({ tab: "events" });
    if (namespace) params.set("namespace", namespace);

    fetch(`/api/cluster/details/${resourceType}/${encodeURIComponent(name)}?${params}`, {
      signal: controller.signal,
      cache: "no-store",
    })
      .then(async (response) => {
        const body = (await response.json()) as EventData & { message?: string };
        if (!response.ok) throw new Error(body.message ?? "Unable to load events");
        setEventState({ status: "ready", data: body });
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setEventState({ status: "error", message: error instanceof Error ? error.message : "Unable to load events" });
      });

    return () => controller.abort();
  }, [activeTab, resourceType, name, namespace]);

  const tabs: { id: Tab; label: string }[] = [
    { id: "status", label: "Status" },
    { id: "yaml", label: "YAML" },
    { id: "logs", label: "Logs" },
    { id: "events", label: "Events" },
  ];

  if (!name) {
    return (
      <DashboardShell
        activeResource={resourceType}
        activeNamespace={namespace ?? ""}
        activeCluster={activeCluster}
        onNavigate={handleNav}
      >
        <div className="space-y-6">
          <Link href="/dashboard?resource=pods" className="text-sm text-cyan-600 hover:underline">
            ← Back to resources
          </Link>
          <p className="rounded-lg border border-red-200 bg-red-50 p-5 text-red-700">
            No resource name provided. Please select a resource from the list.
          </p>
        </div>
      </DashboardShell>
    );
  }

  return (
    <DashboardShell
      activeResource={resourceType}
      activeNamespace={namespace ?? ""}
      activeCluster={activeCluster}
      onNavigate={handleNav}
    >
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link
          href={`/dashboard?resource=${resourceType}${namespace ? `&namespace=${namespace}` : ""}`}
          className="text-sm text-cyan-600 hover:underline"
        >
          ← Back to {resourceType}
        </Link>
        {detailState.status === "ready" && (
          <span className="rounded-full bg-cyan-100 px-3 py-1 text-sm font-medium text-cyan-800">
            {detailState.data.kind}
          </span>
        )}
      </div>

      <div>
        <p className="text-sm font-medium uppercase tracking-[0.2em] text-muted-foreground">Resource details</p>
        <h2 className="text-3xl font-semibold text-foreground">
          {name}
          {namespace && <span className="ml-2 text-lg text-muted-foreground">({namespace})</span>}
        </h2>
      </div>

      <div className="flex gap-1 rounded-lg border border-border bg-muted p-1">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 cursor-pointer rounded-md px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === tab.id
                ? "bg-card text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="mt-6">
        {activeTab === "status" && (
          detailState.status === "loading" ? (
            <p className="rounded-lg bg-muted p-5 text-muted-foreground">Loading status...</p>
          ) : detailState.status === "error" ? (
            <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-5 text-red-700">{detailState.message}</p>
          ) : (
            <StatusPanel data={detailState.data} resourceType={resourceType} name={name} namespace={namespace} />
          )
        )}
        {activeTab === "yaml" && <YamlPanel state={yamlState} />}
        {activeTab === "logs" && <LogsPanel state={logState} />}
        {activeTab === "events" && <EventsPanel state={eventState} />}
      </div>
    </div>
    </DashboardShell>
  );
}
