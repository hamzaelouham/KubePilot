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
import { apiErrorMessage } from "@/lib/api-error";
import { BackgroundJobDialog } from "@/components/background-job-dialog";

const PAGE_SIZE = 10;

type JobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

type JobAction = "install" | "rollback" | "uninstall" | "upgrade" | "agent_run";

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
  can_manage_release: boolean;
  job_type?: "installation" | "agent_run";
  trigger_type?: string | null;
  owner_id?: string | null;
  result_code?: string | null;
  attempt_count?: number;
};

type PendingAction = {
  kind: ReleaseActionKind;
  target: ReleaseActionTarget;
};

type InstallationResponse = { items: Installation[]; total: number };

type HistoryState =
  | { status: "loading" }
  | { status: "ready"; items: Installation[]; total: number }
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
      return "bg-muted text-muted-foreground";
    case "running":
      return "bg-primary/10 text-primary";
    case "succeeded":
      return "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";
    case "failed":
      return "bg-destructive/10 text-destructive";
    case "cancelled":
      return "bg-amber-500/10 text-amber-700 dark:text-amber-300";
  }
}

function canActOn(job: Installation): boolean {
  return job.action === "install" && job.status === "succeeded" && job.can_manage_release;
}

const tableColumns: DataTableColumn<Installation>[] = [
  {
    accessorKey: "package_name",
    header: "Job",
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
    accessorKey: "action",
    header: "Type",
    cell: ({ row }) => <span className="text-sm capitalize">{row.original.action === "agent_run" ? "Agent run" : row.original.action}</span>,
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
    accessorKey: "result_code",
    header: "Result",
    cell: ({ row }) => <span className="text-sm text-muted-foreground">{row.original.result_code?.replaceAll("_", " ") ?? "—"}</span>,
  },
  {
    accessorKey: "created_at",
    header: "Date",
    cell: ({ row }) => (
      <span className="text-sm">{new Date(row.original.created_at).toLocaleString()}</span>
    ),
  },
];

export function BackgroundJobsTable({ canManage }: { canManage: boolean }) {
  const [state, setState] = useState<HistoryState>({ status: "loading" });
  const [filter, setFilter] = useState<JobStatus | "all">("all");
  const [page, setPage] = useState(0);
  const [pending, setPending] = useState<PendingAction | null>(null);
  const [selectedJob, setSelectedJob] = useState<Installation | null>(null);
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
                  onClick={(event) => {
                    event.stopPropagation();
                    openAction("rollback", job);
                  }}
                >
                  Roll back
                </Button>
                <Button
                  variant="destructive"
                  size="xs"
                  onClick={(event) => {
                    event.stopPropagation();
                    openAction("uninstall", job);
                  }}
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
      const query = new URLSearchParams({
        limit: String(PAGE_SIZE),
        offset: String(page * PAGE_SIZE),
      });
      if (filter !== "all") query.set("status", filter);
      const response = await fetch(`/api/marketplace/installations?${query.toString()}`, {
        signal: controller.signal,
        cache: "no-store",
      });
      const body = (await response.json()) as InstallationResponse;
      if (!response.ok) throw new Error(apiErrorMessage(body, "Unable to load background jobs"));
      setState({ status: "ready", items: body.items, total: body.total });
    } catch (error: unknown) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setState({
        status: "error",
        message: error instanceof Error ? error.message : "Unable to load background jobs",
      });
    }
  }, [filter, page]);

  useEffect(() => {
    abortRef.current?.abort();
    void Promise.resolve().then(load);
    return () => abortRef.current?.abort();
  }, [load]);

  const handleFilter = useCallback((value: JobStatus | "all" | null) => {
    setFilter(value === null ? "all" : value);
    setPage(0);
  }, []);

  const items = state.status === "ready" ? state.items : [];
  const totalPages = state.status === "ready" ? Math.ceil(state.total / PAGE_SIZE) : 0;

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-2">
        <div>
          <p className="text-sm font-medium uppercase tracking-[0.2em] text-muted-foreground">
            Operations
          </p>
          <h2 className="text-xl font-semibold text-foreground">Background jobs</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Track Marketplace, Helm, and read-only AI agent operations across your clusters.
          </p>
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
            Loading background jobs…
          </p>
        ) : state.status === "error" ? (
          <div
            role="alert"
            className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-destructive/40 bg-destructive/10 p-5 text-sm text-destructive"
          >
            <p>{state.message}</p>
            <button
              type="button"
              onClick={() => void load()}
              className="cursor-pointer rounded-lg border border-destructive/40 bg-background px-3 py-2 text-sm font-medium text-destructive transition hover:bg-destructive/10"
            >
              Retry
            </button>
          </div>
        ) : (
          <DataTable
            columns={columns}
            data={items}
            placeholder="No background jobs yet."
            searchPlaceholder="Filter background jobs…"
            pageSize={PAGE_SIZE}
            serverPagination={{ page, totalPages, onPageChange: setPage }}
            onRowClick={setSelectedJob}
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
      <BackgroundJobDialog
        job={selectedJob}
        onOpenChange={(open) => {
          if (!open) setSelectedJob(null);
        }}
      />
    </div>
  );
}

export { type Installation as BackgroundJob };
