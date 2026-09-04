"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { healthTone, type Health } from "@/lib/status-tone";
import { formatLastUpdated, usePolling } from "@/lib/use-polling";
import { formatMillicores, formatBytes, type NamespaceMetricSummary, type MetricsSummaryResponse } from "@/lib/metrics";

type Resource = { cluster: string; namespace: string | null; kind: string; name: string; status: string; health: Health };
type ResourceResponse = { items: Resource[]; message?: string };

type OverviewState =
  | { status: "loading" }
  | { status: "ready"; deployments: Resource[]; pods: Resource[]; namespaceSummary: NamespaceMetricSummary[]; metricsAvailable: boolean }
  | { status: "error"; message: string };

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
      <div className="absolute inset-[18px] rounded-full bg-[#f5f7f9]" />
      <div className="absolute inset-0 flex items-center justify-center text-sm font-medium text-slate-700">
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
    setState({ status: "loading" });
    load();
    return () => abortRef.current?.abort();
  }, [load]);

  const { refresh, lastUpdated } = usePolling(load);

  if (state.status === "loading") return <p className="rounded-lg bg-slate-100 p-5 text-slate-500">Loading cluster overview...</p>;
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
          <p className="text-sm font-medium uppercase tracking-[0.2em] text-slate-400">Live cluster data</p>
          <h2 className="text-3xl font-semibold text-slate-700">Overview</h2>
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

      <div className="rounded-xl border border-slate-200 bg-[#f2f5f7] p-5">
        <h3 className="mb-6 text-2xl font-semibold text-slate-700">Workload Status</h3>
        <div className="grid gap-8 md:grid-cols-2">
          {pieData.map((pie) => (
            <div key={pie.label} className="text-center">
              <div className="flex justify-center">
                <DonutChart values={pie.values} colors={pie.color} />
              </div>
              <p className="mt-3 text-lg text-slate-700">{pie.label}</p>
              <p className="text-sm text-slate-500">{pie.values[0]} healthy / {pie.values[0] + pie.values[1]} total</p>
            </div>
          ))}
        </div>
      </div>

      {namespaceSummary.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white">
          <div className="border-b border-slate-200 px-4 py-3">
            <h3 className="text-2xl font-semibold text-slate-700">Namespace Utilization</h3>
          </div>
          <div className="overflow-hidden">
            <table className="min-w-full text-left text-base">
              <thead className="bg-slate-100 text-slate-600">
                <tr>
                  <th className="px-4 py-3 font-medium">Namespace</th>
                  <th className="px-4 py-3 font-medium">CPU</th>
                  <th className="px-4 py-3 font-medium">Memory</th>
                  <th className="px-4 py-3 font-medium">Pods</th>
                </tr>
              </thead>
              <tbody>
                {namespaceSummary.map((ns) => (
                  <tr key={ns.namespace} className="border-t border-slate-200 text-slate-700">
                    <td className="px-4 py-4 font-medium">{ns.namespace}</td>
                    <td className="px-4 py-4 text-sm">{formatMillicores(ns.cpu_usage_millicores)}</td>
                    <td className="px-4 py-4 text-sm">{formatBytes(ns.memory_usage_bytes)}</td>
                    <td className="px-4 py-4">{ns.pod_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!metricsAvailable && namespaceSummary.length === 0 && (
        <p className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-700">
          Namespace metrics are unavailable. Metrics server may not be installed in this cluster.
        </p>
      )}

      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-4 py-3">
          <h3 className="text-2xl font-semibold text-slate-700">Deployments</h3>
        </div>
        <div className="overflow-hidden">
          <table className="min-w-full text-left text-base">
            <thead className="bg-slate-100 text-slate-600">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Namespace</th>
                <th className="px-4 py-3 font-medium">Ready</th>
                <th className="px-4 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {deployments.map((item) => (
                <tr key={`${item.namespace}-${item.name}`} className="border-t border-slate-200 text-slate-700">
                  <td className="px-4 py-4 font-medium">{item.name}</td>
                  <td className="px-4 py-4">
                    <span className="inline-flex rounded-full bg-slate-200 px-2 py-1 text-sm text-slate-600">{item.namespace ?? "All namespaces"}</span>
                  </td>
                  <td className="px-4 py-4">{item.status}</td>
                  <td className="px-4 py-4">
                    <span className={`inline-flex rounded-full px-2 py-1 text-sm font-medium ${healthTone(item.health).pill}`}>
                      {healthTone(item.health).short}
                    </span>
                  </td>
                </tr>
              ))}
              {deployments.length === 0 ? (
                <tr><td colSpan={4} className="px-4 py-4 text-slate-500">No deployments found.</td></tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
