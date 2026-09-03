import { Suspense } from "react";
import ResourceDetailView from "@/components/resource-detail-view";

export default async function DetailPage({
  searchParams,
}: {
  searchParams?: Promise<{ resourceType?: string; name?: string; namespace?: string }> | { resourceType?: string; name?: string; namespace?: string };
}) {
  const params = await Promise.resolve(searchParams ?? {});
  const resourceType = params.resourceType ?? "pods";
  const name = params.name ?? "";
  const namespace = params.namespace ?? null;

  return (
    <Suspense fallback={<ResourceDetailView resourceType={resourceType} name={name} namespace={namespace} />}>
      <ResourceDetailView resourceType={resourceType} name={name} namespace={namespace} />
    </Suspense>
  );
}
