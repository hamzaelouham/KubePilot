"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { formatLastUpdated, usePolling } from "@/lib/use-polling";

type Namespace = { name: string; status: string };
type NamespaceResponse = { items: Namespace[] };
type NamespaceState =
  | { status: "loading" }
  | { status: "ready"; items: Namespace[] }
  | { status: "error"; message: string };

export function NamespacesView() {
  const [state, setState] = useState<NamespaceState>({ status: "loading" });
  const abortRef = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
    const controller = new AbortController();
    abortRef.current?.abort();
    abortRef.current = controller;
    try {
      const response = await fetch("/api/cluster/namespaces", { signal: controller.signal, cache: "no-store" });
      const body = (await response.json()) as NamespaceResponse & { message?: string };
      if (!response.ok) throw new Error(body.message ?? "Unable to load namespaces");
      setState({ status: "ready", items: body.items });
    } catch (error: unknown) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setState({ status: "error", message: error instanceof Error ? error.message : "Unable to load namespaces" });
    }
  }, []);

  useEffect(() => {
    abortRef.current?.abort();
    setState({ status: "loading" });
    load();
    return () => abortRef.current?.abort();
  }, [load]);

  const { refresh, lastUpdated } = usePolling(load);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="text-sm font-medium uppercase tracking-[0.2em] text-slate-400">Live cluster data</p>
          <h2 className="text-3xl font-semibold text-slate-700">Namespaces</h2>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={refresh}
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-100"
          >
            Refresh
          </button>
          <span className="text-sm text-slate-500">Updated {formatLastUpdated(lastUpdated)}</span>
        </div>
      </div>

      {state.status === "loading" ? <p className="rounded-lg bg-slate-100 p-5 text-slate-500">Loading namespaces...</p> : null}
      {state.status === "error" ? <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-5 text-red-700">{state.message}</p> : null}
      {state.status === "ready" && state.items.length === 0 ? <p className="rounded-lg bg-slate-100 p-5 text-slate-500">No namespaces found.</p> : null}
      {state.status === "ready" && state.items.length > 0 ? (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="min-w-full text-left text-base">
            <thead className="bg-slate-100 text-slate-600">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {state.items.map((item) => (
                <tr key={item.name} className="border-t border-slate-200 text-slate-700">
                  <td className="px-4 py-3 font-medium">{item.name}</td>
                  <td className="px-4 py-3">{item.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
