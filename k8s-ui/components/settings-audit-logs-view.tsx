"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { CircleAlert, Clock, Loader2, RefreshCw, ShieldCheck, X } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  AuditLogRequestError,
  auditLogCategories,
  auditLogResults,
  fetchAuditLogs,
  type AuditLog,
  type AuditLogCategory,
  type AuditLogFilters,
  type AuditLogResult,
  type AuditLogsResponse,
} from "@/lib/settings-audit-logs";

const pageSize = 20;
const allValue = "all";

type FilterForm = {
  category: AuditLogCategory | typeof allValue;
  result: AuditLogResult | typeof allValue;
  actor: string;
  resourceType: string;
  action: string;
  dateFrom: string;
  dateTo: string;
};

type LoadState =
  | { kind: "loading" }
  | { kind: "ready"; data: AuditLogsResponse }
  | { kind: "denied"; message: string }
  | { kind: "invalid"; message: string }
  | { kind: "unavailable"; message: string }
  | { kind: "error"; message: string };

const initialFilters: FilterForm = {
  category: allValue,
  result: allValue,
  actor: "",
  resourceType: "",
  action: "",
  dateFrom: "",
  dateTo: "",
};

function toApiFilters(filters: FilterForm, page: number): AuditLogFilters {
  return {
    page,
    limit: pageSize,
    category: filters.category === allValue ? undefined : filters.category,
    result: filters.result === allValue ? undefined : filters.result,
    actor: filters.actor || undefined,
    resource_type: filters.resourceType || undefined,
    action: filters.action || undefined,
    date_from: filters.dateFrom ? new Date(filters.dateFrom).toISOString() : undefined,
    date_to: filters.dateTo ? new Date(filters.dateTo).toISOString() : undefined,
  };
}

function errorState(error: unknown): LoadState {
  if (error instanceof AuditLogRequestError) {
    if (error.status === 403) return { kind: "denied", message: error.message };
    if (error.status === 422 || error.code === "validation_error") return { kind: "invalid", message: error.message };
    if (error.status === 503 || error.code === "backend_unavailable") return { kind: "unavailable", message: error.message };
    return { kind: "error", message: error.message };
  }
  return { kind: "error", message: "The audit logs could not be loaded." };
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function resultVariant(result: string): "default" | "secondary" | "destructive" | "outline" {
  if (result === "success" || result === "succeeded") return "default";
  if (result === "failure" || result === "failed") return "destructive";
  if (result === "requested" || result === "pending") return "secondary";
  return "outline";
}

function categoryLabel(category: AuditLogCategory) {
  return category === "ai" ? "AI" : category[0].toUpperCase() + category.slice(1);
}

function contextText(value: unknown) {
  if (value === null || value === undefined) return "No context";
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}

function Filters({
  filters,
  loading,
  onChange,
  onClear,
  onRefresh,
}: {
  filters: FilterForm;
  loading: boolean;
  onChange: (changes: Partial<FilterForm>) => void;
  onClear: () => void;
  onRefresh: () => void;
}) {
  const hasFilters = Object.entries(filters).some(([key, value]) => key === "category" || key === "result" ? value !== allValue : Boolean(value));
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle>Audit Logs</CardTitle>
            <CardDescription className="mt-1 max-w-3xl">
              Review administrative, resource, Helm, provider/model, and AI activity recorded by KubePilot.
            </CardDescription>
          </div>
          <Button type="button" variant="outline" onClick={onRefresh} disabled={loading}>
            {loading ? <Loader2 className="animate-spin" data-icon="inline-start" /> : <RefreshCw data-icon="inline-start" />}
            Refresh
          </Button>
        </div>
      </CardHeader>
      <CardContent className="grid gap-4 lg:grid-cols-4">
        <label className="flex flex-col gap-2 text-sm font-medium" htmlFor="audit-category">
          Category
          <Select value={filters.category} onValueChange={(value) => onChange({ category: value as FilterForm["category"] })}>
            <SelectTrigger id="audit-category" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectItem value={allValue}>All categories</SelectItem>
                {auditLogCategories.map((category) => (
                  <SelectItem key={category} value={category}>{categoryLabel(category)}</SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
        </label>

        <label className="flex flex-col gap-2 text-sm font-medium" htmlFor="audit-result">
          Result
          <Select value={filters.result} onValueChange={(value) => onChange({ result: value as FilterForm["result"] })}>
            <SelectTrigger id="audit-result" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectItem value={allValue}>All results</SelectItem>
                {auditLogResults.map((result) => (
                  <SelectItem key={result} value={result}>{result}</SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
        </label>

        <label className="flex flex-col gap-2 text-sm font-medium" htmlFor="audit-actor">
          Actor
          <Input id="audit-actor" value={filters.actor} onChange={(event) => onChange({ actor: event.target.value })} maxLength={255} placeholder="admin@example.com" />
        </label>

        <label className="flex flex-col gap-2 text-sm font-medium" htmlFor="audit-resource-type">
          Resource type
          <Input id="audit-resource-type" value={filters.resourceType} onChange={(event) => onChange({ resourceType: event.target.value })} maxLength={128} placeholder="pod, cluster, assistant_tool" />
        </label>

        <label className="flex flex-col gap-2 text-sm font-medium lg:col-span-2" htmlFor="audit-action">
          Action
          <Input id="audit-action" value={filters.action} onChange={(event) => onChange({ action: event.target.value })} maxLength={128} placeholder="settings.update, helm.release_upgrade" />
        </label>

        <label className="flex flex-col gap-2 text-sm font-medium" htmlFor="audit-date-from">
          From
          <Input id="audit-date-from" type="datetime-local" value={filters.dateFrom} onChange={(event) => onChange({ dateFrom: event.target.value })} />
        </label>

        <label className="flex flex-col gap-2 text-sm font-medium" htmlFor="audit-date-to">
          To
          <Input id="audit-date-to" type="datetime-local" value={filters.dateTo} onChange={(event) => onChange({ dateTo: event.target.value })} />
        </label>

        {hasFilters ? (
          <div className="lg:col-span-4">
            <Button type="button" variant="ghost" onClick={onClear}>
              <X data-icon="inline-start" />
              Clear filters
            </Button>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function LoadingTable() {
  return (
    <Card aria-busy="true" aria-label="Loading audit logs">
      <CardContent className="space-y-3 pt-6">
        {["one", "two", "three", "four"].map((item) => (
          <Skeleton key={item} className="h-12 w-full" />
        ))}
      </CardContent>
    </Card>
  );
}

function ErrorState({ state, onRetry }: { state: Exclude<LoadState, { kind: "loading" } | { kind: "ready" }>; onRetry: () => void }) {
  const title = state.kind === "denied"
    ? "Audit logs are restricted"
    : state.kind === "invalid"
      ? "Filters need attention"
      : state.kind === "unavailable"
        ? "Audit log service unavailable"
        : "Audit logs could not be loaded";
  return (
    <Alert variant={state.kind === "denied" || state.kind === "invalid" ? "default" : "destructive"} role="alert">
      <CircleAlert />
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
        <span>{state.message}</span>
        <Button type="button" variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw data-icon="inline-start" />
          Retry
        </Button>
      </AlertDescription>
    </Alert>
  );
}

function EmptyLogs() {
  return (
    <Card>
      <CardContent className="py-10">
        <Empty>
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <ShieldCheck />
            </EmptyMedia>
            <EmptyTitle>No audit logs found</EmptyTitle>
            <EmptyDescription>No records match the current filters.</EmptyDescription>
          </EmptyHeader>
          <EmptyContent />
        </Empty>
      </CardContent>
    </Card>
  );
}

function AuditRows({ logs }: { logs: AuditLog[] }) {
  return (
    <Card>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Time</TableHead>
            <TableHead>Category</TableHead>
            <TableHead>Actor</TableHead>
            <TableHead>Action</TableHead>
            <TableHead>Resource</TableHead>
            <TableHead>Result</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {logs.map((log) => (
            <TableRow key={log.id} className="align-top">
              <TableCell className="min-w-44 whitespace-normal">
                <div className="flex items-start gap-2 text-sm">
                  <Clock className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                  <span>{formatDate(log.created_at)}</span>
                </div>
              </TableCell>
              <TableCell>
                <Badge variant="outline">{categoryLabel(log.category)}</Badge>
              </TableCell>
              <TableCell className="max-w-56 whitespace-normal break-words text-sm">
                {log.actor?.email ?? "System"}
              </TableCell>
              <TableCell className="max-w-64 whitespace-normal break-words">
                <div className="font-medium">{log.action}</div>
                {log.target_user ? <div className="text-xs text-muted-foreground">Target: {log.target_user.email}</div> : null}
                <details className="mt-2 text-xs text-muted-foreground">
                  <summary className="cursor-pointer text-foreground">Context</summary>
                  <pre className="mt-2 max-w-[32rem] overflow-x-auto whitespace-pre-wrap break-words rounded-md bg-muted p-3 font-mono text-xs leading-5 text-muted-foreground">
                    {contextText(log.context)}
                  </pre>
                </details>
              </TableCell>
              <TableCell className="max-w-72 whitespace-normal break-words text-sm">
                <div>{log.resource_type}</div>
                <div className="text-xs text-muted-foreground">{log.resource_id}</div>
              </TableCell>
              <TableCell>
                <Badge variant={resultVariant(log.result)}>{log.result || "unknown"}</Badge>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}

export function SettingsAuditLogsView() {
  const [filters, setFilters] = useState<FilterForm>(initialFilters);
  const [page, setPage] = useState(0);
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  const apiFilters = useMemo(() => toApiFilters(filters, page), [filters, page]);

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      setState({ kind: "ready", data: await fetchAuditLogs(apiFilters) });
    } catch (error) {
      setState(errorState(error));
    }
  }, [apiFilters]);

  useEffect(() => {
    void load();
  }, [load]);

  function updateFilters(changes: Partial<FilterForm>) {
    setPage(0);
    setFilters((current) => ({ ...current, ...changes }));
  }

  const loading = state.kind === "loading";
  const ready = state.kind === "ready" ? state.data : null;
  const canGoBack = Boolean(ready && ready.page > 0);
  const canGoForward = Boolean(ready && ready.page + 1 < ready.total_pages);

  return (
    <div className="space-y-6">
      <Filters
        filters={filters}
        loading={loading}
        onChange={updateFilters}
        onClear={() => {
          setPage(0);
          setFilters(initialFilters);
        }}
        onRefresh={() => void load()}
      />

      {loading ? <LoadingTable /> : null}
      {state.kind !== "loading" && state.kind !== "ready" ? <ErrorState state={state} onRetry={() => void load()} /> : null}
      {ready && ready.logs.length === 0 ? <EmptyLogs /> : null}
      {ready && ready.logs.length > 0 ? (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
            <span>Showing {ready.logs.length} of {ready.total} audit records</span>
            <span>Page {ready.page + 1} of {ready.total_pages}</span>
          </div>
          <AuditRows logs={ready.logs} />
          <div className="flex items-center justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setPage((current) => Math.max(0, current - 1))} disabled={!canGoBack || loading}>
              Previous
            </Button>
            <Button type="button" variant="outline" onClick={() => setPage((current) => current + 1)} disabled={!canGoForward || loading}>
              Next
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
