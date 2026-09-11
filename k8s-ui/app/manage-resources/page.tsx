import { ManageResourcesView } from "@/components/manage-resources-view";
import { requireUsableBackendUser } from "@/lib/auth";

export default async function ManageResourcesPage({ searchParams }: {
  searchParams: Promise<{ cluster?: string; namespace?: string }>;
}) {
  const user = await requireUsableBackendUser();
  const query = await searchParams;
  return <ManageResourcesView user={user}
    initialCluster={typeof query.cluster === "string" ? query.cluster : undefined}
    initialNamespace={typeof query.namespace === "string" ? query.namespace : ""} />;
}
