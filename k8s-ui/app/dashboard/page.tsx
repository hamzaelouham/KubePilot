import { Dashboard } from "@/components/dashboard";

export default async function DashboardPage({
  searchParams,
}: {
  searchParams?: Promise<{ resource?: string; namespace?: string }> | { resource?: string; namespace?: string };
}) {
  const resolvedParams = await Promise.resolve(searchParams ?? {});
  const resource = resolvedParams.resource ?? "overview";
  const namespace = resolvedParams.namespace ?? "default";

  return <Dashboard initResource={resource} initNamespace={namespace} />;
}
