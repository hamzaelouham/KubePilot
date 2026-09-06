import { Suspense } from "react";
import ResourceDetailView from "@/components/resource-detail-view";
import { requireUsableBackendUser } from "@/lib/auth";

export default async function DetailPage({
  searchParams,
}: {
  searchParams?: Promise<{ resourceType?: string; name?: string; namespace?: string; cluster?: string }> | { resourceType?: string; name?: string; namespace?: string; cluster?: string };
}) {
  await requireUsableBackendUser();
  const params = await Promise.resolve(searchParams ?? {});
  const resourceType = params.resourceType ?? "pods";
  const name = params.name ?? "";
  const namespace = params.namespace ?? null;
  const cluster = params.cluster;

  return (
    <Suspense fallback={<ResourceDetailView resourceType={resourceType} name={name} namespace={namespace} cluster={cluster} />}>
      <ResourceDetailView resourceType={resourceType} name={name} namespace={namespace} cluster={cluster} />
    </Suspense>
  );
}
