"use client";

import { useCallback, useEffect, useState } from "react";
import { Field } from "@base-ui/react/field";
import { useRouter } from "next/navigation";
import { CalendarDays, Link, Server, Wifi } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/toast";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export type ManagedCluster = {
  id: string;
  name: string;
  endpoint: string;
  status: string;
  created_at: string;
};

export type ClusterConnectionStatus = "connected" | "unavailable" | "forbidden" | "inactive" | "checking";

function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString();
}

function isLocal(cluster: ManagedCluster) {
  return cluster.endpoint === "in-cluster";
}

function statusBadge(cluster: ManagedCluster, connectionStatus?: ClusterConnectionStatus) {
  if (cluster.status === "inactive" || connectionStatus === "inactive") {
    return (
      <Badge variant="destructive" className="gap-1.5">
        <span aria-hidden="true" className="size-1.5 rounded-full bg-current opacity-70" />
        Inactive
      </Badge>
    );
  }
  if (!connectionStatus || connectionStatus === "checking") {
    return <Badge variant="outline">Checking…</Badge>;
  }
  if (connectionStatus === "connected") {
    return (
      <Badge variant="secondary" className="gap-1.5">
        <span aria-hidden="true" className="size-1.5 rounded-full bg-emerald-500" />
        Connected
      </Badge>
    );
  }
  if (connectionStatus === "forbidden") {
    return (
      <Badge variant="destructive" className="gap-1.5">
        <span aria-hidden="true" className="size-1.5 rounded-full bg-current opacity-70" />
        Access denied
      </Badge>
    );
  }
  return <Badge variant="destructive">Unavailable</Badge>;
}

function ClusterManagementCallout({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">{children}</div>
  );
}

async function fetchClusters(): Promise<{ items: ManagedCluster[] } | "unauthorized" | "unavailable" | "error"> {
  const response = await fetch("/api/clusters", { cache: "no-store" });
  if (response.status === 401) return "unauthorized";
  if (response.status === 503) return "unavailable";
  if (!response.ok) return "error";
  return (await response.json()) as { items: ManagedCluster[] };
}

export function ClustersManagement({ canManage, canDelete }: { canManage: boolean; canDelete?: boolean }) {
  const router = useRouter();
  const [clusters, setClusters] = useState<ManagedCluster[]>([]);
  const [healthByCluster, setHealthByCluster] = useState<Record<string, ClusterConnectionStatus>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [toggleId, setToggleId] = useState<string | null>(null);

  const [createOpen, setCreateOpen] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createKubeconfig, setCreateKubeconfig] = useState("");

  const [editTarget, setEditTarget] = useState<ManagedCluster | null>(null);
  const [editName, setEditName] = useState("");
  const [editKubeconfig, setEditKubeconfig] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<ManagedCluster | null>(null);

  const refreshHealth = useCallback(async (items: ManagedCluster[]) => {
    if (items.length === 0) {
      setHealthByCluster({});
      return;
    }
    const results = await Promise.all(
      items.map(async (cluster) => {
        let status: ClusterConnectionStatus = "unavailable";
        try {
          const response = await fetch(`/api/clusters/${cluster.id}/health`, { cache: "no-store" });
          if (response.ok) {
            const body = (await response.json()) as { connection_status?: ClusterConnectionStatus };
            status = body.connection_status ?? "unavailable";
          }
        } catch {
          // Health check is best-effort; the badge stays on the last known state.
        }
        return [cluster.id, status] as const;
      }),
    );
    setHealthByCluster(Object.fromEntries(results));
  }, []);

  useEffect(() => {
    let mounted = true;
    void (async () => {
      const result = await fetchClusters();
      if (!mounted) return;
      if (result === "unauthorized") {
        router.push("/login");
        return;
      }
      if (result === "unavailable") {
        setClusters([]);
        setError("The cluster management service is currently unavailable.");
        setLoading(false);
        return;
      }
      if (result === "error") {
        setClusters([]);
        setError("Could not load clusters.");
        setLoading(false);
        return;
      }
      setClusters(result.items);
      setError(null);
      setLoading(false);
      void refreshHealth(result.items);
    })();
    return () => {
      mounted = false;
    };
  }, [refreshHealth, router]);

  const extractError = async (response: Response): Promise<string | null> => {
    if (response.status === 401) {
      router.push("/login");
      return null;
    }
    if (response.status === 503 || response.status === 0) {
      return "The cluster management service is currently unavailable.";
    }
    try {
      const body = (await response.json()) as { message?: string };
      return body.message ?? "The operation could not be completed.";
    } catch {
      return "The operation could not be completed.";
    }
  };

  const showOperationError = (message: string) => {
    setError(message);
    toast.add({ type: "error", title: "Cluster operation failed", description: message });
  };

  const refresh = async (): Promise<void> => {
    const result = await fetchClusters();
    if (result === "unauthorized") {
      router.push("/login");
      return;
    }
    if (result === "unavailable") {
      setError("Could not refresh the cluster list.");
      return;
    }
    if (result === "error") {
      setError("Could not refresh the cluster list.");
      return;
    }
    setClusters(result.items);
    void refreshHealth(result.items);
  };

  const doCreate = async () => {
    setPending("create");
    setError(null);
    try {
      const response = await fetch("/api/clusters", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ name: createName, kubeconfig_content: createKubeconfig }),
        cache: "no-store",
      });
      if (response.status === 401) {
        router.push("/login");
        return;
      }
      if (response.status === 503) {
        showOperationError("The cluster management service is currently unavailable.");
        return;
      }
      if (!response.ok) {
        const failure = await extractError(response);
        if (failure) showOperationError(failure);
        return;
      }
      toast.add({ type: "success", title: "Cluster registered", description: `${createName} is now available.` });
      setCreateOpen(false);
      setCreateName("");
      setCreateKubeconfig("");
      await refresh();
    } catch {
      showOperationError("An unexpected error occurred.");
    } finally {
      setPending(null);
    }
  };

  const doToggle = async (cluster: ManagedCluster) => {
    setToggleId(cluster.id);
    setError(null);
    try {
      const response = await fetch(`/api/clusters/${cluster.id}`, {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ status: cluster.status === "active" ? "inactive" : "active" }),
        cache: "no-store",
      });
      if (response.status === 401) {
        router.push("/login");
        return;
      }
      if (response.status === 503) {
        showOperationError("The cluster management service is currently unavailable.");
        return;
      }
      if (!response.ok) {
        const failure = await extractError(response);
        if (failure) showOperationError(failure);
        return;
      }
      const nextStatus = cluster.status === "active" ? "deactivated" : "reactivated";
      toast.add({ type: "success", title: `Cluster ${nextStatus}`, description: cluster.name });
      await refresh();
    } catch {
      showOperationError("An unexpected error occurred.");
    } finally {
      setToggleId(null);
    }
  };

  const openEdit = (cluster: ManagedCluster) => {
    setEditTarget(cluster);
    setEditName(cluster.name);
    setEditKubeconfig("");
    setError(null);
  };

  const doEdit = async () => {
    if (!editTarget) return;
    setPending("edit");
    setError(null);
    try {
      const payload: { name: string; kubeconfig_content?: string } = { name: editName };
      if (editKubeconfig.trim()) payload.kubeconfig_content = editKubeconfig;
      const response = await fetch(`/api/clusters/${editTarget.id}`, {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
        cache: "no-store",
      });
      if (response.status === 401) {
        router.push("/login");
        return;
      }
      if (response.status === 503) {
        showOperationError("The cluster management service is currently unavailable.");
        return;
      }
      if (!response.ok) {
        const failure = await extractError(response);
        if (failure) showOperationError(failure);
        return;
      }
      toast.add({ type: "success", title: "Cluster updated", description: `${editName} was saved.` });
      setEditTarget(null);
      setEditName("");
      setEditKubeconfig("");
      await refresh();
    } catch {
      showOperationError("An unexpected error occurred.");
    } finally {
      setPending(null);
    }
  };

  const doDelete = async () => {
    if (!deleteTarget) return;
    setPending("delete");
    setError(null);
    try {
      const response = await fetch(`/api/clusters/${deleteTarget.id}`, { method: "DELETE", cache: "no-store" });
      if (response.status === 401) {
        router.push("/login");
        return;
      }
      if (response.status === 503) {
        showOperationError("The cluster management service is currently unavailable.");
        return;
      }
      if (!response.ok) {
        const failure = await extractError(response);
        if (failure) showOperationError(failure);
        return;
      }
      toast.add({ type: "success", title: "Cluster deleted", description: deleteTarget.name });
      setDeleteTarget(null);
      await refresh();
    } catch {
      showOperationError("An unexpected error occurred.");
    } finally {
      setPending(null);
    }
  };

  if (loading && clusters.length === 0) {
    return <p className="py-10 text-center text-sm text-muted-foreground">Loading clusters…</p>;
  }

  return (
    <div className="space-y-4">
      {error ? <ClusterManagementCallout>{error}</ClusterManagementCallout> : null}

      {canManage ? (
        <div className="flex items-center justify-end gap-2">
          <Button onClick={() => setCreateOpen(true)} disabled={pending !== null}>
            create cluster
          </Button>
        </div>
      ) : null}

      <div className="rounded-md border border-border bg-surface-elevated p-2 shadow-sm">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Cluster name</TableHead>
              <TableHead>Endpoint</TableHead>
              <TableHead>Connection</TableHead>
              <TableHead>Created</TableHead>
              {canManage ? <TableHead className="text-right">Actions</TableHead> : null}
            </TableRow>
          </TableHeader>
          <TableBody>
            {clusters.map((cluster) => (
              <TableRow key={cluster.id}>
                <TableCell>
                  <div className="flex items-center gap-2.5">
                    <div className="flex size-8 shrink-0 items-center justify-center rounded-md border border-border bg-muted/40 text-muted-foreground">
                      <Server aria-hidden="true" className="size-4" />
                    </div>
                    <div className="min-w-0">
                      <span className="block font-medium text-foreground">{cluster.name}</span>
                      <span className="block text-xs text-muted-foreground">Cluster</span>
                    </div>
                  </div>
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Link aria-hidden="true" className="size-3.5 shrink-0" />
                    <span className="max-w-60 truncate" title={cluster.endpoint}>{cluster.endpoint}</span>
                  </div>
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <Wifi aria-hidden="true" className="size-3.5 text-muted-foreground" />
                    {statusBadge(cluster, healthByCluster[cluster.id])}
                  </div>
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <CalendarDays aria-hidden="true" className="size-3.5 shrink-0" />
                    <span>{formatDateTime(cluster.created_at)}</span>
                  </div>
                </TableCell>
                {canManage ? (
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => openEdit(cluster)}
                        disabled={toggleId === cluster.id || pending !== null}
                      >
                        Edit
                      </Button>
                      <Button
                        size="sm"
                        variant={cluster.status === "active" ? "destructive" : "secondary"}
                        onClick={() => void doToggle(cluster)}
                        disabled={toggleId === cluster.id || pending !== null}
                      >
                        {cluster.status === "active" ? "Deactivate" : "Reactivate"}
                      </Button>
                      {canDelete ? (
                        isLocal(cluster) ? (
                          <span className="text-xs text-muted-foreground">Local</span>
                        ) : (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => setDeleteTarget(cluster)}
                            disabled={toggleId === cluster.id || pending !== null}
                          >
                            Delete
                          </Button>
                        )
                      ) : null}
                    </div>
                  </TableCell>
                ) : null}
              </TableRow>
            ))}
            {clusters.length === 0 ? (
              <TableRow>
                <TableCell colSpan={canManage ? 5 : 4} className="py-10 text-center text-sm text-muted-foreground">
                  No clusters yet.
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </div>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-2xl" showCloseButton={pending !== "create"}>
          <DialogHeader>
            <DialogTitle>New cluster</DialogTitle>
            <DialogDescription>
              Register a cluster with a name and its kubeconfig. The cluster becomes available to the cluster selector
              immediately.
            </DialogDescription>
          </DialogHeader>
          <form className="flex min-w-0 flex-col gap-5" onSubmit={(event) => { event.preventDefault(); void doCreate(); }}>
            <Field.Root name="cluster-name" className="flex min-w-0 flex-col gap-2">
              <Field.Label className="text-sm font-medium" htmlFor="create-cluster-name">Name</Field.Label>
              <Input
                id="create-cluster-name"
                type="text"
                value={createName}
                onChange={(event) => setCreateName(event.target.value)}
                placeholder="staging"
              />
            </Field.Root>
            <Field.Root name="kubeconfig" className="flex min-w-0 flex-col gap-2">
              <Field.Label className="text-sm font-medium" htmlFor="create-cluster-kubeconfig">Kubeconfig</Field.Label>
              <Field.Description className="text-sm text-muted-foreground">Paste the kubeconfig used to connect to this cluster.</Field.Description>
              <textarea
                id="create-cluster-kubeconfig"
                value={createKubeconfig}
                onChange={(event) => setCreateKubeconfig(event.target.value)}
                rows={10}
                spellCheck={false}
                placeholder="Paste the contents of the cluster's kubeconfig file"
                className="min-h-64 w-full resize-y rounded-lg border border-input bg-background px-3 py-2 font-mono text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/50"
              />
            </Field.Root>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setCreateOpen(false)} disabled={pending === "create"}>Cancel</Button>
              <Button type="submit" disabled={!createName.trim() || !createKubeconfig.trim() || pending === "create"}>
                {pending === "create" ? "Registering…" : "Register cluster"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={editTarget !== null} onOpenChange={(open) => { if (!open && pending !== "edit") setEditTarget(null); }}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-2xl" showCloseButton={pending !== "edit"}>
          <DialogHeader>
            <DialogTitle>Edit cluster</DialogTitle>
            <DialogDescription>
              Rename the cluster or replace its kubeconfig to change the endpoint.
            </DialogDescription>
          </DialogHeader>
          <form className="flex min-w-0 flex-col gap-5" onSubmit={(event) => { event.preventDefault(); void doEdit(); }}>
            <Field.Root name="cluster-name" className="flex min-w-0 flex-col gap-2">
              <Field.Label className="text-sm font-medium" htmlFor="edit-cluster-name">Name</Field.Label>
              <Input
                id="edit-cluster-name"
                type="text"
                value={editName}
                onChange={(event) => setEditName(event.target.value)}
                placeholder="staging"
              />
            </Field.Root>
            <Field.Root name="kubeconfig" className="flex min-w-0 flex-col gap-2">
              <Field.Label className="text-sm font-medium" htmlFor="edit-cluster-kubeconfig">Kubeconfig (optional)</Field.Label>
              <Field.Description className="text-sm text-muted-foreground">Leave this empty to keep the current connection.</Field.Description>
              <textarea
                id="edit-cluster-kubeconfig"
                value={editKubeconfig}
                onChange={(event) => setEditKubeconfig(event.target.value)}
                rows={10}
                spellCheck={false}
                placeholder="Paste a new kubeconfig to change the endpoint; leave empty to keep it"
                className="min-h-64 w-full resize-y rounded-lg border border-input bg-background px-3 py-2 font-mono text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/50"
              />
            </Field.Root>
            <p className="text-xs text-muted-foreground">Current endpoint: {editTarget?.endpoint ?? "—"}</p>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setEditTarget(null)} disabled={pending === "edit"}>Cancel</Button>
              <Button type="submit" disabled={!editName.trim() || pending === "edit"}>{pending === "edit" ? "Saving…" : "Save changes"}</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <AlertDialog open={deleteTarget !== null} onOpenChange={(open) => { if (!open) setDeleteTarget(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete cluster</AlertDialogTitle>
            <AlertDialogDescription>
              Delete {deleteTarget?.name ?? "this cluster"} and all namespaces, workloads, and other data
              registered under it. This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={pending === "delete"}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => void doDelete()}>Delete cluster</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {pending ? <p className="text-sm text-muted-foreground">Working…</p> : null}
    </div>
  );
}
