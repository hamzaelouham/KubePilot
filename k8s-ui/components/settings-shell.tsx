"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { DashboardShell } from "@/components/dashboard-shell";
import { useClusterSelection } from "@/lib/use-cluster-selection";
import type { BackendUser } from "@/lib/auth-client";
import { scrollPageToTop } from "@/lib/navigation";

const sections = [
  { label: "AI Providers", href: "/settings/providers" },
  { label: "Models", href: "/settings/models" },
  { label: "Integrations", href: "/settings/integrations" },
  { label: "Secrets & Credentials", href: "/settings/credentials" },
  { label: "Conversations", href: "/settings/conversations" },
  { label: "Audit Logs", href: "/settings/audit-logs" },
] as const;

export function SettingsShell({ user, children }: { user: BackendUser; children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
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
          {sections.map((section) => (
            <Link
              key={section.href}
              href={section.href}
              onClick={scrollPageToTop}
              aria-current={pathname === section.href ? "page" : undefined}
              className={`inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm ${pathname === section.href ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}
            >
              {section.label}
            </Link>
          ))}
        </nav>

        {children}
      </div>
    </DashboardShell>
  );
}
