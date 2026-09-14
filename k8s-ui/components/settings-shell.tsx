"use client";

import { useRouter } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { DashboardShell } from "@/components/dashboard-shell";
import { useClusterSelection } from "@/lib/use-cluster-selection";
import type { BackendUser } from "@/lib/auth-client";

const sections = [
  "General",
  "Appearance",
  "AI Providers",
  "Models",
  "Integrations",
  "Secrets & Credentials",
  "Audit Logs",
  "AI Agents",
] as const;

export function SettingsShell({ user, children }: { user: BackendUser; children: React.ReactNode }) {
  const router = useRouter();
  const { cluster, clusters, selectCluster } = useClusterSelection();

  const handleNav = (resource: string, namespace: string) => {
    const params = new URLSearchParams({ resource, namespace });
    if (cluster) params.set("cluster", cluster);
    router.push(`/dashboard?${params.toString()}`);
  };

  return (
    <DashboardShell
      user={user}
      activeResource="settings"
      activeNamespace="default"
      activeCluster={cluster}
      clusters={clusters}
      onSelectCluster={selectCluster}
      onNavigate={handleNav}
    >
      <div className="space-y-6">
        <div>
          <p className="text-sm font-medium uppercase tracking-[0.18em] text-primary">Administration</p>
          <h1 className="mt-2 text-2xl font-semibold text-foreground">Settings</h1>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">
            Manage KubePilot configuration from one protected control plane.
          </p>
        </div>

        <nav aria-label="Settings sections" className="flex flex-wrap gap-2 border-b border-border pb-3">
          <span
            aria-current="page"
            className="rounded-md bg-sidebar-accent px-3 py-2 text-sm font-medium text-sidebar-accent-foreground"
          >
            Overview
          </span>
          {sections.map((section) => (
            <span
              key={section}
              aria-disabled="true"
              className="inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm text-muted-foreground"
            >
              {section}
              <Badge variant="outline" className="text-[10px] font-normal">
                Planned
              </Badge>
            </span>
          ))}
        </nav>

        {children}
      </div>
    </DashboardShell>
  );
}
