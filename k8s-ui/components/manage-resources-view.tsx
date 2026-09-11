"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Tabs } from "@base-ui/react/tabs";
import { Plus, RefreshCw, Trash2 } from "lucide-react";
import { DashboardShell } from "@/components/dashboard-shell";
import { DataTable, type DataTableColumn } from "@/components/data-table";
import { CreateResourceDialog } from "@/components/create-resource-dialog";
import { DeleteResourceDialog } from "@/components/delete-resource-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { BackendUser } from "@/lib/auth-client";
import { withCluster } from "@/lib/cluster-query";
import { useClusterSelection } from "@/lib/use-cluster-selection";
import { usePolling } from "@/lib/use-polling";
import { managementRequest, managementUrl, RESOURCE_TYPES, ResourceApiError, scopeLabel, type ManagedResource, type ResourceScope, type ResourceType } from "@/lib/resource-management";

function InventoryMessage({ title, children, action }: { title: string; children: React.ReactNode; action?: React.ReactNode }) {
  return <Empty className="border border-dashed"><EmptyHeader><EmptyTitle>{title}</EmptyTitle><EmptyDescription>{children}</EmptyDescription></EmptyHeader>{action ? <EmptyContent>{action}</EmptyContent> : null}</Empty>;
}

export function ManageResourcesView({ user, initialCluster, initialNamespace }: { user: BackendUser; initialCluster?: string; initialNamespace: string }) {
  const selection = useClusterSelection(initialCluster, true);
  // Remount scope-owned state immediately: no old rows, drafts, or confirmation can survive a cluster change.
  return <ClusterWorkspace key={`${selection.cluster}:${selection.loading}:${selection.error ?? ""}`} user={user} selection={selection} initialNamespace={initialNamespace} />;
}

function ClusterWorkspace({ user, selection, initialNamespace }: {
  user: BackendUser; selection: ReturnType<typeof useClusterSelection>; initialNamespace: string;
}) {
  const router = useRouter();
  const { cluster, clusters, selectCluster } = selection;
  const active = !selection.loading && !selection.error && Boolean(cluster) && clusters.includes(cluster);
  const [resourceType, setResourceType] = useState<ResourceType>("pods");
  const [namespace, setNamespace] = useState(initialNamespace);
  const [namespaces, setNamespaces] = useState<ManagedResource[]>([]);
  const [namespaceLoading, setNamespaceLoading] = useState(true);
  const [namespaceError, setNamespaceError] = useState<ResourceApiError | null>(null);
  const [unexpectedError, setUnexpectedError] = useState<Error | null>(null);
  const namespaceRead = useRef<AbortController | null>(null);
  const loadNamespaces = useCallback(() => {
    if (!active) return Promise.resolve(false);
    namespaceRead.current?.abort();
    const controller = new AbortController();
    namespaceRead.current = controller;
    return managementRequest<{ items: ManagedResource[] }>(managementUrl({ cluster, resourceType: "namespaces", namespace: "" }), { signal: controller.signal }).then((result) => {
      if (controller.signal.aborted) return false;
      setNamespaces(result.items);
      setNamespaceError(null);
      return true;
    }).catch((error: unknown) => {
      if (controller.signal.aborted) return false;
      if (!(error instanceof ResourceApiError)) {
        setUnexpectedError(error instanceof Error ? error : new Error("Unexpected namespace inventory failure"));
        return false;
      }
      setNamespaces([]);
      setNamespaceError(error);
      return false;
    }).finally(() => { if (!controller.signal.aborted) setNamespaceLoading(false); });
  }, [active, cluster]);
  useEffect(() => {
    void loadNamespaces();
    return () => namespaceRead.current?.abort();
  }, [loadNamespaces]);
  function refreshNamespaces() {
    setNamespaceLoading(true);
    return loadNamespaces();
  }
  if (unexpectedError) throw unexpectedError;

  const selectedNamespace = namespaces.find((item) => item.name === namespace);
  const invalidNamespace = resourceType !== "namespaces" && Boolean(namespace) && !namespaceLoading && !namespaceError && !selectedNamespace;
  const namespaceReason = selectedNamespace?.delete_blocked_reason;
  const protectedReason = namespaceReason === "The default namespace cannot be deleted." ? null : namespaceReason;
  const creationBlocked = resourceType === "namespaces" ? null
    : !namespace ? "Select a namespace to create a resource."
      : namespaceLoading ? "Loading namespaces…"
        : namespaceError ? "Refresh namespaces before creating a resource."
          : !selectedNamespace ? "Select an available namespace."
            : selectedNamespace.deletion_timestamp ? "This namespace is terminating."
              : protectedReason;
  const scope = { cluster, resourceType, namespace: resourceType === "namespaces" ? "" : namespace };

  return (
    <DashboardShell user={user} activeResource="manage-resources" activeNamespace={namespace} activeCluster={cluster}
      clusters={clusters} onSelectCluster={selectCluster} namespaceOptions={namespaces.map((item) => item.name)}
      namespaceDisabled={!active || resourceType === "namespaces" || namespaceLoading}
      onNavigate={(resource, nextNamespace) => {
        if (resource === "manage-resources") setNamespace(nextNamespace);
        else router.push(withCluster(`/dashboard?resource=${encodeURIComponent(resource)}&namespace=${encodeURIComponent(nextNamespace)}`, cluster));
      }}>
      <div className="flex min-w-0 flex-col gap-5">
        <div><h1 className="text-2xl font-semibold tracking-tight">Manage resources</h1><p className="mt-1 text-sm text-muted-foreground">Inspect live Kubernetes objects and manage their lifecycle in the selected cluster.</p></div>
        <Tabs.Root defaultValue="kubernetes">
          <Tabs.List className="mb-5 flex border-b border-border" aria-label="Resource management">
            <Tabs.Tab value="kubernetes" className="border-b-2 border-transparent px-3 py-2 text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring data-active:border-primary data-active:text-primary">Kubernetes resources</Tabs.Tab>
          </Tabs.List>
          <Tabs.Panel value="kubernetes" className="flex min-w-0 flex-col gap-4">
            {!active ? <InventoryMessage title={selection.loading ? "Loading clusters…" : selection.error ? "Cluster access unavailable" : !clusters.length ? "No active clusters" : "Selected cluster unavailable"}
              action={!selection.loading ? <><Button variant="outline" onClick={selection.refreshClusters}>Refresh clusters</Button>{user.role === "admin" ? <Button variant="outline" render={<Link href="/settings/clusters" />}>Manage clusters</Button> : null}</> : undefined}>
              {selection.loading ? "Retrieving registered clusters." : selection.error ?? (cluster ? `The selected cluster “${cluster}” is not active. Select an active cluster in the header or check cluster settings.` : "Register or activate a cluster to inspect resources.")}
            </InventoryMessage> : <>
              <div className="flex flex-wrap items-center gap-3">
                <Select value={resourceType} items={RESOURCE_TYPES} onValueChange={(value) => { if (value) setResourceType(value as ResourceType); }}>
                  <SelectTrigger aria-label="Resource type" className="w-52"><SelectValue /></SelectTrigger>
                  <SelectContent><SelectGroup>{RESOURCE_TYPES.map((type) => <SelectItem key={type.value} value={type.value}>{type.label}</SelectItem>)}</SelectGroup></SelectContent>
                </Select>
                <p className="min-w-0 break-words text-sm text-muted-foreground">{scopeLabel(scope)}</p>
              </div>
              {namespaceError ? <div role="alert" className="flex flex-wrap items-center gap-3 rounded-lg border border-border p-3 text-sm"><span>Namespace list: {namespaceError.message}</span><Button variant="outline" size="sm" disabled={namespaceLoading} onClick={() => void refreshNamespaces()}>Refresh namespaces</Button></div> : null}
              {invalidNamespace ? <InventoryMessage title="Namespace unavailable">The namespace “{namespace}” is no longer listed. Select another namespace or All namespaces in the sidebar.</InventoryMessage>
                : <ResourceInventory key={`${resourceType}:${scope.namespace}`} user={user} scope={scope}
                  creationBlocked={creationBlocked ?? null} onNamespacesChanged={refreshNamespaces} />}
            </>}
          </Tabs.Panel>
        </Tabs.Root>
      </div>
    </DashboardShell>
  );
}

function ResourceInventory({ user, scope, creationBlocked, onNamespacesChanged }: {
  user: BackendUser; scope: ResourceScope; creationBlocked: string | null; onNamespacesChanged: () => Promise<boolean>;
}) {
  const [items, setItems] = useState<ManagedResource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ResourceApiError | null>(null);
  const [unexpectedError, setUnexpectedError] = useState<Error | null>(null);
  const [updated, setUpdated] = useState<Date | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ManagedResource | null>(null);
  const createButton = useRef<HTMLButtonElement>(null);
  const deleteButton = useRef<HTMLButtonElement | null>(null);
  const inventory = useRef<HTMLDivElement>(null);
  const read = useRef<AbortController | null>(null);
  const alive = useRef(true);
  const { cluster, resourceType, namespace } = scope;
  const canMutate = user.role === "admin" || user.role === "operator";
  const load = useCallback(() => {
    if (!alive.current) return Promise.resolve(false);
    read.current?.abort();
    const controller = new AbortController();
    read.current = controller;
    return managementRequest<{ items: ManagedResource[] }>(managementUrl({ cluster, resourceType, namespace }), { signal: controller.signal }).then((result) => {
      if (controller.signal.aborted || !alive.current) return false;
      setItems(result.items);
      setError(null);
      setUpdated(new Date());
      return true;
    }).catch((error: unknown) => {
      if (controller.signal.aborted || !alive.current) return false;
      if (!(error instanceof ResourceApiError)) {
        setUnexpectedError(error instanceof Error ? error : new Error("Unexpected resource inventory failure"));
        return false;
      }
      setItems([]);
      setError(error);
      return false;
    }).finally(() => { if (!controller.signal.aborted && alive.current) setLoading(false); });
  }, [cluster, resourceType, namespace]);
  useEffect(() => {
    alive.current = true;
    void load();
    return () => { alive.current = false; read.current?.abort(); };
  }, [load]);
  usePolling(load, !createOpen && !deleteTarget);
  if (unexpectedError) throw unexpectedError;

  async function refresh() {
    if (!alive.current) return false;
    setLoading(true);
    const success = await load();
    if (resourceType === "namespaces" && alive.current) await onNamespacesChanged();
    return success;
  }
  function afterMutation() {
    if (!alive.current) return;
    void refresh();
  }

  const columns: DataTableColumn<ManagedResource>[] = [
    { accessorKey: "name", header: "Name", cell: ({ row }) => <span className="break-all font-medium">{row.original.name}</span> },
    { accessorKey: "kind", header: "Kind" },
    { accessorKey: "namespace", header: "Namespace", cell: ({ row }) => row.original.namespace ?? "Cluster-wide" },
    { accessorKey: "status", header: "Status", cell: ({ row }) => <Badge variant={row.original.health === "error" ? "destructive" : "secondary"}>{row.original.deletion_timestamp ? "Terminating" : row.original.status}</Badge> },
    { id: "protection", header: "Management", cell: ({ row }) => <span className="whitespace-normal text-xs text-muted-foreground">{row.original.delete_blocked_reason ?? (canMutate ? "Manageable" : "Read only")}</span> },
  ];
  if (canMutate) columns.push({ id: "actions", header: "Actions", enableSorting: false, cell: ({ row }) => <Button variant="outline" size="sm"
    disabled={loading || Boolean(row.original.delete_blocked_reason) || Boolean(row.original.deletion_timestamp)}
    aria-label={`Delete ${row.original.kind} ${row.original.name}`}
    onClick={(event) => { deleteButton.current = event.currentTarget; setDeleteTarget(row.original); }}><Trash2 data-icon="inline-start" />Delete</Button> });

  return <div ref={inventory} tabIndex={-1} aria-label="Resource inventory" className="flex min-w-0 flex-col gap-4 outline-none">
    <div className="flex flex-wrap items-center gap-3">
      <Button variant="outline" disabled={loading} onClick={() => void refresh()}><RefreshCw data-icon="inline-start" />{loading ? "Refreshing…" : "Refresh"}</Button>
      {canMutate ? <Button ref={createButton} disabled={loading || Boolean(error) || Boolean(creationBlocked)} onClick={() => setCreateOpen(true)}><Plus data-icon="inline-start" />Create resource</Button> : <Badge variant="secondary">Read only</Badge>}
      <p className="text-xs text-muted-foreground" role="status">{loading ? "Loading live inventory…" : error ? "Inventory refresh failed." : updated ? `Updated ${updated.toLocaleTimeString()} · refreshes every 30 seconds` : ""}</p>
    </div>
    {canMutate && creationBlocked ? <p className="text-sm text-muted-foreground">{creationBlocked}</p> : null}
    {error ? <InventoryMessage title={error.status === 401 ? "Session expired" : error.status === 403 ? "Access denied" : error.status === 404 || error.status === 422 ? "Invalid resource scope" : "Inventory unavailable"}
      action={error.status === 401 ? <Button variant="outline" render={<Link href="/login" />}>Sign in again</Button> : undefined}>{error.message} Use Refresh to check again.</InventoryMessage>
      : loading && !updated ? <InventoryMessage title="Loading resources…">Retrieving live objects from {cluster}.</InventoryMessage>
        : !items.length ? <InventoryMessage title="No resources found">There are no {RESOURCE_TYPES.find((type) => type.value === resourceType)!.label} in this scope.{canMutate ? " Select a namespace and create a resource, or choose another scope." : " Choose another scope or refresh."}</InventoryMessage>
          : <DataTable columns={columns} data={items} searchPlaceholder="Filter resources…" />}
    {createOpen ? <CreateResourceDialog scope={scope} returnFocus={createButton} fallbackFocus={inventory} onClose={() => setCreateOpen(false)} onCreated={afterMutation} onRefresh={refresh} /> : null}
    {deleteTarget ? <DeleteResourceDialog resource={deleteTarget} returnFocus={deleteButton} fallbackFocus={inventory} onClose={() => setDeleteTarget(null)} onDeleted={afterMutation} onRefresh={refresh} /> : null}
  </div>;
}
