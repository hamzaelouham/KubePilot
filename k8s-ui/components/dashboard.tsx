"use client";

import { useEffect, useMemo, useState } from "react";
import type { BackendUser } from "@/lib/auth";
import { DashboardShell } from "@/components/dashboard-shell";
import { useClusterStatus } from "@/lib/use-cluster-status";
import { CoreResourceView } from "@/components/core-resource-view";
import { OverviewView } from "@/components/overview-view";
import { ClusterView } from "@/components/cluster-view";
import { WorkloadsView } from "@/components/workloads-view";
import { NamespacesView } from "@/components/namespaces-view";

const resourceViewTypes = new Set([
  "deployments",
  "pods",
  "services",
  "nodes",
  "replica-sets",
  "daemon-sets",
  "stateful-sets",
  "jobs",
  "cron-jobs",
  "replication-controllers",
  "persistent-volumes",
  "cluster-roles",
  "storage-classes",
]);

export function Dashboard({
  user,
  initResource,
  initNamespace,
  initCluster,
}: {
  user: BackendUser;
  initResource: string;
  initNamespace: string;
  initCluster?: string;
}) {
  const [resource, setResource] = useState(initResource);
  const [namespace, setNamespace] = useState(initNamespace);
  const cluster = useClusterStatus(initCluster);

  useEffect(() => {
    if (!cluster || cluster === initCluster) return;
    const params = new URLSearchParams(window.location.search);
    params.set("cluster", cluster);
    window.history.replaceState(null, "", `/dashboard?${params.toString()}`);
  }, [cluster, initCluster]);

  const syncUrl = (nextResource: string, nextNamespace: string, nextCluster: string) => {
    const params = new URLSearchParams();
    params.set("resource", nextResource);
    params.set("namespace", nextNamespace);
    if (nextCluster) params.set("cluster", nextCluster);
    window.history.replaceState(null, "", `/dashboard?${params.toString()}`);
  };

  const navigate = (nextResource: string, nextNamespace: string) => {
    setResource(nextResource);
    setNamespace(nextNamespace);
    syncUrl(nextResource, nextNamespace, cluster);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const renderView = useMemo(() => {
    if (resourceViewTypes.has(resource)) {
      return <CoreResourceView resource={resource} namespace={namespace} />;
    }
    switch (resource) {
      case "overview":
        return <OverviewView />;
      case "cluster":
        return <ClusterView />;
      case "workloads":
        return <WorkloadsView />;
      case "namespaces":
        return <NamespacesView />;
      default:
        return <OverviewView />;
    }
  }, [resource, namespace]);

  return (
    <DashboardShell
      user={user}
      activeResource={resource}
      activeNamespace={namespace}
      activeCluster={cluster}
      onNavigate={navigate}
    >
      {renderView}
    </DashboardShell>
  );
}
