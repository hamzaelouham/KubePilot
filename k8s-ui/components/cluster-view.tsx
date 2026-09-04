"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { healthTone, type Health } from "@/lib/status-tone";
import { formatLastUpdated, usePolling } from "@/lib/use-polling";
import { MetricBar } from "@/components/metric-bar";
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

  if (state.status === "loading") return <p className="rounded-lg bg-slate-100 p-5 text-slate-500">Loading cluster data...</p>;
  if (state.status === "error") return <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-5 text-red-700">{state.message}</p>;

  const { namespaces, nodes, storageClasses, persistentVolumes, nodeMetrics, storageMetrics, metricsAvailable } = state;
  const nodeMetricsByName = new Map(nodeMetrics.map((n) => [n.name, n]));
  const storageMetricsByName = new Map(storageMetrics.map((s) => [s.name, s]));

  const totalCpu = nodeMetrics.reduce((sum, n) => sum + (n.cpu_usage_millicores ?? 0), 0);
  const totalMemory = nodeMetrics.reduce((sum, n) => sum + (n.memory_usage_bytes ?? 0), 0);
  const unhealthyNodes = nodes.filter((n) => n.health === "warning" || n.health === "error").length;

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="text-sm font-medium uppercase tracking-[0.2em] text-slate-400">Live cluster data</p>
          <h2 className="text-3xl font-semibold text-slate-700">Cluster</h2>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={refresh}
            className="cursor-pointer rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-100"
          >
            Refresh
          </button>
          <span className="text-sm text-slate-500">Updated {formatLastUpdated(lastUpdated)}</span>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <p className="text-sm text-slate-500">Namespaces</p>
          <p className="mt-1 text-3xl font-semibold text-slate-700">{namespaces.length}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <p className="text-sm text-slate-500">Nodes</p>
          <p className="mt-1 text-3xl font-semibold text-slate-700">{nodes.length}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <p className="text-sm text-slate-500">Aggregate CPU</p>
          <p className="mt-1 text-3xl font-semibold text-slate-700">{metricsAvailable ? formatMillicores(totalCpu) : "—"}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <p className="text-sm text-slate-500">Aggregate Memory</p>
          <p className="mt-1 text-3xl font-semibold text-slate-700">{metricsAvailable ? formatBytes(totalMemory) : "—"}</p>
        </div>
      </div>

      {unhealthyNodes > 0 && (
        <div role="alert" className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-amber-800">
          <p className="font-medium">{unhealthyNodes} node{unhealthyNodes === 1 ? "" : "s"} need attention</p>
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-4 py-3">
          <h3 className="text-2xl font-semibold text-slate-700">Node Utilization</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-base">
            <thead className="bg-slate-100 text-slate-600">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">CPU</th>
                <th className="px-4 py-3 font-medium">Memory</th>
                <th className="px-4 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {nodes.map((node) => {
                const metric = nodeMetricsByName.get(node.name);
                const cpuPct = metric ? utilizationPercent(metric.cpu_usage_millicores, metric.cpu_allocatable_millicores) : null;
                const memPct = metric ? utilizationPercent(metric.memory_usage_bytes, metric.memory_allocatable_bytes) : null;
                return (
                  <tr key={node.name} className="border-t border-slate-200 text-slate-700 hover:bg-slate-50">
                    <td className="px-4 py-3 font-medium">
                      <Link href={`/dashboard/detail?resourceType=nodes&name=${encodeURIComponent(node.name)}`} className="text-cyan-600 hover:underline">
                        {node.name}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <MetricBar
                        label="CPU"
                        value={metric ? `${formatMillicores(metric.cpu_usage_millicores)}${cpuPct !== null ? ` (${cpuPct}%)` : ""}` : "—"}
                        percent={cpuPct}
                        toneClass="text-slate-700"
                      />
                    </td>
                    <td className="px-4 py-3">
                      <MetricBar
                        label="Memory"
                        value={metric ? `${formatBytes(metric.memory_usage_bytes)}${memPct !== null ? ` (${memPct}%)` : ""}` : "—"}
                        percent={memPct}
                        toneClass="text-slate-700"
                      />
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex rounded-full px-2 py-1 text-sm font-medium ${healthTone(node.health).pill}`}>
                        {healthTone(node.health).short}
                      </span>
                    </td>
                  </tr>
                );
              })}
              {nodes.length === 0 ? <tr><td colSpan={4} className="px-4 py-4 text-slate-500">No nodes found.</td></tr> : null}
            </tbody>
          </table>
        </div>
        {!metricsAvailable && (
          <p className="border-t border-slate-200 px-4 py-3 text-sm text-amber-700">
            Node metrics are unavailable. Metrics server may not be installed in this cluster.
          </p>
        )}
      </div>

      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-4 py-3">
          <h3 className="text-2xl font-semibold text-slate-700">Persistent Volumes</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-base">
            <thead className="bg-slate-100 text-slate-600">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Capacity</th>
                <th className="px-4 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {persistentVolumes.map((pv) => {
                const storageMetric = storageMetricsByName.get(pv.name);
                return (
                  <tr key={pv.name} className="border-t border-slate-200 text-slate-700">
                    <td className="px-4 py-3 font-medium">{pv.name}</td>
                    <td className="px-4 py-3 text-sm">{storageMetric?.capacity_bytes != null ? formatBytes(storageMetric.capacity_bytes) : "—"}</td>
                    <td className="px-4 py-3 text-sm">{pv.status}</td>
                  </tr>
                );
              })}
              {persistentVolumes.length === 0 ? <tr><td colSpan={3} className="px-4 py-4 text-slate-500">No persistent volumes found.</td></tr> : null}
            </tbody>
          </table>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-4 py-3">
          <h3 className="text-2xl font-semibold text-slate-700">Storage Classes</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-base">
            <thead className="bg-slate-100 text-slate-600">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
              </tr>
            </thead>
            <tbody>
              {storageClasses.map((sc) => (
                <tr key={sc.name} className="border-t border-slate-200 text-slate-700">
                  <td className="px-4 py-3 font-medium">{sc.name}</td>
                </tr>
              ))}
              {storageClasses.length === 0 ? <tr><td className="px-4 py-4 text-slate-500">No storage classes found.</td></tr> : null}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
