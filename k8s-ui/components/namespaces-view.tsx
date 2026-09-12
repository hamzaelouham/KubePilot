"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { formatLastUpdated, usePolling } from "@/lib/use-polling";
import { useCluster } from "@/lib/cluster-context";
import { withCluster } from "@/lib/cluster-query";
import { DataTable, type DataTableColumn } from "@/components/data-table";
import { Button } from "@/components/ui/button";

type Namespace = { name: string; status: string };
type NamespaceResponse = { items: Namespace[] };
type NamespaceState =
  | { status: "loading" }
  | { status: "ready"; items: Namespace[] }
  | { status: "error"; message: string };

const tableColumns: DataTableColumn<Namespace>[] = [
  {
    accessorKey: "name",
    header: "Name",
    cell: ({ row }) => <span className="font-medium">{row.original.name}</span>,
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => <span>{row.original.status}</span>,
  },
];

export function NamespacesView() {
  const [state, setState] = useState<NamespaceState>({ status: "loading" });
  const abortRef = useRef<AbortController | null>(null);
  const cluster = useCluster();

  const load = useCallback(async () => {
    const controller = new AbortController();
    abortRef.current?.abort();
    abortRef.current = controller;
    try {
      const response = await fetch(withCluster("/api/cluster/namespaces", cluster), { signal: controller.signal, cache: "no-store" });
      const body = (await response.json()) as NamespaceResponse & { message?: string };
      if (!response.ok) throw new Error(body.message ?? "Unable to load namespaces");
      setState({ status: "ready", items: body.items });
    } catch (error: unknown) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setState({ status: "error", message: error instanceof Error ? error.message : "Unable to load namespaces" });
    }
  }, [cluster]);

  useEffect(() => {
    abortRef.current?.abort();
    void Promise.resolve().then(load);
    return () => abortRef.current?.abort();
  }, [load]);

  const { refresh, lastUpdated } = usePolling(load);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-2">
        <div>
          <p className="text-sm font-medium uppercase tracking-[0.16em] text-muted-foreground">Live cluster data</p>
          <h2 className="text-2xl font-semibold tracking-tight text-foreground">Namespaces</h2>
        </div>
        <div className="flex items-center gap-3">
          <Button type="button" variant="outline" onClick={refresh}>Refresh</Button>
          <span className="text-sm text-muted-foreground">Updated {formatLastUpdated(lastUpdated)}</span>
        </div>
      </div>

      {state.status === "loading" ? <p className="rounded-lg border border-border bg-muted p-5 text-sm text-muted-foreground">Loading namespaces…</p> : null}
      {state.status === "error" ? <p role="alert" className="rounded-lg border border-destructive/40 bg-destructive/10 p-5 text-sm text-destructive">{state.message}</p> : null}
      {state.status === "ready" && state.items.length === 0 ? <p className="rounded-lg border border-border bg-muted p-5 text-sm text-muted-foreground">No namespaces found.</p> : null}
      {state.status === "ready" && state.items.length > 0 ? (
        <DataTable
          columns={tableColumns}
          data={state.items}
          placeholder="No namespaces found."
          searchPlaceholder="Filter namespaces…"
        />
      ) : null}
    </div>
  );
}
