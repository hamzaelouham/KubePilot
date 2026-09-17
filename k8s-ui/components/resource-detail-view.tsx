"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowDown, FileText, RefreshCw, Terminal } from "lucide-react";
import { DashboardShell } from "@/components/dashboard-shell";
import { useClusterSelection } from "@/lib/use-cluster-selection";
import { useCluster } from "@/lib/cluster-context";
import { withCluster } from "@/lib/cluster-query";
import { MetricBar } from "@/components/metric-bar";
import { usePolling } from "@/lib/use-polling";
import { DataTable, type DataTableColumn } from "@/components/data-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
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
  const cluster = useCluster();

  const loadMetrics = useCallback(async () => {
    if (!metricsEnabled) return;
    const controller = new AbortController();
    metricsAbortRef.current?.abort();
    metricsAbortRef.current = controller;
    setMetricsState({ status: "loading" });
    try {
      if (nodeMetricTypes.has(resourceType)) {
        const response = await fetch(withCluster("/api/cluster/metrics?type=nodes", cluster), { signal: controller.signal, cache: "no-store" });
        const body = (await response.json()) as { available: boolean; items: NodeMetricItem[]; message?: string };
        if (!response.ok) throw new Error(body.message ?? "Unable to load metrics");
        const item = body.items.find((i) => i.name === name) ?? null;
        setMetricsState({ status: "ready", available: body.available, nodeItem: item, workloadItem: null, storageItem: null });
      } else if (workloadMetricTypes.has(resourceType)) {
        const targetNs = namespace ?? "default";
        const response = await fetch(withCluster(`/api/cluster/metrics?type=namespaces&namespace=${encodeURIComponent(targetNs)}`, cluster), { signal: controller.signal, cache: "no-store" });
        const body = (await response.json()) as { available: boolean; workloads: WorkloadMetricItem[]; message?: string };
        if (!response.ok) throw new Error(body.message ?? "Unable to load metrics");
        const item = body.workloads.find((w) => w.name === name) ?? null;
        setMetricsState({ status: "ready", available: body.available, nodeItem: null, workloadItem: item, storageItem: null });
      } else if (storageMetricTypes.has(resourceType)) {
        const response = await fetch(withCluster("/api/cluster/metrics?type=storage", cluster), { signal: controller.signal, cache: "no-store" });
        const body = (await response.json()) as { available: boolean; items: StorageMetricsItem[]; message?: string };
        if (!response.ok) throw new Error(body.message ?? "Unable to load metrics");
        const item = body.items.find((i) => i.name === name) ?? null;
        setMetricsState({ status: "ready", available: body.available, nodeItem: null, workloadItem: null, storageItem: item });
      }
    } catch (error: unknown) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setMetricsState({ status: "error", message: error instanceof Error ? error.message : "Unable to load metrics" });
    }
  }, [cluster, resourceType, name, namespace, metricsEnabled]);

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
                  toneClass={cpuPct !== null && cpuPct >= 90 ? "text-destructive font-medium" : cpuPct !== null && cpuPct >= 70 ? "text-amber-600 font-medium" : "text-foreground"}
                />
                <MetricBar
                  label="Memory"
                  value={`${formatBytes(m.memory_usage_bytes)} / ${m.memory_allocatable_bytes !== null ? formatBytes(m.memory_allocatable_bytes) : "—"}${memPct !== null ? ` (${memPct}%)` : ""}`}
                  percent={memPct}
                  toneClass={memPct !== null && memPct >= 90 ? "text-destructive font-medium" : memPct !== null && memPct >= 70 ? "text-amber-600 font-medium" : "text-foreground"}
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
    return <p role="alert" className="rounded-lg border border-destructive/40 bg-destructive/10 p-5 text-destructive">{state.message}</p>;
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

function LogViewer({ data, onRefresh }: { data: LogData; onRefresh: () => void }) {
  const logRef = useRef<HTMLPreElement | null>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const lastLine = data.lines.at(-1) ?? "";

  useEffect(() => {
    const element = logRef.current;
    if (!element) return;
    const frame = window.requestAnimationFrame(() => {
      element.scrollTop = element.scrollHeight;
    });
    return () => window.cancelAnimationFrame(frame);
  }, [data.lines.length, lastLine]);

  const scrollToBottom = () => {
    const element = logRef.current;
    if (!element) return;
    element.scrollTo({ top: element.scrollHeight, behavior: "smooth" });
    setIsAtBottom(true);
  };

  return (
    <Card className="overflow-hidden">
      <CardHeader className="border-b bg-muted/20">
        <div className="flex items-start gap-3">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Terminal className="size-5" aria-hidden="true" />
          </div>
          <div>
            <CardTitle>Pod Logs</CardTitle>
            <CardDescription className="mt-1">
              Latest bounded snapshot{data.container ? ` from ${data.container}` : " from the selected pod"}.
            </CardDescription>
          </div>
        </div>
        <CardAction>
          <div className="flex flex-wrap items-center justify-end gap-2">
            <Badge variant="outline" className="gap-1.5 font-normal">
              <FileText className="size-3.5" aria-hidden="true" />
              {data.lines.length} {data.lines.length === 1 ? "line" : "lines"}
            </Badge>
            <Button type="button" variant="outline" size="sm" onClick={onRefresh}>
              <RefreshCw data-icon="inline-start" />
              Refresh
            </Button>
          </div>
        </CardAction>
      </CardHeader>
      <CardContent className="space-y-4 p-4 sm:p-6">
        {data.truncated ? (
          <div className="flex items-start gap-3 rounded-lg border border-amber-300/60 bg-amber-50/70 p-3 text-sm text-amber-800 dark:border-amber-400/30 dark:bg-amber-950/20 dark:text-amber-200">
            <span className="mt-0.5 size-2 shrink-0 rounded-full bg-amber-500" aria-hidden="true" />
            <span>Only the most recent logs are shown because this snapshot reached the display limit.</span>
          </div>
        ) : null}
        <div className="relative overflow-hidden rounded-xl border border-border bg-zinc-950 shadow-inner dark:bg-black">
          <pre
            ref={logRef}
            role="log"
            aria-label="Pod log output"
            tabIndex={0}
            onScroll={(event) => {
              const element = event.currentTarget;
              setIsAtBottom(element.scrollHeight - element.scrollTop - element.clientHeight <= 24);
            }}
            className="h-[28rem] max-h-[60vh] min-h-64 overflow-auto p-4 font-mono text-xs leading-6 text-zinc-200 outline-none focus-visible:ring-2 focus-visible:ring-primary/60 sm:p-5 sm:text-sm"
          >
            <code>
              {data.lines.map((line, index) => (
                <span className="block whitespace-pre" key={`${index}-${line}`}>
                  <span className="mr-4 inline-block w-10 select-none text-right text-zinc-500" aria-hidden="true">{index + 1}</span>
                  {line}
                </span>
              ))}
            </code>
          </pre>
          {!isAtBottom ? (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={scrollToBottom}
              className="absolute bottom-4 right-4 shadow-lg"
            >
              <ArrowDown data-icon="inline-start" />
              Scroll to bottom
            </Button>
          ) : null}
        </div>
      </CardContent>
      <CardFooter className="flex flex-wrap justify-between gap-3 text-xs text-muted-foreground">
        <span>Showing the newest {data.lines.length} lines</span>
        <span>Scroll inside the viewer to inspect older entries</span>
      </CardFooter>
    </Card>
  );
}

function LogsPanel({ state, onRefresh }: { state: LogState; onRefresh: () => void }) {
  if (state.status === "loading") {
    return (
      <Card aria-busy="true" aria-label="Loading pod logs">
        <CardHeader className="border-b bg-muted/20">
          <CardTitle>Pod Logs</CardTitle>
          <CardDescription>Loading the latest bounded snapshot…</CardDescription>
        </CardHeader>
        <CardContent className="p-4 sm:p-6">
          <div className="h-[28rem] max-h-[60vh] min-h-64 animate-pulse rounded-xl bg-muted" />
        </CardContent>
      </Card>
    );
  }
  if (state.status === "error") {
    return (
      <Card role="alert" className="border-destructive/40">
        <CardHeader>
          <CardTitle>Unable to load Pod Logs</CardTitle>
          <CardDescription className="text-destructive">{state.message}</CardDescription>
        </CardHeader>
        <CardFooter>
          <Button type="button" variant="outline" onClick={onRefresh}>
            <RefreshCw data-icon="inline-start" />
            Try again
          </Button>
        </CardFooter>
      </Card>
    );
  }
  if (state.data.lines.length === 0) {
    return (
      <Card>
        <CardHeader className="border-b bg-muted/20">
          <CardTitle>Pod Logs</CardTitle>
          <CardDescription>No log lines were returned for the selected pod.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col items-center justify-center gap-3 p-10 text-center">
          <div className="flex size-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
            <FileText className="size-5" aria-hidden="true" />
          </div>
          <p className="text-sm text-muted-foreground">The container may not have written output yet.</p>
          <Button type="button" variant="outline" onClick={onRefresh}>
            <RefreshCw data-icon="inline-start" />
            Refresh logs
          </Button>
        </CardContent>
      </Card>
    );
  }
  return <LogViewer key={`${state.data.lines.length}-${state.data.lines.at(-1) ?? ""}`} data={state.data} onRefresh={onRefresh} />;
}

function EventsPanel({ state }: { state: EventState }) {
  if (state.status === "loading") {
    return <p className="rounded-lg bg-muted p-5 text-muted-foreground">Loading events...</p>;
  }
  if (state.status === "error") {
    return <p role="alert" className="rounded-lg border border-destructive/40 bg-destructive/10 p-5 text-destructive">{state.message}</p>;
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
  const { cluster: activeCluster, clusters, selectCluster } = useClusterSelection(initialCluster);
  const [activeTab, setActiveTab] = useState<Tab>("status");
  const [detailState, setDetailState] = useState<DetailState>({ status: "loading" });
  const [yamlState, setYamlState] = useState<YamlState>({ status: "loading" });
  const [logState, setLogState] = useState<LogState>({ status: "loading" });
  const [eventState, setEventState] = useState<EventState>({ status: "loading" });
  const [logRefreshKey, setLogRefreshKey] = useState(0);
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
    if (activeCluster) params.set("cluster", activeCluster);
    router.push(`/dashboard?${params.toString()}`);
  };

  useEffect(() => {
    if (!name) return;

    const controller = new AbortController();

    const params = new URLSearchParams({ tab: "detail" });
    if (namespace) params.set("namespace", namespace);

    fetch(withCluster(`/api/cluster/details/${resourceType}/${encodeURIComponent(name)}?${params}`, activeCluster), {
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
  }, [resourceType, name, namespace, activeCluster]);

  useEffect(() => {
    if (!name || activeTab !== "yaml") return;

    const controller = new AbortController();

    const params = new URLSearchParams({ tab: "yaml" });
    if (namespace) params.set("namespace", namespace);

    fetch(withCluster(`/api/cluster/details/${resourceType}/${encodeURIComponent(name)}?${params}`, activeCluster), {
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
  }, [activeTab, resourceType, name, namespace, activeCluster]);

  useEffect(() => {
    if (!name || activeTab !== "logs") return;

    const controller = new AbortController();

    const params = new URLSearchParams({ tab: "logs" });
    if (namespace) params.set("namespace", namespace);

    fetch(withCluster(`/api/cluster/details/${resourceType}/${encodeURIComponent(name)}?${params}`, activeCluster), {
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
  }, [activeTab, resourceType, name, namespace, activeCluster, logRefreshKey]);

  useEffect(() => {
    if (!name || activeTab !== "events") return;

    const controller = new AbortController();

    const params = new URLSearchParams({ tab: "events" });
    if (namespace) params.set("namespace", namespace);

    fetch(withCluster(`/api/cluster/details/${resourceType}/${encodeURIComponent(name)}?${params}`, activeCluster), {
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
  }, [activeTab, resourceType, name, namespace, activeCluster]);

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
        clusters={clusters}
        onSelectCluster={selectCluster}
        onNavigate={handleNav}
      >
        <div className="space-y-6">
          <Link href="/dashboard?resource=pods" className="text-sm text-cyan-600 hover:underline">
            ← Back to resources
          </Link>
          <p className="rounded-lg border border-destructive/40 bg-destructive/10 p-5 text-destructive">
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
      clusters={clusters}
      onSelectCluster={selectCluster}
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
        <Link className="mt-3 inline-flex text-sm font-medium text-primary hover:underline" href={`/assistant?${new URLSearchParams({ cluster: activeCluster, resource: resourceType, name, ...(namespace ? { namespace } : {}) })}`}>Investigate with AI Assistant</Link>
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
            <p role="alert" className="rounded-lg border border-destructive/40 bg-destructive/10 p-5 text-destructive">{detailState.message}</p>
          ) : (
            <StatusPanel data={detailState.data} resourceType={resourceType} name={name} namespace={namespace} />
          )
        )}
        {activeTab === "yaml" && <YamlPanel state={yamlState} />}
        {activeTab === "logs" && <LogsPanel state={logState} onRefresh={() => { setLogState({ status: "loading" }); setLogRefreshKey((current) => current + 1); }} />}
        {activeTab === "events" && <EventsPanel state={eventState} />}
      </div>
    </div>
    </DashboardShell>
  );
}
