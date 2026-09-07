"use client";

import { useRouter } from "next/navigation";
import { DashboardShell } from "@/components/dashboard-shell";
import { ClustersManagement } from "@/components/clusters-management";
import { useClusterSelection } from "@/lib/use-cluster-selection";
import type { BackendUser } from "@/lib/auth";

export function ClusterSettingsView({ user, canManage }: { user: BackendUser; canManage: boolean }) {
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
      activeResource="clusters"
      activeNamespace="default"
      activeCluster={cluster}
      clusters={clusters}
      onSelectCluster={selectCluster}
      onNavigate={handleNav}
    >
      <div>
        <div className="mb-6">
          <h1 className="text-2xl font-semibold text-foreground">Clusters</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Register clusters and control which ones are available. Permissions are enforced by the backend.
          </p>
        </div>
        <ClustersManagement canManage={canManage} />
      </div>
    </DashboardShell>
  );
}