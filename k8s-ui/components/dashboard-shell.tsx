"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { NotificationPopover } from "@/components/notification-popover";
import { UserMenu } from "@/components/user-menu";
import { ClusterContext } from "@/lib/cluster-context";
import { withCluster } from "@/lib/cluster-query";
import { ADMIN_ROLE, type BackendUser } from "@/lib/auth-client";

type NavGroup = {
  label: string;
  items: { id: string; label: string }[];
};

const navGroups: NavGroup[] = [
  {
    label: "Overview",
    items: [{ id: "overview", label: "Dashboard" }],
  },
  {
    label: "Workloads",
    items: [
      { id: "pods", label: "Pods" },
      { id: "deployments", label: "Deployments" },
      { id: "stateful-sets", label: "StatefulSets" },
      { id: "daemon-sets", label: "DaemonSets" },
      { id: "jobs", label: "Jobs" },
      { id: "cron-jobs", label: "CronJobs" },
      { id: "replica-sets", label: "ReplicaSets" },
      { id: "replication-controllers", label: "ReplicationControllers" },
    ],
  },
  {
    label: "Network",
    items: [{ id: "services", label: "Services" }],
  },
  {
    label: "Configuration",
    items: [{ id: "namespaces", label: "Namespaces" }],
  },
  {
    label: "Storage",
    items: [
      { id: "persistent-volumes", label: "PersistentVolumes" },
      { id: "storage-classes", label: "StorageClasses" },
    ],
  },
  {
    label: "Cluster",
    items: [
      { id: "nodes", label: "Nodes" },
      { id: "cluster-roles", label: "ClusterRoles" },
    ],
  },
];

const resourceTitles: Record<string, string> = {
  overview: "Overview",
  workloads: "Workloads",
  users: "Users",
  clusters: "Clusters",
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
  activeCluster: string;
  clusters?: string[];
  onSelectCluster?: (cluster: string) => void;
  onNavigate: (resource: string, namespace: string) => void;
  children: React.ReactNode;
};

export function DashboardShell({
  user,
  activeResource,
  activeNamespace,
  activeCluster,
  clusters,
  onSelectCluster,
  onNavigate,
  children,
}: DashboardShellProps) {
  const headerLabel = resourceTitles[activeResource] ?? "Overview";

  const [namespaceOptions, setNamespaceOptions] = useState<string[]>(["default"]);

  useEffect(() => {
    const controller = new AbortController();
    fetch(withCluster("/api/cluster/namespaces", activeCluster), { signal: controller.signal, cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) return;
        const body = (await response.json()) as { items: { name: string }[] };
        const names = body.items.map((n) => n.name);
        if (names.length > 0) setNamespaceOptions(names);
      })
      .catch(() => {});
    return () => controller.abort();
  }, [activeCluster]);

  const isActive = (id: string) => id === activeResource;

  return (
    <ClusterContext.Provider value={activeCluster}>
      <div className="min-h-screen overflow-x-clip bg-background text-foreground">
        <div className="border-b border-border bg-card">
          <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
            <Link href="/" className="flex min-w-0 items-center gap-2.5">
              <span className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/10 text-lg text-primary">
                ☸
              </span>
              <span className="text-xl font-semibold tracking-tight text-foreground">KubePilot</span>
            </Link>

            <div className="ml-auto flex items-center gap-2">
              <div className="flex min-w-0 items-center gap-2 rounded-xl border border-border bg-header-control px-3 py-2">
                <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Cluster</span>
                {activeCluster ? (
                  <select
                    value={activeCluster}
                    aria-label="Active cluster"
                    onChange={onSelectCluster ? (event) => onSelectCluster(event.target.value) : undefined}
                    className="bg-transparent text-sm font-medium text-foreground outline-none"
                  >
                    {(clusters && clusters.length > 0 ? clusters : [activeCluster]).map((name) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                  </select>
                ) : (
                  <span className="text-sm text-muted-foreground">Cluster unavailable</span>
                )}
              </div>
            <button className="flex h-10 w-10 cursor-pointer items-center justify-center rounded-xl border border-border bg-header-control text-xl text-muted-foreground">
              +
            </button>
            <NotificationPopover />
            {user ? <UserMenu user={user} /> : null}
          </div>
        </div>
      </div>

      <div className="bg-primary text-primary-foreground">
        <div className="mx-auto flex max-w-[1600px] items-center gap-3 px-4 py-3 text-lg font-medium">
          <span className="text-xl">☰</span>
          <span>{headerLabel}</span>
        </div>
      </div>

      <div className="mx-auto max-w-[1600px] px-0 py-0">
        <div className="flex min-h-[calc(100vh-160px)]">
          <aside className="w-56 shrink-0 border-r border-sidebar-border bg-sidebar p-4 lg:w-[286px]">
            <nav className="space-y-6">
              {navGroups.map((group) => (
                <div key={group.label}>
                  <p className="mb-1 px-3 text-xs font-medium uppercase tracking-[0.15em] text-sidebar-foreground/70">
                    {group.label}
                  </p>
                  <div className="space-y-1">
                    {group.items.map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => onNavigate(item.id, activeNamespace)}
                        className={`block w-full cursor-pointer rounded-md px-3 py-2 text-left text-base transition ${
                          isActive(item.id)
                            ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
                            : "text-sidebar-foreground/70 hover:bg-sidebar-accent"
                        }`}
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </nav>

            <div className="mt-6">
              <label className="mb-2 block text-sidebar-foreground/70">Namespace</label>
              <select
                value={activeNamespace}
                onChange={(event) => onNavigate(activeResource, event.target.value)}
                className="w-full rounded-md border border-border bg-card px-3 py-2 text-base text-foreground outline-none"
              >
                {namespaceOptions.map((namespace) => (
                  <option key={namespace} value={namespace}>
                    {namespace}
                  </option>
                ))}
              </select>
            </div>

            {user ? (
              <nav className="mt-6">
                <p className="mb-1 px-3 text-xs font-medium uppercase tracking-[0.15em] text-sidebar-foreground/70">
                  Administration
                </p>
                <div className="space-y-1">
                  <Link
                    href="/settings/clusters"
                    className="block w-full cursor-pointer rounded-md px-3 py-2 text-left text-base text-sidebar-foreground/70 transition hover:bg-sidebar-accent"
                  >
                    Clusters
                  </Link>
                  {user.role === ADMIN_ROLE ? (
                    <Link
                      href="/settings/users"
                      className="block w-full cursor-pointer rounded-md px-3 py-2 text-left text-base text-sidebar-foreground/70 transition hover:bg-sidebar-accent"
                    >
                      Users
                    </Link>
                  ) : null}
                  <Link
                    href="/settings/password"
                    className="block w-full cursor-pointer rounded-md px-3 py-2 text-left text-base text-sidebar-foreground/70 transition hover:bg-sidebar-accent"
                  >
                    Password
                  </Link>
                </div>
              </nav>
            ) : null}
          </aside>

          <main className="min-w-0 flex-1 bg-surface p-4 md:p-6">
            <div className="min-w-0 rounded-md border border-border bg-surface-elevated p-4 shadow-sm md:p-5">{children}</div>
          </main>
        </div>
      </div>
    </div>
    </ClusterContext.Provider>
  );
}