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

function renderResource(resource: string, namespace: string) {
  if (resourceViewTypes.has(resource)) {
    return <CoreResourceView resource={resource} namespace={namespace} />;
  }

  switch (resource) {
    case "overview":
    case "workloads":
      return <OverviewView />;

    case "namespaces":
      return <NamespacesView />;

    default:
      return <OverviewView />;
  }
}

export default async function DashboardPage({
  searchParams,
}: {
  searchParams?: Promise<{ resource?: string; namespace?: string }> | { resource?: string; namespace?: string };
}) {
  const resolvedParams = await Promise.resolve(searchParams ?? {});
  const resource = resolvedParams.resource ?? "overview";
  const namespace = resolvedParams.namespace ?? "default";

  return <DashboardShell>{renderResource(resource, namespace)}</DashboardShell>;
}
