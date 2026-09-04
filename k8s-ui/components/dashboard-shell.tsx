"use client";

import { useEffect, useState } from "react";

async function signOut() {
  await fetch("/api/logout", { method: "POST" });
  window.location.href = "/login";
}

const navItems = [
  { id: "cluster", label: "Cluster" },
  { id: "cluster-roles", label: "Cluster Roles" },
  { id: "namespaces", label: "Namespaces" },
  { id: "nodes", label: "Nodes" },
  { id: "persistent-volumes", label: "Persistent Volumes" },
  { id: "storage-classes", label: "Storage Classes" },
];

const secondaryNav = [
  { id: "overview", label: "Overview" },
  { id: "workloads", label: "Workloads" },
  { id: "cron-jobs", label: "Cron Jobs" },
  { id: "daemon-sets", label: "Daemon Sets" },
  { id: "deployments", label: "Deployments" },
  { id: "jobs", label: "Jobs" },
  { id: "pods", label: "Pods" },
  { id: "replica-sets", label: "Replica Sets" },
  { id: "replication-controllers", label: "Replication Controllers" },
  { id: "services", label: "Services" },
  { id: "stateful-sets", label: "Stateful Sets" },
];

const resourceTitles: Record<string, string> = {
  overview: "Overview",
  workloads: "Workloads",
  "cron-jobs": "Cron Jobs",
  "daemon-sets": "Daemon Sets",
  deployments: "Deployments",
  jobs: "Jobs",
  pods: "Pods",
  "replica-sets": "Replica Sets",
  "replication-controllers": "Replication Controllers",
  services: "Services",
  "stateful-sets": "Stateful Sets",
  cluster: "Cluster",
  "cluster-roles": "Cluster Roles",
  namespaces: "Namespaces",
  nodes: "Nodes",
  "persistent-volumes": "Persistent Volumes",
  "storage-classes": "Storage Classes",
};

type DashboardShellProps = {
  activeResource: string;
  activeNamespace: string;
  onNavigate: (resource: string, namespace: string) => void;
  children: React.ReactNode;
};

export function DashboardShell({ activeResource, activeNamespace, onNavigate, children }: DashboardShellProps) {
  const headerLabel = resourceTitles[activeResource] ?? "Overview";

  const [namespaceOptions, setNamespaceOptions] = useState<string[]>(["default"]);

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/cluster/namespaces", { signal: controller.signal, cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) return;
        const body = (await response.json()) as { items: { name: string }[] };
        const names = body.items.map((n) => n.name);
        if (names.length > 0) setNamespaceOptions(names);
      })
      .catch(() => {});
    return () => controller.abort();
  }, []);

  const isActive = (id: string) => id === activeResource;

  return (
    <div className="min-h-screen bg-[#ebeff3] text-slate-800">
      <div className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-[1600px] items-center gap-4 px-4 py-4">
          <div className="flex items-center gap-3 text-[#3b4edb]">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#e8ebff] text-xl">◈</div>
            <div className="text-3xl font-semibold tracking-tight text-[#3f4fce]">kubernetes</div>
          </div>

          <div className="ml-auto flex items-center gap-3">
            <div className="flex w-[520px] items-center gap-3 rounded-xl border border-slate-200 bg-[#f2f4f6] px-4 py-2 text-slate-500">
              <span className="text-lg">⌕</span>
              <span className="text-base">Search</span>
            </div>
            <button className="flex h-11 w-11 items-center justify-center rounded-xl border border-slate-200 bg-[#f3f4f6] text-xl text-slate-500">
              +
            </button>
            <button className="flex h-11 w-11 items-center justify-center rounded-xl border border-slate-200 bg-[#f3f4f6] text-xl text-slate-500">
              🔔
            </button>
            <button
              type="button"
              onClick={signOut}
              className="rounded-xl border border-slate-200 bg-[#f3f4f6] px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-200"
            >
              Sign out
            </button>
          </div>
        </div>
      </div>

      <div className="bg-[#4a5ee7] text-white">
        <div className="mx-auto flex max-w-[1600px] items-center gap-3 px-4 py-4 text-xl font-medium">
          <span className="text-2xl">☰</span>
          <span>{headerLabel}</span>
        </div>
      </div>

      <div className="mx-auto max-w-[1600px] px-0 py-0">
        <div className="flex min-h-[calc(100vh-180px)]">
          <aside className="w-[286px] border-r border-slate-200 bg-[#f8f9fb] p-4">
            <nav className="space-y-2">
              {navItems.map((item) => (
                <div key={item.id} className={isActive(item.id) ? "font-medium text-slate-700" : "text-slate-600"}>
                  <button
                    type="button"
                    onClick={() => onNavigate(item.id, activeNamespace)}
                    className="w-full rounded-md px-3 py-2 text-left text-lg transition hover:bg-slate-200/80"
                  >
                    {item.label}
                  </button>
                </div>
              ))}
            </nav>

            <div className="mt-8">
              <label className="mb-2 block text-slate-600">Namespace</label>
              <select
                value={activeNamespace}
                onChange={(event) => onNavigate(activeResource, event.target.value)}
                className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-lg text-slate-700 outline-none"
              >
                {namespaceOptions.map((namespace) => (
                  <option key={namespace} value={namespace}>
                    {namespace}
                  </option>
                ))}
              </select>
            </div>

            <nav className="mt-8 space-y-1">
              {secondaryNav.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onNavigate(item.id, activeNamespace)}
                  className={`block w-full rounded-md px-3 py-2 text-left text-lg ${
                    isActive(item.id) ? "bg-[#eceef3] text-slate-700" : "text-slate-600 hover:bg-slate-200/80"
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </nav>
          </aside>

          <main className="flex-1 bg-[#f5f7f9] p-6">
            <div className="rounded-md border border-slate-200 bg-[#f9fafb] p-5 shadow-sm">{children}</div>
          </main>
        </div>
      </div>
    </div>
  );
}
