"use client";

import { useMemo, useState } from "react";
import { DashboardShell } from "@/components/dashboard-shell";
import { CoreResourceView } from "@/components/core-resource-view";
import { OverviewView } from "@/components/overview-view";
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

export function Dashboard({ initResource, initNamespace }: { initResource: string; initNamespace: string }) {
  const [resource, setResource] = useState(initResource);
  const [namespace, setNamespace] = useState(initNamespace);

  const navigate = (nextResource: string, nextNamespace: string) => {
    setResource(nextResource);
    setNamespace(nextNamespace);
    const params = new URLSearchParams();
    params.set("resource", nextResource);
    params.set("namespace", nextNamespace);
    window.history.replaceState(null, "", `/dashboard?${params.toString()}`);
  };

  const renderView = useMemo(() => {
    if (resourceViewTypes.has(resource)) {
      return <CoreResourceView resource={resource} namespace={namespace} />;
    }
    switch (resource) {
      case "namespaces":
        return <NamespacesView />;
      case "overview":
      case "workloads":
      default:
        return <OverviewView />;
    }
  }, [resource, namespace]);

  return (
    <DashboardShell activeResource={resource} activeNamespace={namespace} onNavigate={navigate}>
      {renderView}
    </DashboardShell>
  );
}
