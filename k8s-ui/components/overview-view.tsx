"use client";

import { useEffect, useState } from "react";

type Resource = { cluster: string; namespace: string | null; kind: string; name: string; status: string };
type ResourceResponse = { items: Resource[]; message?: string };

type OverviewState =
  | { status: "loading" }
  | { status: "ready"; deployments: Resource[]; pods: Resource[] }
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

  useEffect(() => {
    const controller = new AbortController();
    setState({ status: "loading" });

    Promise.all([
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
    ])
      .then(([deployments, pods]) => setState({ status: "ready", deployments, pods }))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setState({ status: "error", message: error instanceof Error ? error.message : "Unable to load cluster data" });
      });

    return () => controller.abort();
  }, []);

  if (state.status === "loading") return <p className="rounded-lg bg-slate-100 p-5 text-slate-500">Loading cluster overview...</p>;
  if (state.status === "error") return <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-5 text-red-700">{state.message}</p>;

  const { deployments, pods } = state;

  const deploymentsReady = deployments.filter((d) => d.status === "1").length;
  const deploymentsNotReady = deployments.length - deploymentsReady;
  const podsRunning = pods.filter((p) => p.status === "Running").length;
  const podsNotRunning = pods.length - podsRunning;

  const pieData = [
    { label: "Deployments", values: [deploymentsReady, deploymentsNotReady], color: ["#22c55e", "#e74c3c"] },
    { label: "Pods", values: [podsRunning, podsNotRunning], color: ["#22c55e", "#e74c3c"] },
  ];

  return (
    <div className="space-y-8">
      <div>
        <p className="text-sm font-medium uppercase tracking-[0.2em] text-slate-400">Live cluster data</p>
        <h2 className="text-3xl font-semibold text-slate-700">Workloads</h2>
      </div>

      <div className="rounded-xl border border-slate-200 bg-[#f2f5f7] p-5">
        <h3 className="mb-6 text-2xl font-semibold text-slate-700">Workload Status</h3>
        <div className="grid gap-8 md:grid-cols-2">
          {pieData.map((pie) => (
            <div key={pie.label} className="text-center">
              <div className="flex justify-center">
                <DonutChart values={pie.values} colors={pie.color} />
              </div>
              <p className="mt-3 text-lg text-slate-700">{pie.label}</p>
              <p className="text-sm text-slate-500">{pie.values[0]} ready / {pie.values[0] + pie.values[1]} total</p>
            </div>
          ))}
        </div>
      </div>

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
                    <span className={`inline-flex h-5 w-5 items-center justify-center rounded-full text-xs ${item.status === "1" ? "bg-green-500 text-white" : "bg-red-500 text-white"}`}>
                      {item.status === "1" ? "\u2713" : "!"}
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
