"use client";

import { useMemo, useState } from "react";
import type { BackendUser } from "@/lib/auth";
import { DashboardShell } from "@/components/dashboard-shell";
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
}: {
  user: BackendUser;
  initResource: string;
  initNamespace: string;
}) {
  const [resource, setResource] = useState(initResource);
  const [namespace, setNamespace] = useState(initNamespace);

  const navigate = (nextResource: string, nextNamespace: string) => {
    setResource(nextResource);
    setNamespace(nextNamespace);
    const params = new URLSearchParams();
    params.set("resource", nextResource);
    params.set("namespace", nextNamespace);
    window.history.replaceState(null, "", `/dashboard?${params.toString()}`);
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
      onNavigate={navigate}
    >
      {renderView}
    </DashboardShell>
  );
}
