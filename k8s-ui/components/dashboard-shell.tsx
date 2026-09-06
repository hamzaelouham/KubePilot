"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { NotificationPopover } from "@/components/notification-popover";
import { UserMenu } from "@/components/user-menu";
import { ADMIN_ROLE, type BackendUser } from "@/lib/auth-client";

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
  user?: BackendUser;
  activeResource: string;
  activeNamespace: string;
  onNavigate: (resource: string, namespace: string) => void;
  children: React.ReactNode;
};

export function DashboardShell({ user, activeResource, activeNamespace, onNavigate, children }: DashboardShellProps) {
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
    <div className="min-h-screen bg-background text-foreground">
      <div className="border-b border-border bg-card">
        <div className="mx-auto flex max-w-[1600px] items-center gap-4 px-4 py-4">
          <div className="flex items-center gap-3 text-[#3b4edb]">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#e8ebff] text-xl">◈</div>
            <div className="text-3xl font-semibold tracking-tight text-[#3f4fce]">kubernetes</div>
          </div>

          <div className="ml-auto flex items-center gap-3">
            <button className="flex h-11 w-11 cursor-pointer items-center justify-center rounded-xl border border-border bg-header-control text-xl text-slate-500">
              +
            </button>
            <NotificationPopover />
            {user ? <UserMenu user={user} /> : null}
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
          <aside className="w-[286px] border-r border-sidebar-border bg-sidebar p-4">
            <nav className="space-y-2">
              {navItems.map((item) => (
                <div key={item.id} className={isActive(item.id) ? "font-medium text-sidebar-accent-foreground" : "text-sidebar-foreground/70"}>
                  <button
                    type="button"
                    onClick={() => onNavigate(item.id, activeNamespace)}
                    className="w-full cursor-pointer rounded-md px-3 py-2 text-left text-lg transition hover:bg-sidebar-accent"
                  >
                    {item.label}
                  </button>
                </div>
              ))}
            </nav>

            <div className="mt-8">
              <label className="mb-2 block text-sidebar-foreground/70">Namespace</label>
              <select
                value={activeNamespace}
                onChange={(event) => onNavigate(activeResource, event.target.value)}
                className="w-full rounded-md border border-border bg-card px-3 py-2 text-lg text-foreground outline-none"
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
                  className={`block w-full cursor-pointer rounded-md px-3 py-2 text-left text-lg ${
                    isActive(item.id) ? "bg-sidebar-accent text-sidebar-accent-foreground" : "text-sidebar-foreground/70 hover:bg-sidebar-accent"
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </nav>
          {user ? (
            <nav className="mt-8 space-y-1">
              <p className="mb-1 px-3 text-xs font-medium uppercase tracking-[0.15em] text-sidebar-foreground/70">
                Settings
              </p>
              {user.role === ADMIN_ROLE ? (
                <Link
                  href="/settings/users"
                  className="block w-full cursor-pointer rounded-md px-3 py-2 text-left text-lg text-sidebar-foreground/70 transition hover:bg-sidebar-accent sm:text-base"
                >
                  Users
                </Link>
              ) : null}
              <Link
                href="/settings/password"
                className="block w-full cursor-pointer rounded-md px-3 py-2 text-left text-lg text-sidebar-foreground/70 transition hover:bg-sidebar-accent sm:text-base"
              >
                Password
              </Link>
            </nav>
          ) : null}
          </aside>

          <main className="flex-1 bg-surface p-6">
            <div className="rounded-md border border-border bg-surface-elevated p-5 shadow-sm">{children}</div>
          </main>
        </div>
      </div>
    </div>
  );
}
