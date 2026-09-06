import { Dashboard } from "@/components/dashboard";
import { requireUsableBackendUser } from "@/lib/auth";

export default async function DashboardPage({
  searchParams,
}: {
  searchParams?: Promise<{ resource?: string; namespace?: string; cluster?: string }> | { resource?: string; namespace?: string; cluster?: string };
}) {
  const user = await requireUsableBackendUser();
  const resolvedParams = await Promise.resolve(searchParams ?? {});
  const resource = resolvedParams.resource ?? "overview";
  const namespace = resolvedParams.namespace ?? "default";
  const cluster = resolvedParams.cluster;

  return <Dashboard user={user} initResource={resource} initNamespace={namespace} initCluster={cluster} />;
}