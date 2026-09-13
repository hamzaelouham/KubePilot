"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowUpCircle, History, PackageOpen, RefreshCw, RotateCcw, Trash2 } from "lucide-react";
import { DataTable, type DataTableColumn } from "@/components/data-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "@/components/ui/toast";
import type { BackendUser } from "@/lib/auth-client";
import { helmRequest, helmUrl, type HelmReleaseRevision, type HelmReleaseSummary } from "@/lib/helm-releases";
import { helmRepositoryRequest, helmRepositoryUrl, type HelmRepository } from "@/lib/helm-repositories";
import { ResourceApiError } from "@/lib/resource-management";
import { usePolling } from "@/lib/use-polling";

type Action = "rollback" | "uninstall";
type JobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

function InventoryMessage({ title, children, action }: { title: string; children: React.ReactNode; action?: React.ReactNode }) {
  return <Empty className="border border-dashed"><EmptyHeader><EmptyTitle>{title}</EmptyTitle><EmptyDescription>{children}</EmptyDescription></EmptyHeader>{action ? <EmptyContent>{action}</EmptyContent> : null}</Empty>;
}

function statusVariant(status: string | null): "default" | "secondary" | "destructive" | "outline" {
  if (status === "deployed") return "default";
  if (status === "failed" || status === "uninstalling" || status === "pending-upgrade") return "destructive";
  return "secondary";
}

export function HelmReleasesView({ user, cluster, active }: { user: BackendUser; cluster: string; active: boolean }) {
  const [items, setItems] = useState<HelmReleaseSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ResourceApiError | null>(null);
  const [unexpectedError, setUnexpectedError] = useState<string | null>(null);
  const [selected, setSelected] = useState<HelmReleaseSummary | null>(null);
  const [action, setAction] = useState<Action | null>(null);
  const [actionTarget, setActionTarget] = useState<HelmReleaseSummary | null>(null);
  const [upgradeTarget, setUpgradeTarget] = useState<HelmReleaseSummary | null>(null);
  const read = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
    if (!active || !cluster) return false;
    read.current?.abort();
    const controller = new AbortController();
    read.current = controller;
    setLoading(true);
    try {
      const result = await helmRequest<{ items: HelmReleaseSummary[] }>(helmUrl(cluster), { signal: controller.signal });
      if (controller.signal.aborted) return false;
      setItems(result.items);
      setError(null);
      setUnexpectedError(null);
      setSelected((current) => current && result.items.some((item) => item.name === current.name && item.namespace === current.namespace) ? current : null);
      return true;
    } catch (caught: unknown) {
      if (controller.signal.aborted) return false;
      if (caught instanceof ResourceApiError) {
        setError(caught);
        setItems([]);
      } else {
        setUnexpectedError(caught instanceof Error ? caught.message : "Unexpected Helm inventory failure");
      }
      return false;
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, [active, cluster]);

  useEffect(() => {
    void Promise.resolve().then(() => load());
    return () => read.current?.abort();
  }, [cluster, load]);
  const polling = usePolling(load, active && action === null);

  if (!active) return <InventoryMessage title="Cluster unavailable">Select an active registered cluster to inspect live Helm releases.</InventoryMessage>;
  if (error) return <InventoryMessage title={error.status === 401 ? "Session expired" : error.status === 403 ? "Access denied" : error.status === 404 || error.status === 422 ? "Invalid release scope" : "Helm inventory unavailable"} action={<Button variant="outline" onClick={polling.refresh}>Refresh releases</Button>}>{error.message}</InventoryMessage>;
  if (unexpectedError) return <InventoryMessage title="Unexpected inventory error" action={<Button variant="outline" onClick={polling.refresh}>Refresh releases</Button>}>The live release inventory could not be displayed. Try again.</InventoryMessage>;

  const canMutate = user.role === "admin" || user.role === "operator";
  const columns: DataTableColumn<HelmReleaseSummary>[] = [
    { accessorKey: "name", header: "Release", cell: ({ row }) => <span className="break-all font-medium">{row.original.name}</span> },
    { accessorKey: "namespace", header: "Namespace" },
    { accessorKey: "status", header: "Status", cell: ({ row }) => <Badge variant={statusVariant(row.original.status)}>{row.original.status ?? "Unknown"}</Badge> },
    { accessorKey: "revision", header: "Revision", cell: ({ row }) => row.original.revision ?? "—" },
    { accessorKey: "chart", header: "Chart", cell: ({ row }) => <span className="break-all">{row.original.chart ?? "—"}</span> },
    { accessorKey: "updated", header: "Updated", cell: ({ row }) => row.original.updated ? new Date(row.original.updated).toLocaleString() : "—" },
  ];

  return <div className="flex min-w-0 flex-col gap-4">
    <div className="flex flex-wrap items-center gap-3">
      <Button variant="outline" disabled={loading} onClick={polling.refresh}><RefreshCw data-icon="inline-start" />{loading ? "Refreshing…" : "Refresh"}</Button>
      {!canMutate ? <Badge variant="secondary">Read only</Badge> : <p className="text-xs text-muted-foreground">Upgrade preserves deployed values. Rollback targets the previous revision; uninstall removes the release.</p>}
      <p className="text-xs text-muted-foreground" role="status">{loading ? "Loading live releases…" : `${items.length} release${items.length === 1 ? "" : "s"} · all namespaces`}</p>
    </div>
    {loading && !items.length ? <InventoryMessage title="Loading Helm releases…">Reading the live Helm inventory from {cluster}.</InventoryMessage>
      : !items.length ? <InventoryMessage title="No Helm releases found"><PackageOpen className="mx-auto mb-2 size-8 text-muted-foreground" />This cluster has no installed Helm releases.</InventoryMessage>
        : <DataTable columns={columns} data={items} searchPlaceholder="Filter Helm releases…" onRowClick={setSelected} />}
    {selected ? <ReleaseDetails key={`${selected.name}:${selected.namespace}`} release={selected} cluster={cluster} canMutate={canMutate} onClose={() => setSelected(null)} onAction={(next) => { setActionTarget(selected); setSelected(null); setAction(next); }} onUpgrade={() => { setUpgradeTarget(selected); setSelected(null); }} /> : null}
    {action ? <HelmActionDialog action={action} cluster={cluster} release={actionTarget} onClose={() => { setAction(null); setActionTarget(null); }} onResolved={() => { setAction(null); setActionTarget(null); void load(); }} /> : null}
    {upgradeTarget ? <HelmUpgradeDialog cluster={cluster} release={upgradeTarget} onClose={() => setUpgradeTarget(null)} onResolved={() => { setUpgradeTarget(null); void load(); }} /> : null}
  </div>;
}

function ReleaseDetails({ release, cluster, canMutate, onClose, onAction, onUpgrade }: { release: HelmReleaseSummary; cluster: string; canMutate: boolean; onClose: () => void; onAction: (action: Action) => void; onUpgrade: () => void }) {
  const [history, setHistory] = useState<HelmReleaseRevision[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    void helmRequest<{ revisions: HelmReleaseRevision[] }>(helmUrl(cluster, `/${encodeURIComponent(release.name)}/history`, release.namespace), { signal: controller.signal })
      .then((result) => { setHistory(result.revisions); setHistoryError(null); })
      .catch((caught: unknown) => { if (!controller.signal.aborted) setHistoryError(caught instanceof Error ? caught.message : "Unable to load release history"); })
      .finally(() => { if (!controller.signal.aborted) setHistoryLoading(false); });
    return () => controller.abort();
  }, [cluster, release]);
  return <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}><DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-2xl">
    <Link className="text-sm font-medium text-primary hover:underline" href={`/assistant?${new URLSearchParams({ cluster, namespace: release.namespace, release: release.name })}`}>Investigate with AI Assistant</Link>
    <DialogHeader><div className="flex items-start gap-3 pr-6"><span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary"><PackageOpen className="size-5" /></span><div className="min-w-0"><DialogTitle className="truncate">{release.name}</DialogTitle><DialogDescription className="mt-1">{cluster} · {release.namespace}</DialogDescription></div></div></DialogHeader>
    <div className="grid gap-3 rounded-xl border border-border bg-muted/30 p-4 sm:grid-cols-2"><Detail label="Status" value={release.status ?? "Unknown"} /><Detail label="Revision" value={String(release.revision ?? "—")} /><Detail label="Chart" value={release.chart ?? "—"} /><Detail label="App version" value={release.app_version ?? "—"} /><Detail label="Updated" value={release.updated ? new Date(release.updated).toLocaleString() : "—"} /><Detail label="Description" value={release.description ?? "—"} /></div>
    <section><div className="mb-2 flex items-center gap-2"><History className="size-4 text-muted-foreground" /><h3 className="text-sm font-medium">Revision history</h3></div>{historyLoading ? <p className="rounded-xl border border-border p-4 text-sm text-muted-foreground">Loading history…</p> : historyError ? <p role="alert" className="rounded-xl border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">{historyError}</p> : !history.length ? <p className="rounded-xl border border-dashed border-border p-4 text-sm text-muted-foreground">No revision history was returned.</p> : <div className="overflow-x-auto rounded-xl border border-border"><table className="w-full min-w-[44rem] text-left text-sm"><thead className="bg-muted text-muted-foreground"><tr><th className="px-3 py-2">Revision</th><th className="px-3 py-2">Status</th><th className="px-3 py-2">Chart</th><th className="px-3 py-2">Updated</th><th className="px-3 py-2">Description</th></tr></thead><tbody>{history.map((entry) => <tr key={entry.revision} className="border-t border-border"><td className="px-3 py-2 font-medium">{entry.revision}</td><td className="px-3 py-2">{entry.status ?? "—"}</td><td className="px-3 py-2">{entry.chart ?? "—"}</td><td className="px-3 py-2">{entry.updated ? new Date(entry.updated).toLocaleString() : "—"}</td><td className="max-w-xs whitespace-normal px-3 py-2">{entry.description ?? "—"}</td></tr>)}</tbody></table></div>}</section>
    <DialogFooter>{canMutate ? <><Button variant="default" onClick={onUpgrade}><ArrowUpCircle data-icon="inline-start" />Upgrade</Button><Button variant="outline" onClick={() => onAction("rollback")}><RotateCcw data-icon="inline-start" />Roll back</Button><Button variant="destructive" onClick={() => onAction("uninstall")}><Trash2 data-icon="inline-start" />Uninstall</Button></> : null}<Button variant="outline" onClick={onClose}>Close</Button></DialogFooter>
  </DialogContent></Dialog>;
}

function HelmUpgradeDialog({ cluster, release, onClose, onResolved }: { cluster: string; release: HelmReleaseSummary; onClose: () => void; onResolved: () => void }) {
  const [repositories, setRepositories] = useState<HelmRepository[]>([]);
  const [repositoriesLoading, setRepositoriesLoading] = useState(true);
  const [repositoriesError, setRepositoriesError] = useState<string | null>(null);
  const [repositoryId, setRepositoryId] = useState("");
  const [chartName, setChartName] = useState("");
  const [version, setVersion] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [logs, setLogs] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [posting, setPosting] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    void helmRepositoryRequest<{ items: HelmRepository[] }>(helmRepositoryUrl(), { signal: controller.signal })
      .then((result) => { setRepositories(result.items); setRepositoriesError(null); })
      .catch((caught: unknown) => { if (!controller.signal.aborted) setRepositoriesError(caught instanceof Error ? caught.message : "Unable to load Helm repositories."); })
      .finally(() => { if (!controller.signal.aborted) setRepositoriesLoading(false); });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!jobId) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        const [statusResponse, logsResponse] = await Promise.all([
          fetch(`/api/marketplace/installations/${encodeURIComponent(jobId)}`, { signal: controller.signal, cache: "no-store" }),
          fetch(`/api/marketplace/installations/${encodeURIComponent(jobId)}/logs`, { signal: controller.signal, cache: "no-store" }),
        ]);
        const body = await statusResponse.json() as { status?: JobStatus; error_message?: string | null; message?: string };
        const logBody = await logsResponse.json() as { log_output?: string | null };
        if (!statusResponse.ok) throw new Error(body.message ?? "Unable to load job status");
        if (!logsResponse.ok) throw new Error("Unable to load upgrade logs");
        if (!body.status) throw new Error("The backend returned an invalid job status.");
        setStatus(body.status);
        setLogs(logBody.log_output ?? null);
        if (["succeeded", "failed", "cancelled"].includes(body.status)) {
          if (body.status === "succeeded") { toast.add({ type: "success", title: "Upgrade complete", description: `${release.name} finished successfully with its deployed values preserved.` }); onResolved(); }
          else setError(body.error_message ?? "The upgrade operation did not complete.");
          return;
        }
        timer = setTimeout(poll, 2000);
      } catch (caught: unknown) { if (!controller.signal.aborted) setError(caught instanceof Error ? caught.message : "Unable to load upgrade progress"); }
    };
    void poll();
    return () => { controller.abort(); if (timer) clearTimeout(timer); };
  }, [jobId, onResolved, release]);

  const selectedRepository = repositories.find((repository) => repository.id === repositoryId);
  const submit = async () => {
    setPosting(true); setError(null);
    try {
      const response = await helmRequest<{ job_id: string }>(helmUrl(cluster, `/${encodeURIComponent(release.name)}/upgrade`, release.namespace), {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ repository_id: repositoryId, chart_name: chartName, version, confirm_name: confirmation }),
      });
      setJobId(response.job_id); setStatus("queued");
    } catch (caught: unknown) { setError(caught instanceof Error ? caught.message : "Unable to queue the upgrade."); }
    finally { setPosting(false); }
  };
  const pending = jobId !== null;
  const formReady = Boolean(selectedRepository && chartName.trim() && version.trim() && confirmation === release.name);
  return <Dialog open onOpenChange={(open) => { if (!open && !posting) onClose(); }}><DialogContent className="sm:max-w-lg">
    <DialogHeader><DialogTitle>Upgrade release</DialogTitle><DialogDescription>{cluster} · {release.namespace} · {release.name}</DialogDescription></DialogHeader>
    {pending ? <div role="status" className="space-y-3 rounded-xl border border-border bg-muted/30 p-4 text-sm"><div className="flex items-center gap-2"><Badge variant={status === "failed" ? "destructive" : status === "succeeded" ? "default" : "secondary"}>{status ?? "Queued"}</Badge><span>{status === "running" ? "Helm is processing the upgrade." : status === "queued" ? "Waiting for the background worker." : status === "succeeded" ? "The upgrade completed." : "Review the error and close this dialog."}</span></div>{logs ? <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded-lg bg-background p-3 text-xs text-muted-foreground">{logs}</pre> : null}{error ? <p role="alert" className="text-destructive">{error}</p> : null}</div> : <>
      <div className="grid gap-4 rounded-xl border border-border bg-muted/30 p-4">
        <div className="grid gap-2"><label htmlFor="upgrade-repository" className="text-sm font-medium">Repository</label>{repositoriesLoading ? <p className="text-sm text-muted-foreground">Loading global repositories…</p> : repositoriesError ? <p role="alert" className="text-sm text-destructive">{repositoriesError}</p> : !repositories.length ? <p className="text-sm text-muted-foreground">No global repositories are configured. Add one in Manage resources → Repositories.</p> : <Select value={repositoryId || null} onValueChange={(value) => setRepositoryId(value ?? "")}><SelectTrigger id="upgrade-repository" className="w-full"><SelectValue placeholder="Select a repository" /></SelectTrigger><SelectContent><SelectGroup>{repositories.map((repository) => <SelectItem key={repository.id} value={repository.id}>{repository.name} · {repository.url}</SelectItem>)}</SelectGroup></SelectContent></Select>}</div>
        <div className="grid gap-2"><label htmlFor="upgrade-chart" className="text-sm font-medium">Chart name</label><Input id="upgrade-chart" value={chartName} onChange={(event) => setChartName(event.target.value)} placeholder="chart-name" autoComplete="off" /></div>
        <div className="grid gap-2"><label htmlFor="upgrade-version" className="text-sm font-medium">Chart version</label><Input id="upgrade-version" value={version} onChange={(event) => setVersion(event.target.value)} placeholder="1.2.3" autoComplete="off" /></div>
      </div>
      <div className="rounded-xl border border-primary/20 bg-primary/5 p-4 text-sm"><p className="font-medium">Review upgrade</p><p className="mt-1 text-muted-foreground">{selectedRepository?.name ?? "Select a repository"} / {chartName || "chart-name"} · {version || "version"}</p><p className="mt-2 text-muted-foreground">Currently deployed Helm values will be preserved.</p></div>
      <label className="grid gap-2 text-sm font-medium">Type <span className="font-mono">{release.name}</span> to confirm<Input value={confirmation} onChange={(event) => setConfirmation(event.target.value)} placeholder={release.name} autoComplete="off" /></label>
      {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
    </>}
    <DialogFooter>{pending ? <Button onClick={onClose}>Close</Button> : <><Button variant="outline" onClick={onClose} disabled={posting}>Cancel</Button><Button onClick={() => void submit()} disabled={posting || !formReady}>{posting ? "Queueing…" : "Queue upgrade"}</Button></>}</DialogFooter>
  </DialogContent></Dialog>;
}

function HelmActionDialog({ action, cluster, release, onClose, onResolved }: { action: Action; cluster: string; release: HelmReleaseSummary | null; onClose: () => void; onResolved: () => void }) {
  const [confirmation, setConfirmation] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [posting, setPosting] = useState(false);
  useEffect(() => {
    if (!jobId) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        const response = await fetch(`/api/marketplace/installations/${encodeURIComponent(jobId)}`, { signal: controller.signal, cache: "no-store" });
        const body = await response.json() as { status?: JobStatus; error_message?: string | null; message?: string };
        if (!response.ok) throw new Error(body.message ?? "Unable to load job status");
        if (!body.status) throw new Error("The backend returned an invalid job status.");
        setStatus(body.status);
        if (["succeeded", "failed", "cancelled"].includes(body.status)) {
          if (body.status === "succeeded") { toast.add({ type: "success", title: action === "rollback" ? "Rollback complete" : "Release uninstalled", description: `${release?.name ?? "Release"} finished successfully.` }); onResolved(); }
          else setError(body.error_message ?? `The ${action} operation did not complete.`);
          return;
        }
        timer = setTimeout(poll, 2000);
      } catch (caught: unknown) { if (!controller.signal.aborted) setError(caught instanceof Error ? caught.message : "Unable to load job status"); }
    };
    void poll();
    return () => { controller.abort(); if (timer) clearTimeout(timer); };
  }, [action, jobId, onResolved, release]);
  if (!release) return null;
  const submit = async () => {
    setPosting(true); setError(null);
    try {
      const response = await helmRequest<{ job_id: string }>(helmUrl(cluster, `/${encodeURIComponent(release.name)}/${action}`, release.namespace), { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ confirm_name: confirmation }) });
      setJobId(response.job_id); setStatus("queued");
    } catch (caught: unknown) { setError(caught instanceof Error ? caught.message : `Unable to ${action} the release.`); }
    finally { setPosting(false); }
  };
  const pending = jobId !== null;
  return <Dialog open onOpenChange={(open) => { if (!open && !posting) onClose(); }}><DialogContent className="sm:max-w-lg"><DialogHeader><DialogTitle>{action === "rollback" ? "Roll back release" : "Uninstall release"}</DialogTitle><DialogDescription>{cluster} · {release.namespace} · {release.name}</DialogDescription></DialogHeader>{pending ? <div role="status" className="rounded-xl border border-border bg-muted/30 p-4 text-sm"><div className="flex items-center gap-2"><Badge variant={status === "failed" ? "destructive" : status === "succeeded" ? "default" : "secondary"}>{status ?? "Queued"}</Badge><span>{status === "running" ? "Helm is processing the release." : status === "queued" ? "Waiting for the background worker." : status === "succeeded" ? "The operation completed." : "Review the error and close this dialog."}</span></div>{error ? <p role="alert" className="mt-3 text-destructive">{error}</p> : null}</div> : <><p className="text-sm text-muted-foreground">{action === "rollback" ? "Helm will roll this release back to its previous revision." : "Helm will uninstall this release and remove its Kubernetes resources."}</p><label className="grid gap-2 text-sm font-medium">Type <span className="font-mono">{release.name}</span> to confirm<Input value={confirmation} onChange={(event) => setConfirmation(event.target.value)} placeholder={release.name} autoComplete="off" /></label>{error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}</>}<DialogFooter>{pending ? <Button onClick={onClose}>Close</Button> : <><Button variant="outline" onClick={onClose} disabled={posting}>Cancel</Button><Button variant={action === "uninstall" ? "destructive" : "default"} onClick={() => void submit()} disabled={posting || confirmation !== release.name}>{posting ? "Queueing…" : action === "rollback" ? "Roll back" : "Uninstall"}</Button></>}</DialogFooter></DialogContent></Dialog>;
}

function Detail({ label, value }: { label: string; value: string }) { return <div className="min-w-0"><p className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">{label}</p><p className="mt-1 break-words text-sm text-foreground">{value}</p></div>; }
