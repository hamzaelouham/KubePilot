"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DataTable, type DataTableColumn } from "@/components/data-table";
import {
  ReleaseActionDialog,
  type ReleaseActionKind,
  type ReleaseActionTarget,
} from "@/components/release-action-dialog";

type JobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

type JobAction = "install" | "rollback" | "uninstall";

type Installation = {
  job_id: string;
  package_name: string;
  cluster: string;
  namespace: string;
  release_name: string;
  action: JobAction;
  status: JobStatus;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
};

type PendingAction = {
  kind: ReleaseActionKind;
  target: ReleaseActionTarget;
};

type InstallationResponse = { items: Installation[]; total: number };

type HistoryState =
  | { status: "loading" }
  | { status: "ready"; items: Installation[] }
  | { status: "error"; message: string };

const STATUS_FILTERS: { value: JobStatus | "all"; label: string }[] = [
  { value: "all", label: "All statuses" },
  { value: "queued", label: "Queued" },
  { value: "running", label: "Running" },
  { value: "succeeded", label: "Succeeded" },
  { value: "failed", label: "Failed" },
  { value: "cancelled", label: "Cancelled" },
];

function statusTone(status: JobStatus): string {
  switch (status) {
    case "queued":
      return "bg-slate-200 text-slate-600";
    case "running":
      return "bg-cyan-100 text-cyan-700";
    case "succeeded":
      return "bg-green-100 text-green-700";
    case "failed":
      return "bg-red-100 text-red-700";
    case "cancelled":
      return "bg-amber-100 text-amber-700";
  }
}

function canActOn(job: Installation): boolean {
  return job.action === "install" && job.status === "succeeded";
}

const tableColumns: DataTableColumn<Installation>[] = [
  {
    accessorKey: "package_name",
    header: "Package",
    cell: ({ row }) => <span className="text-sm font-medium">{row.original.package_name}</span>,
  },
  {
    accessorKey: "cluster",
    header: "Cluster",
    cell: ({ row }) => <span className="text-sm">{row.original.cluster}</span>,
  },
  {
    accessorKey: "namespace",
    header: "Namespace",
    cell: ({ row }) => <span className="text-sm">{row.original.namespace}</span>,
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => (
      <Badge variant="outline" className={statusTone(row.original.status)}>
        {row.original.status}
      </Badge>
    ),
  },
  {
    accessorKey: "created_at",
    header: "Date",
    cell: ({ row }) => (
      <span className="text-sm">{new Date(row.original.created_at).toLocaleString()}</span>
    ),
  },
];

export function MarketplaceHistory({ canManage }: { canManage: boolean }) {
  const [state, setState] = useState<HistoryState>({ status: "loading" });
  const [filter, setFilter] = useState<JobStatus | "all">("all");
  const [pending, setPending] = useState<PendingAction | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const openAction = useCallback(
    (kind: ReleaseActionKind, job: Installation) => {
      setPending({
        kind,
        target: {
          job_id: job.job_id,
          package_name: job.package_name,
          cluster: job.cluster,
          namespace: job.namespace,
          release_name: job.release_name,
        },
      });
    },
    [],
  );

  const columns: DataTableColumn<Installation>[] = canManage
    ? [
        ...tableColumns,
        {
          id: "actions",
          header: "Actions",
          cell: ({ row }) => {
            const job = row.original;
            if (!canActOn(job)) return <span />;
            return (
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="xs"
                  onClick={() => openAction("rollback", job)}
                >
                  Roll back
                </Button>
                <Button
                  variant="destructive"
                  size="xs"
                  onClick={() => openAction("uninstall", job)}
                >
                  Uninstall
                </Button>
              </div>
            );
          },
        },
      ]
    : tableColumns;

  const load = useCallback(async () => {
    const controller = new AbortController();
    abortRef.current?.abort();
    abortRef.current = controller;
    setState({ status: "loading" });
    try {
      const response = await fetch("/api/marketplace/installations", {
        signal: controller.signal,
        cache: "no-store",
      });
      const body = (await response.json()) as InstallationResponse & { message?: string };
      if (!response.ok) throw new Error(body.message ?? "Unable to load installation history");
      setState({ status: "ready", items: body.items });
    } catch (error: unknown) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setState({
        status: "error",
        message: error instanceof Error ? error.message : "Unable to load installation history",
      });
    }
  }, []);

  useEffect(() => {
    abortRef.current?.abort();
    void Promise.resolve().then(load);
    return () => abortRef.current?.abort();
  }, [load]);

  const handleFilter = useCallback((value: JobStatus | "all" | null) => {
    setFilter(value === null ? "all" : value);
  }, []);

  const items = state.status === "ready" ? state.items : [];
  const visibleItems =
    filter === "all" ? items : items.filter((item) => item.status === filter);

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-2">
        <div>
          <p className="text-sm font-medium uppercase tracking-[0.2em] text-muted-foreground">
            Marketplace
          </p>
          <h2 className="text-xl font-semibold text-foreground">Installation history</h2>
        </div>
        <div className="flex items-center gap-3">
          <Select value={filter} onValueChange={handleFilter}>
            <SelectTrigger aria-label="Filter installations by status" className="w-48">
              <SelectValue />
            </SelectTrigger>
            <SelectContent align="end">
              {STATUS_FILTERS.map(({ value, label }) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <button
            type="button"
            onClick={() => void load()}
            className="cursor-pointer rounded-xl border border-border bg-card px-3 py-2 text-sm font-medium text-foreground transition hover:bg-muted"
          >
            Refresh
          </button>
        </div>
      </div>

      <div className="mt-4">
        {state.status === "loading" ? (
          <p className="rounded-lg bg-muted p-5 text-sm text-muted-foreground">
            Loading installation history…
          </p>
        ) : state.status === "error" ? (
          <div
            role="alert"
            className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-red-200 bg-red-50 p-5 text-sm text-red-700"
          >
            <p>{state.message}</p>
            <button
              type="button"
              onClick={() => void load()}
              className="cursor-pointer rounded-xl border border-red-200 bg-white px-3 py-2 text-sm font-medium text-red-700 transition hover:bg-red-100"
            >
              Retry
            </button>
          </div>
        ) : (
          <DataTable
            columns={columns}
            data={visibleItems}
            placeholder="No installations yet."
            searchPlaceholder="Filter installations…"
          />
        )}
      </div>

      {pending && (
        <ReleaseActionDialog
          kind={pending.kind}
          target={pending.target}
          onClose={() => setPending(null)}
          onResolved={() => void load()}
        />
      )}
    </div>
  );
}