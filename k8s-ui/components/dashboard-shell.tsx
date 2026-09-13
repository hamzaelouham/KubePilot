"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ChevronDown,
  Boxes,
  BriefcaseBusiness,
  Database,
  KeyRound,
  Layers,
  LayoutDashboard,
  Network,
  Server,
  ShieldCog,
  SlidersHorizontal,
  Store,
  SquarePen,
  Sparkles,
  Users,
  type LucideIcon,
} from "lucide-react";
import { NotificationPopover } from "@/components/notification-popover";
import { UserMenu } from "@/components/user-menu";
import { ClusterContext } from "@/lib/cluster-context";
import { withCluster } from "@/lib/cluster-query";
import { ADMIN_ROLE, type BackendUser } from "@/lib/auth-client";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

type NavGroup = {
  label: string;
  icon: LucideIcon;
  items: { id: string; label: string }[];
};

const navGroups: NavGroup[] = [
  {
    label: "Workloads",
    icon: Layers,
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
    icon: Network,
    items: [{ id: "services", label: "Services" }],
  },
  {
    label: "Configuration",
    icon: SlidersHorizontal,
    items: [{ id: "namespaces", label: "Namespaces" }],
  },
  {
    label: "Storage",
    icon: Database,
    items: [
      { id: "persistent-volumes", label: "PersistentVolumes" },
      { id: "storage-classes", label: "StorageClasses" },
    ],
  },
  {
    label: "Cluster",
    icon: Server,
    items: [
      { id: "nodes", label: "Nodes" },
      { id: "cluster-roles", label: "ClusterRoles" },
    ],
  },
];

const adminNavItems: {
  id: string;
  label: string;
  href: string;
  adminOnly: boolean;
  icon: LucideIcon;
}[] = [
  { id: "clusters", label: "Clusters", href: "/settings/clusters", adminOnly: false, icon: Server },
  { id: "users", label: "Users", href: "/settings/users", adminOnly: true, icon: Users },
  { id: "password", label: "Password", href: "/settings/password", adminOnly: false, icon: KeyRound },
];

const ADMIN_GROUP = "Administration";

const adminResourceIds = new Set(adminNavItems.map((item) => item.id));

const resourceTitles: Record<string, string> = {
  overview: "Overview",
  assistant: "AI Assistant",
  workloads: "Workloads",
  marketplace: "Marketplace",
  "background-jobs": "Background jobs",
  "manage-resources": "Manage resources",
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
  password: "Password",
};

type DashboardShellProps = {
  user?: BackendUser;
  activeResource: string;
  activeNamespace: string;
  activeCluster: string;
  clusters?: string[];
  onSelectCluster?: (cluster: string) => void;
  namespaceOptions?: string[];
  namespaceDisabled?: boolean;
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
  namespaceOptions: suppliedNamespaces,
  namespaceDisabled = false,
  onNavigate,
  children,
}: DashboardShellProps) {
  const headerLabel = resourceTitles[activeResource] ?? "Overview";

  const [discoveredNamespaces, setNamespaceOptions] = useState<string[]>(["default"]);
  const namespaceOptions = suppliedNamespaces ?? discoveredNamespaces;

  useEffect(() => {
    if (suppliedNamespaces !== undefined) return;
    const controller = new AbortController();
    fetch(withCluster("/api/cluster/namespaces", activeCluster), { signal: controller.signal, cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) return;
        const body = (await response.json()) as { items: { name: string }[] };
        const names = body.items.map((n) => n.name);
        if (!controller.signal.aborted && names.length > 0) setNamespaceOptions(names);
      })
      .catch(() => {});
    return () => controller.abort();
  }, [activeCluster, suppliedNamespaces]);

  const isActive = (id: string) => id === activeResource;

  const groupForResource = (resource: string): string | undefined =>
    navGroups.find((group) => group.items.some((item) => item.id === resource))?.label ??
    (adminResourceIds.has(resource) ? ADMIN_GROUP : undefined);

  const [manuallyOpened, setManuallyOpened] = useState<Set<string>>(() => new Set());
  const [manuallyClosed, setManuallyClosed] = useState<Set<string>>(() => new Set());

  const groupContainsActive = (label: string) => groupForResource(activeResource) === label;

  const [activeGroup, setActiveGroup] = useState<string | undefined>(groupForResource(activeResource));
  if (activeGroup !== groupForResource(activeResource)) {
    const nextGroup = groupForResource(activeResource);
    setActiveGroup(nextGroup);
    if (nextGroup) {
      setManuallyClosed((prev) => {
        if (!prev.has(nextGroup)) return prev;
        const next = new Set(prev);
        next.delete(nextGroup);
        return next;
      });
    }
  }

  const isGroupOpen = (label: string) => {
    if (manuallyOpened.has(label)) return true;
    if (manuallyClosed.has(label)) return false;
    return groupContainsActive(label);
  };

  const toggleGroup = (label: string) => {
    if (isGroupOpen(label)) {
      setManuallyClosed((prev) => new Set(prev).add(label));
      setManuallyOpened((prev) => {
        const next = new Set(prev);
        next.delete(label);
        return next;
      });
    } else {
      setManuallyClosed((prev) => {
        const next = new Set(prev);
        next.delete(label);
        return next;
      });
      setManuallyOpened((prev) => new Set(prev).add(label));
    }
  };

  return (
    <ClusterContext.Provider value={activeCluster}>
      <div className="min-h-screen overflow-x-clip bg-background text-foreground">
        <div className="border-b border-border bg-card">
          <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
            <Link href="/" className="flex min-w-0 items-center gap-2.5">
              <span className="flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <Boxes aria-hidden="true" className="size-5" />
              </span>
              <span className="text-xl font-semibold tracking-tight text-foreground">KubePilot</span>
            </Link>

            <div className="ml-auto flex items-center gap-2">
              <div className="flex min-w-0 items-center gap-2 rounded-lg border border-border bg-header-control px-2.5 py-1.5">
                <Server className="size-4 shrink-0 text-muted-foreground" />
                <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Cluster</span>
                {activeCluster ? (
                  <Select
                  value={activeCluster}
                  items={(clusters?.length ? clusters : [activeCluster]).map((name) => ({ value: name, label: name }))}
                  onValueChange={(value) => {
                    if (value) onSelectCluster?.(value);
                  }}
                >
                    <SelectTrigger
                      aria-label="Active cluster"
                      className="h-8 min-w-28 gap-1.5 border-0 bg-transparent px-1 text-sm font-medium text-foreground shadow-none hover:bg-transparent data-[size=default]:h-8"
                    >
                      <SelectValue placeholder="Select cluster" />
                    </SelectTrigger>
                    <SelectContent align="end">
                      <SelectGroup>
                      {(clusters && clusters.length > 0 ? clusters : [activeCluster]).map((name) => (
                        <SelectItem
                          key={name}
                          value={name}
                          className="data-selected:bg-primary/10 data-selected:text-primary data-selected:font-medium"
                        >
                          <span className="flex items-center gap-2">
                            <span className="size-2 shrink-0 rounded-full bg-emerald-500" />
                            <Server className="size-4 text-muted-foreground" />
                            {name}
                          </span>
                        </SelectItem>
                      ))}
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                ) : (
                  <span className="text-sm text-muted-foreground">Cluster unavailable</span>
                )}
            </div>
            <NotificationPopover />
            {user ? <UserMenu user={user} /> : null}
          </div>
        </div>
      </div>

      <div className="bg-primary text-primary-foreground">
        <div className="mx-auto flex max-w-[1600px] items-center gap-3 px-4 py-3 text-lg font-medium">
          <LayoutDashboard aria-hidden="true" className="size-5" />
          <span>{headerLabel}</span>
        </div>
      </div>

      <div className="mx-auto max-w-[1600px] px-0 py-0">
        <div className="flex min-h-[calc(100vh-160px)]">
          <aside className="w-56 shrink-0 border-r border-sidebar-border bg-sidebar p-4 lg:w-[286px]">
            <nav className="space-y-4">
              <button
                type="button"
                onClick={() => onNavigate("overview", activeNamespace)}
                className={`flex w-full cursor-pointer items-center gap-2.5 rounded-md px-3 py-2 text-left text-base transition ${
                  isActive("overview")
                    ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
                    : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                }`}
              >
                <LayoutDashboard className="h-4 w-4 shrink-0" />
                Dashboard
              </button>

              <Link
                href={withCluster(`/assistant?namespace=${encodeURIComponent(activeNamespace)}`, activeCluster)}
                className={`flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-left text-base transition ${isActive("assistant") ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground" : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"}`}
              ><Sparkles className="size-4 shrink-0" />AI Assistant</Link>

              <Link
                href="/marketplace"
                className={`flex w-full cursor-pointer items-center gap-2.5 rounded-md px-3 py-2 text-left text-base transition ${
                  isActive("marketplace")
                    ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
                    : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                }`}
              >
                <Store className="h-4 w-4 shrink-0" />
                Marketplace
              </Link>

              <Link
                href={withCluster("/background-jobs", activeCluster)}
                aria-current={isActive("background-jobs") ? "page" : undefined}
                className={`flex w-full cursor-pointer items-center gap-2.5 rounded-md px-3 py-2 text-left text-base transition ${
                  isActive("background-jobs")
                    ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
                    : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                }`}
              >
                <BriefcaseBusiness className="size-4 shrink-0" />
                Background jobs
              </Link>

              <Link
                href={withCluster(`/manage-resources?namespace=${encodeURIComponent(activeNamespace)}`, activeCluster)}
                aria-current={isActive("manage-resources") ? "page" : undefined}
                className={`flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-left text-base transition ${
                  isActive("manage-resources")
                    ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
                    : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                }`}
              >
                <SquarePen className="size-4 shrink-0" />
                Manage resources
              </Link>

              {navGroups.map((group) => {
                const open = isGroupOpen(group.label);
                const GroupIcon = group.icon;
                return (
                  <Collapsible key={group.label} open={open} onOpenChange={() => toggleGroup(group.label)}>
                    <CollapsibleTrigger className="flex w-full cursor-pointer items-center gap-2.5 rounded-md px-3 py-2 text-left text-base font-medium text-sidebar-foreground transition hover:bg-sidebar-accent hover:text-sidebar-accent-foreground">
                      <GroupIcon className="h-4 w-4 shrink-0 text-sidebar-foreground" />
                      <span>{group.label}</span>
                      <ChevronDown
                        className={`ml-auto h-4 w-4 shrink-0 text-sidebar-foreground transition-transform duration-200 ${
                          open ? "rotate-180" : ""
                        }`}
                      />
                    </CollapsibleTrigger>
                    <CollapsibleContent className="mt-1 space-y-1">
                      {group.items.map((item) => (
                        <button
                          key={item.id}
                          type="button"
                          onClick={() => onNavigate(item.id, activeNamespace)}
                          className={`block w-full cursor-pointer rounded-md px-3 py-2 pl-10 text-left text-base transition ${
                            isActive(item.id)
                              ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
                              : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                          }`}
                        >
                          {item.label}
                        </button>
                      ))}
                    </CollapsibleContent>
                  </Collapsible>
                );
              })}
            </nav>

            <div className="mt-6">
              <label className="mb-2 block text-sm font-medium text-sidebar-foreground">Namespace</label>
              <Select
                value={activeNamespace || "__all__"}
                onValueChange={(value) => {
                  if (value) onNavigate(activeResource, value === "__all__" ? "" : value);
                }}
                disabled={namespaceDisabled}
              >
                <SelectTrigger aria-label="Namespace" className="h-10 w-full border-sidebar-border bg-sidebar px-3 text-sm font-medium text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground">
                  <SelectValue placeholder="Select namespace" />
                </SelectTrigger>
                <SelectContent align="start">
                  <SelectGroup>
                    {suppliedNamespaces !== undefined ? <SelectItem value="__all__">All namespaces</SelectItem> : null}
                    {suppliedNamespaces !== undefined && activeNamespace && !namespaceOptions.includes(activeNamespace)
                      ? <SelectItem value={activeNamespace}>{activeNamespace} (unavailable)</SelectItem> : null}
                    {namespaceOptions.map((namespace) => (
                      <SelectItem key={namespace} value={namespace}>{namespace}</SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>

            {user ? (
              <Collapsible
                className="mt-6"
                open={isGroupOpen(ADMIN_GROUP)}
                onOpenChange={() => toggleGroup(ADMIN_GROUP)}
              >
                <CollapsibleTrigger className="flex w-full cursor-pointer items-center gap-2.5 rounded-md px-3 py-2 text-left text-base font-medium text-sidebar-foreground transition hover:bg-sidebar-accent hover:text-sidebar-accent-foreground">
                  <ShieldCog className="h-4 w-4 shrink-0 text-sidebar-foreground" />
                  <span>{ADMIN_GROUP}</span>
                  <ChevronDown
                    className={`ml-auto h-4 w-4 shrink-0 text-sidebar-foreground transition-transform duration-200 ${
                      isGroupOpen(ADMIN_GROUP) ? "rotate-180" : ""
                    }`}
                  />
                </CollapsibleTrigger>
                <CollapsibleContent className="mt-1 space-y-1">
                  {adminNavItems
                    .filter((item) => !item.adminOnly || user.role === ADMIN_ROLE)
                    .map((item) => (
                      <Link
                        key={item.id}
                        href={item.href}
                        className={`flex w-full cursor-pointer items-center gap-2.5 rounded-md px-3 py-2 pl-10 text-left text-base transition ${
                            isActive(item.id)
                              ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
                            : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                        }`}
                      >
                        <item.icon className="size-4 shrink-0" />
                        {item.label}
                      </Link>
                    ))}
                </CollapsibleContent>
              </Collapsible>
            ) : null}
          </aside>

          <main className="min-w-0 flex-1 bg-surface p-4 md:p-6">
            <div className="min-w-0 rounded-2xl border border-border/70 bg-surface-elevated p-5 shadow-sm md:p-6">{children}</div>
          </main>
        </div>
      </div>
    </div>
    </ClusterContext.Provider>
  );
}
