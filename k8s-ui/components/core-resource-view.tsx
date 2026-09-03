"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

type Resource = {
  cluster: string;
  namespace: string | null;
  kind: string;
  name: string;
  status: string;
};

type ResourceResponse = { items: Resource[] };
type ResourceState =
  | { status: "loading" }
  | { status: "ready"; items: Resource[] }
  | { status: "error"; message: string };

const columns: Record<string, string[]> = {
  pods: ["Name", "Namespace", "Status"],
  deployments: ["Name", "Namespace", "Status"],
  replicaSets: ["Name", "Namespace", "Status"],
  services: ["Name", "Namespace", "Status"],
  "replica-sets": ["Name", "Namespace", "Status"],
  "daemon-sets": ["Name", "Namespace", "Status"],
  "stateful-sets": ["Name", "Namespace", "Status"],
  jobs: ["Name", "Namespace", "Status"],
  "cron-jobs": ["Name", "Namespace", "Status"],
  "replication-controllers": ["Name", "Namespace", "Status"],
  nodes: ["Name", "Status", "Cluster"],
  "persistent-volumes": ["Name", "Status"],
  "cluster-roles": ["Name", "Status"],
  "storage-classes": ["Name", "Status"],
};

const clusterScoped = new Set(["nodes", "persistent-volumes", "cluster-roles", "storage-classes"]);

export function CoreResourceView({ resource, namespace }: { resource: string; namespace: string }) {
  const [state, setState] = useState<ResourceState>({ status: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    setState({ status: "loading" });
    fetch(`/api/cluster/resources?resource=${encodeURIComponent(resource)}&namespace=${encodeURIComponent(namespace)}`, {
      signal: controller.signal,
      cache: "no-store",
    })
      .then(async (response) => {
        const body = (await response.json()) as ResourceResponse & { message?: string };
        if (!response.ok) throw new Error(body.message ?? "Unable to load resources");
        setState({ status: "ready", items: body.items });
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setState({ status: "error", message: error instanceof Error ? error.message : "Unable to load resources" });
      });

    return () => controller.abort();
  }, [namespace, resource]);

  const title = resource.charAt(0).toUpperCase() + resource.slice(1);
  const tableColumns = columns[resource] ?? columns.pods;

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="text-sm font-medium uppercase tracking-[0.2em] text-slate-400">Live cluster data</p>
          <h2 className="text-3xl font-semibold text-slate-700">{title}</h2>
        </div>
        <span className="rounded-full bg-cyan-100 px-3 py-1 text-sm font-medium text-cyan-800">FastAPI</span>
      </div>

      {state.status === "loading" ? <p className="rounded-lg bg-slate-100 p-5 text-slate-500">Loading {title.toLowerCase()}...</p> : null}
      {state.status === "error" ? <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-5 text-red-700">{state.message}</p> : null}
      {state.status === "ready" && state.items.length === 0 ? <p className="rounded-lg bg-slate-100 p-5 text-slate-500">No {title.toLowerCase()} found for this scope.</p> : null}
      {state.status === "ready" && state.items.length > 0 ? (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="min-w-full text-left text-base">
            <thead className="bg-slate-100 text-slate-600">
              <tr>{tableColumns.map((column) => <th key={column} className="px-4 py-3 font-medium">{column}</th>)}</tr>
            </thead>
            <tbody>
              {state.items.map((item) => {
                const detailParams = new URLSearchParams({
                  resourceType: resource,
                  name: item.name,
                });
                if (item.namespace) detailParams.set("namespace", item.namespace);

                return (
                  <tr key={`${item.kind}-${item.namespace ?? "cluster"}-${item.name}`} className="border-t border-slate-200 text-slate-700 hover:bg-slate-50">
                    <td className="px-4 py-3 font-medium">
                      <Link
                        href={`/dashboard/detail?${detailParams}`}
                        className="text-cyan-600 hover:underline"
                      >
                        {item.name}
                      </Link>
                    </td>
                    {!clusterScoped.has(resource) ? <td className="px-4 py-3">{item.namespace ?? "All namespaces"}</td> : null}
                    <td className="px-4 py-3">{item.status}</td>
                    {resource === "nodes" ? <td className="px-4 py-3">{item.cluster}</td> : null}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
