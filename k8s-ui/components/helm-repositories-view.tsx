"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Field } from "@base-ui/react/field";
import { Pencil, Plus, RefreshCw, Trash2 } from "lucide-react";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DataTable, type DataTableColumn } from "@/components/data-table";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/toast";
import type { BackendUser } from "@/lib/auth-client";
import { helmRepositoryRequest, helmRepositoryUrl, type HelmRepository, type HelmRepositoryApiError } from "@/lib/helm-repositories";

function RepositoryMessage({ title, children }: { title: string; children: React.ReactNode }) {
  return <Empty className="border border-dashed"><EmptyHeader><EmptyTitle>{title}</EmptyTitle><EmptyDescription>{children}</EmptyDescription></EmptyHeader></Empty>;
}

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString();
}

export function HelmRepositoriesView({ user }: { user: BackendUser }) {
  const [repositories, setRepositories] = useState<HelmRepository[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<HelmRepositoryApiError | null>(null);
  const [unexpectedError, setUnexpectedError] = useState<Error | null>(null);
  const [updated, setUpdated] = useState<Date | null>(null);
  const [dialogRepository, setDialogRepository] = useState<HelmRepository | null | undefined>(undefined);
  const [deleteTarget, setDeleteTarget] = useState<HelmRepository | null>(null);
  const [pendingDelete, setPendingDelete] = useState(false);
  const read = useRef<AbortController | null>(null);
  const alive = useRef(true);
  const canMutate = user.role === "admin" || user.role === "operator";

  const load = useCallback(() => {
    read.current?.abort();
    const controller = new AbortController();
    read.current = controller;
    return helmRepositoryRequest<{ items: HelmRepository[] }>(helmRepositoryUrl(), { signal: controller.signal }).then((result) => {
      if (controller.signal.aborted || !alive.current) return false;
      setRepositories(Array.isArray(result.items) ? result.items : []);
      setError(null);
      setUpdated(new Date());
      return true;
    }).catch((reason: unknown) => {
      if (controller.signal.aborted || !alive.current) return false;
      if (!(reason instanceof Error) || !("status" in reason)) {
        setUnexpectedError(reason instanceof Error ? reason : new Error("Unexpected Helm repository response"));
        return false;
      }
      setRepositories([]);
      setError(reason as HelmRepositoryApiError);
      return false;
    }).finally(() => {
      if (!controller.signal.aborted && alive.current) setLoading(false);
    });
  }, []);

  useEffect(() => {
    alive.current = true;
    void load();
    return () => { alive.current = false; read.current?.abort(); };
  }, [load]);

  if (unexpectedError) throw unexpectedError;

  async function refresh() {
    setLoading(true);
    await load();
  }

  const columns: DataTableColumn<HelmRepository>[] = [
    { accessorKey: "name", header: "Name", cell: ({ row }) => <span className="font-medium">{row.original.name}</span> },
    { accessorKey: "url", header: "Repository URL", cell: ({ row }) => <span className="break-all font-mono text-xs text-muted-foreground">{row.original.url}</span> },
    { accessorKey: "updated_at", header: "Last updated", cell: ({ row }) => formatDate(row.original.updated_at) },
  ];
  if (canMutate) {
    columns.push({ id: "actions", header: "Actions", enableSorting: false, cell: ({ row }) => <div className="flex flex-wrap gap-2">
      <Button size="sm" variant="outline" onClick={() => setDialogRepository(row.original)} aria-label={`Edit ${row.original.name}`}><Pencil data-icon="inline-start" />Edit</Button>
      <Button size="sm" variant="outline" onClick={() => setDeleteTarget(row.original)} aria-label={`Delete ${row.original.name}`}><Trash2 data-icon="inline-start" />Delete</Button>
    </div> });
  }

  return <div className="flex min-w-0 flex-col gap-4">
    <div className="flex flex-wrap items-center gap-3">
      <Button variant="outline" disabled={loading} onClick={() => void refresh()}><RefreshCw data-icon="inline-start" />{loading ? "Refreshing…" : "Refresh"}</Button>
      {canMutate ? <Button onClick={() => setDialogRepository(null)}><Plus data-icon="inline-start" />Add repository</Button> : <Badge variant="secondary">Read only</Badge>}
      <p className="text-xs text-muted-foreground" role="status">{loading ? "Loading configured repositories…" : error ? "Repository list refresh failed." : updated ? `Updated ${updated.toLocaleTimeString()}` : ""}</p>
    </div>
    <p className="text-sm text-muted-foreground">Global public chart sources used by KubePilot. Repository settings are shared across clusters.</p>
    {error ? <RepositoryMessage title={error.status === 401 ? "Session expired" : error.status === 403 ? "Access denied" : "Repositories unavailable"}>{error.message} Use Refresh to try again.</RepositoryMessage>
      : loading && !updated ? <RepositoryMessage title="Loading repositories…">Retrieving KubePilot-managed chart sources.</RepositoryMessage>
        : !repositories.length ? <RepositoryMessage title="No repositories configured">Add a public Helm repository to make it available for future release operations.</RepositoryMessage>
          : <DataTable columns={columns} data={repositories} searchPlaceholder="Filter repositories…" />}
    {dialogRepository !== undefined ? <RepositoryDialog repository={dialogRepository} onClose={() => setDialogRepository(undefined)} onSaved={() => { void refresh(); }} /> : null}
    {deleteTarget ? <RepositoryDeleteDialog repository={deleteTarget} pending={pendingDelete} onPending={setPendingDelete} onClose={() => setDeleteTarget(null)} onDeleted={() => { setDeleteTarget(null); void refresh(); }} /> : null}
  </div>;
}

function RepositoryDialog({ repository, onClose, onSaved }: { repository: HelmRepository | null; onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState(repository?.name ?? "");
  const [url, setUrl] = useState(repository?.url ?? "");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<HelmRepositoryApiError | null>(null);
  const [unexpectedError, setUnexpectedError] = useState<Error | null>(null);

  if (unexpectedError) throw unexpectedError;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (pending || !name.trim() || !url.trim()) return;
    setPending(true);
    setError(null);
    try {
      const result = await helmRepositoryRequest<HelmRepository>(helmRepositoryUrl(repository?.id), {
        method: repository ? "PATCH" : "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ name, url }),
      });
      toast.add({ type: "success", title: repository ? "Repository updated" : "Repository added", description: `${result.name} is ready for future Helm operations.` });
      onSaved();
      onClose();
    } catch (reason: unknown) {
      if (!(reason instanceof Error) || !("status" in reason)) {
        setUnexpectedError(reason instanceof Error ? reason : new Error("Unexpected Helm repository save failure"));
        return;
      }
      const apiError = reason as HelmRepositoryApiError;
      toast.add({ type: "error", title: repository ? "Repository update failed" : "Repository creation failed", description: apiError.message });
      setError(apiError);
    } finally {
      setPending(false);
    }
  }

  return <Dialog open onOpenChange={(open) => { if (!open && !pending) onClose(); }}>
    <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg" showCloseButton={!pending}>
      <DialogHeader><DialogTitle>{repository ? "Edit repository" : "Add repository"}</DialogTitle><DialogDescription>{repository ? `Update ${repository.name}'s public Helm chart source.` : "Connect a public Helm chart repository for KubePilot operations."}</DialogDescription></DialogHeader>
      <form onSubmit={submit} aria-busy={pending} className="flex min-w-0 flex-col gap-5">
        <Field.Root name="name" disabled={pending} invalid={Boolean(error)} className="flex min-w-0 flex-col gap-2"><Field.Label className="text-sm font-medium" htmlFor="repository-name">Repository name</Field.Label><Input id="repository-name" value={name} onChange={(event) => { setName(event.target.value); setError(null); }} placeholder="bitnami" autoCapitalize="none" autoComplete="off" /><Field.Description className="text-xs text-muted-foreground">Use lowercase letters, numbers, and hyphens.</Field.Description></Field.Root>
        <Field.Root name="url" disabled={pending} invalid={Boolean(error)} className="flex min-w-0 flex-col gap-2"><Field.Label className="text-sm font-medium" htmlFor="repository-url">Public repository URL</Field.Label><Input id="repository-url" type="url" value={url} onChange={(event) => { setUrl(event.target.value); setError(null); }} placeholder="https://charts.example.com/stable" autoComplete="url" /><Field.Description className="text-xs text-muted-foreground">HTTP(S) only. Credentials and query parameters are not supported.</Field.Description>{error ? <Field.Description role="alert" className="text-sm text-destructive">{error.message}</Field.Description> : null}</Field.Root>
        <DialogFooter><Button type="button" variant="outline" onClick={onClose} disabled={pending}>Cancel</Button><Button type="submit" disabled={pending || !name.trim() || !url.trim()}>{pending ? "Saving…" : repository ? "Save changes" : "Add repository"}</Button></DialogFooter>
      </form>
    </DialogContent>
  </Dialog>;
}

function RepositoryDeleteDialog({ repository, pending, onPending, onClose, onDeleted }: { repository: HelmRepository; pending: boolean; onPending: (value: boolean) => void; onClose: () => void; onDeleted: () => void }) {
  const [error, setError] = useState<HelmRepositoryApiError | null>(null);
  const [unexpectedError, setUnexpectedError] = useState<Error | null>(null);

  if (unexpectedError) throw unexpectedError;

  async function remove() {
    if (pending) return;
    onPending(true);
    try {
      await helmRepositoryRequest(helmRepositoryUrl(repository.id), { method: "DELETE" });
      toast.add({ type: "success", title: "Repository removed", description: repository.name });
      onDeleted();
    } catch (reason: unknown) {
      if (!(reason instanceof Error) || !("status" in reason)) {
        setUnexpectedError(reason instanceof Error ? reason : new Error("Unexpected Helm repository removal failure"));
        return;
      }
      const apiError = reason as HelmRepositoryApiError;
      setError(apiError);
      toast.add({ type: "error", title: "Repository removal failed", description: apiError.message });
    } finally {
      onPending(false);
    }
  }

  return <AlertDialog open onOpenChange={(open) => { if (!open && !pending) onClose(); }}><AlertDialogContent className="sm:max-w-lg"><AlertDialogHeader><AlertDialogTitle>Remove {repository.name}?</AlertDialogTitle><AlertDialogDescription>This removes the global public Helm repository configuration from KubePilot. It does not change any installed releases.{error ? <span role="alert" className="mt-2 block text-destructive">{error.message}</span> : null}</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel disabled={pending}>Cancel</AlertDialogCancel><AlertDialogAction variant="destructive" disabled={pending} onClick={() => void remove()}>{pending ? "Removing…" : "Remove repository"}</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>;
}
