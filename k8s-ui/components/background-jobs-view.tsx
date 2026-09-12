"use client";

import { useRouter } from "next/navigation";
import { BriefcaseBusiness } from "lucide-react";
import { DashboardShell } from "@/components/dashboard-shell";
import { BackgroundJobsTable } from "@/components/marketplace-history";
import { useClusterSelection } from "@/lib/use-cluster-selection";
import type { BackendUser } from "@/lib/auth";

export function BackgroundJobsView({ user }: { user: BackendUser }) {
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
      activeResource="background-jobs"
      activeNamespace="default"
      activeCluster={cluster}
      clusters={clusters}
      onSelectCluster={selectCluster}
      onNavigate={handleNav}
    >
      <div>
        <div className="mb-6 flex items-start gap-3">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <BriefcaseBusiness className="size-5" />
          </span>
          <div>
            <h1 className="text-2xl font-semibold text-foreground">Background jobs</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Monitor long-running Kubernetes and Helm operations.
            </p>
          </div>
        </div>
        <BackgroundJobsTable canManage={user.role === "admin" || user.role === "operator"} />
      </div>
    </DashboardShell>
  );
}
