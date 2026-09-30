"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, CircleAlert, Clock3, LoaderCircle, TerminalSquare } from "lucide-react";
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
import { apiErrorMessage } from "@/lib/api-error";
import type { BackgroundJob } from "@/components/marketplace-history";

type JobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

function statusTone(status: JobStatus) {
  switch (status) {
    case "succeeded":
      return "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";
    case "failed":
      return "bg-destructive/10 text-destructive";
    case "running":
      return "bg-primary/10 text-primary";
    case "cancelled":
      return "bg-amber-500/10 text-amber-700 dark:text-amber-300";
    default:
      return "bg-muted text-muted-foreground";
  }
}

function StatusIcon({ status }: { status: JobStatus }) {
  if (status === "running") return <LoaderCircle className="size-4 animate-spin" />;
  if (status === "succeeded") return <CheckCircle2 className="size-4" />;
  if (status === "failed") return <CircleAlert className="size-4" />;
  return <Clock3 className="size-4" />;
}

export function BackgroundJobDialog({
  job,
  onOpenChange,
}: {
  job: BackgroundJob | null;
  onOpenChange: (open: boolean) => void;
}) {
  const [logState, setLogState] = useState<
    { status: "idle" } | { status: "loading" } | { status: "ready"; output: string | null } | { status: "error"; message: string }
  >({ status: "idle" });

  useEffect(() => {
    if (!job) return;
    const controller = new AbortController();
    void Promise.resolve().then(async () => {
      if (controller.signal.aborted) return;
      setLogState({ status: "loading" });
      try {
        const response = await fetch(`/api/marketplace/installations/${encodeURIComponent(job.job_id)}/logs`, {
          signal: controller.signal,
          cache: "no-store",
        });
        const body = (await response.json()) as { log_output?: string | null; code?: string; message?: string };
        if (!response.ok) throw new Error(apiErrorMessage(body, "Unable to load job logs"));
        setLogState({ status: "ready", output: body.log_output ?? null });
      } catch (error: unknown) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setLogState({
          status: "error",
          message: error instanceof Error ? error.message : "Unable to load job logs",
        });
      }
    });
    return () => controller.abort();
  }, [job]);

  return (
    <Dialog open={job !== null} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-2xl">
        {job ? (
          <>
            <DialogHeader>
              <div className="flex items-start gap-3 pr-6">
                <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                  <TerminalSquare className="size-5" />
                </span>
                <div className="min-w-0">
                  <DialogTitle className="truncate">{job.package_name}</DialogTitle>
                  <DialogDescription className="mt-1">
                    {job.action === "agent_run" ? `${job.trigger_type === "kubernetes_event" ? "Kubernetes event" : "Scheduled"} agent run` : `${job.action} operation for release ${job.release_name}`}
                  </DialogDescription>
                </div>
              </div>
            </DialogHeader>

            <div className="grid gap-3 rounded-xl border border-border bg-muted/30 p-4 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <p className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">Status</p>
                <Badge variant="outline" className={`mt-1 gap-1.5 capitalize ${statusTone(job.status)}`}>
                  <StatusIcon status={job.status} />
                  {job.status}
                </Badge>
              </div>
              <Detail label="Cluster" value={job.cluster} />
              <Detail label="Namespace" value={job.namespace} />
              {job.action === "agent_run" ? <><Detail label="Trigger" value={job.trigger_type === "kubernetes_event" ? "Kubernetes event" : "Schedule"} /><Detail label="Result" value={job.result_code?.replaceAll("_", " ") ?? "Pending"} /><Detail label="Attempt" value={String(job.attempt_count ?? 0)} /></> : <Detail label="Release" value={job.release_name} />}
              <Detail label="Created" value={formatDate(job.created_at)} />
              <Detail label="Started" value={formatDate(job.started_at)} />
              <Detail label="Completed" value={formatDate(job.completed_at)} />
              <div className="sm:col-span-2">
                <p className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">Job ID</p>
                <p className="mt-1 break-all font-mono text-xs text-foreground">{job.job_id}</p>
              </div>
            </div>

            {job.error_message ? (
              <div className="rounded-xl border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
                <p className="font-medium">Operation error</p>
                <p className="mt-1 whitespace-pre-wrap">{job.error_message}</p>
              </div>
            ) : null}

            <section>
              <div className="mb-2 flex items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-medium text-foreground">Execution logs</h3>
                  <p className="text-xs text-muted-foreground">Captured from the backend worker.</p>
                </div>
                {logState.status === "loading" ? <LoaderCircle className="size-4 animate-spin text-muted-foreground" /> : null}
              </div>
              {logState.status === "loading" ? (
                <div className="rounded-xl border border-border bg-muted/30 p-5 text-sm text-muted-foreground">Loading logs…</div>
              ) : logState.status === "error" ? (
                <div role="alert" className="rounded-xl border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">{logState.message}</div>
              ) : logState.status === "ready" && logState.output ? (
                <pre className="max-h-72 overflow-auto rounded-xl border border-border bg-slate-950 p-4 font-mono text-xs leading-5 text-slate-100">{logState.output}</pre>
              ) : (
                <div className="rounded-xl border border-dashed border-border bg-muted/20 p-5 text-sm text-muted-foreground">No backend logs have been recorded for this job.</div>
              )}
            </section>

            <DialogFooter>
              <Button variant="outline" onClick={() => onOpenChange(false)}>Close</Button>
            </DialogFooter>
          </>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <p className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">{label}</p>
      <p className="mt-1 truncate text-sm text-foreground">{value}</p>
    </div>
  );
}

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleString() : "Not started";
}
