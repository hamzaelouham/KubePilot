"use client";

import { useRouter } from "next/navigation";
import { DashboardShell } from "@/components/dashboard-shell";
import { MarketplaceBrowser } from "@/components/marketplace-browser";
import { useClusterSelection } from "@/lib/use-cluster-selection";
import type { BackendUser } from "@/lib/auth";
import type { InitialMarketplaceData } from "@/lib/marketplace-server";

export function MarketplaceView({ user, initialData }: { user: BackendUser; initialData: InitialMarketplaceData }) {
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
      activeResource="marketplace"
      activeNamespace="default"
      activeCluster={cluster}
      clusters={clusters}
      onSelectCluster={selectCluster}
      onNavigate={handleNav}
    >
      <div>
        <div className="mb-6">
          <h1 className="text-2xl font-semibold text-foreground">Marketplace</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Discover and install Kubernetes applications.
          </p>
        </div>
        <MarketplaceBrowser
          cluster={cluster}
          clusters={clusters}
          onSelectCluster={selectCluster}
          initialData={initialData}
        />
      </div>
    </DashboardShell>
  );
}
