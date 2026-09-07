"use client";

import { useEffect, useState } from "react";
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

function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString();
}

function statusBadge(status: string) {
  if (status === "active") return <Badge variant="secondary">Active</Badge>;
  if (status === "inactive") return <Badge variant="destructive">Inactive</Badge>;
  return <Badge variant="outline">{status}</Badge>;
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

export function ClustersManagement({ canManage }: { canManage: boolean }) {
  const [clusters, setClusters] = useState<ManagedCluster[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [toggleId, setToggleId] = useState<string | null>(null);

  const [createOpen, setCreateOpen] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createKubeconfig, setCreateKubeconfig] = useState("");

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
    })();
    return () => {
      mounted = false;
    };
  }, []);

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
              <TableHead>Name</TableHead>
              <TableHead>Endpoint</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Created</TableHead>
              {canManage ? <TableHead className="text-right">Actions</TableHead> : null}
            </TableRow>
          </TableHeader>
          <TableBody>
            {clusters.map((cluster) => (
              <TableRow key={cluster.id}>
                <TableCell>
                  <span className="font-medium">{cluster.name}</span>
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">{cluster.endpoint}</TableCell>
                <TableCell>{statusBadge(cluster.status)}</TableCell>
                <TableCell className="text-sm text-muted-foreground">{formatDateTime(cluster.created_at)}</TableCell>
                {canManage ? (
                  <TableCell className="text-right">
                    <Button
                      size="sm"
                      variant={cluster.status === "active" ? "destructive" : "secondary"}
                      onClick={() => void doToggle(cluster)}
                      disabled={toggleId === cluster.id || pending !== null}
                    >
                      {cluster.status === "active" ? "Deactivate" : "Reactivate"}
                    </Button>
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

      {pending ? <p className="text-sm text-muted-foreground">Working…</p> : null}
    </div>
  );
}