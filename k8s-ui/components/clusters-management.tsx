"use client";

import { useCallback, useEffect, useState } from "react";
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
    <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-200">{children}</div>
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
        window.location.href = "/login";
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
  }, [refreshHealth]);

  const extractError = async (response: Response): Promise<string | null> => {
    if (response.status === 401) {
      window.location.href = "/login";
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

  const refresh = async (): Promise<void> => {
    const result = await fetchClusters();
    if (result === "unauthorized") {
      window.location.href = "/login";
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
        window.location.href = "/login";
        return;
      }
      if (response.status === 503) {
        setError("The cluster management service is currently unavailable.");
        return;
      }
      if (!response.ok) {
        const failure = await extractError(response);
        if (failure) setError(failure);
        return;
      }
      setCreateOpen(false);
      setCreateName("");
      setCreateKubeconfig("");
      await refresh();
    } catch {
      setError("An unexpected error occurred.");
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
        window.location.href = "/login";
        return;
      }
      if (response.status === 503) {
        setError("The cluster management service is currently unavailable.");
        return;
      }
      if (!response.ok) {
        const failure = await extractError(response);
        if (failure) setError(failure);
        return;
      }
      await refresh();
    } catch {
      setError("An unexpected error occurred.");
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
        window.location.href = "/login";
        return;
      }
      if (response.status === 503) {
        setError("The cluster management service is currently unavailable.");
        return;
      }
      if (!response.ok) {
        const failure = await extractError(response);
        if (failure) setError(failure);
        return;
      }
      setEditTarget(null);
      setEditName("");
      setEditKubeconfig("");
      await refresh();
    } catch {
      setError("An unexpected error occurred.");
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
        window.location.href = "/login";
        return;
      }
      if (response.status === 503) {
        setError("The cluster management service is currently unavailable.");
        return;
      }
      if (!response.ok) {
        const failure = await extractError(response);
        if (failure) setError(failure);
        return;
      }
      setDeleteTarget(null);
      await refresh();
    } catch {
      setError("An unexpected error occurred.");
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
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New cluster</DialogTitle>
            <DialogDescription>
              Register a cluster with a name and its kubeconfig. The cluster becomes available to the cluster selector
              immediately.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium" htmlFor="create-cluster-name">Name</label>
              <Input
                id="create-cluster-name"
                type="text"
                value={createName}
                onChange={(event) => setCreateName(event.target.value)}
                placeholder="staging"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium" htmlFor="create-cluster-kubeconfig">kubeconfig</label>
              <textarea
                id="create-cluster-kubeconfig"
                value={createKubeconfig}
                onChange={(event) => setCreateKubeconfig(event.target.value)}
                rows={10}
                spellCheck={false}
                placeholder="Paste the contents of the cluster's kubeconfig file"
                className="w-full rounded-lg border border-input bg-transparent px-2.5 py-1.5 font-mono text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
              />
            </div>
          </div>
          <DialogFooter>
            <div className="flex w-full justify-end gap-2">
              <Button variant="outline" onClick={() => setCreateOpen(false)} disabled={pending === "create"}>
                Cancel
              </Button>
              <Button onClick={() => void doCreate()} disabled={!createName.trim() || !createKubeconfig.trim()}>
                Register cluster
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={editTarget !== null} onOpenChange={(open) => { if (!open) setEditTarget(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit cluster</DialogTitle>
            <DialogDescription>
              Rename the cluster or replace its kubeconfig to change the endpoint.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium" htmlFor="edit-cluster-name">Name</label>
              <Input
                id="edit-cluster-name"
                type="text"
                value={editName}
                onChange={(event) => setEditName(event.target.value)}
                placeholder="staging"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium" htmlFor="edit-cluster-kubeconfig">kubeconfig (optional)</label>
              <textarea
                id="edit-cluster-kubeconfig"
                value={editKubeconfig}
                onChange={(event) => setEditKubeconfig(event.target.value)}
                rows={10}
                spellCheck={false}
                placeholder="Paste a new kubeconfig to change the endpoint; leave empty to keep it"
                className="w-full rounded-lg border border-input bg-transparent px-2.5 py-1.5 font-mono text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
              />
            </div>
            <p className="text-xs text-muted-foreground">Current endpoint: {editTarget?.endpoint ?? "—"}</p>
          </div>
          <DialogFooter>
            <div className="flex w-full justify-end gap-2">
              <Button variant="outline" onClick={() => setEditTarget(null)} disabled={pending === "edit"}>
                Cancel
              </Button>
              <Button onClick={() => void doEdit()} disabled={!editName.trim() || pending === "edit"}>
                Save changes
              </Button>
            </div>
          </DialogFooter>
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
