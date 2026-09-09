"use client";

import { useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "@/components/ui/toast";

export type ReleaseActionKind = "rollback" | "uninstall";

export type ReleaseActionTarget = {
  job_id: string;
  package_name: string;
  cluster: string;
  namespace: string;
  release_name: string;
};

type JobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

const POLL_MS = 2000;

const TERMINAL_JOB_STAGES: ReadonlySet<string> = new Set([
  "succeeded",
  "failed",
  "cancelled",
]);

const JOB_STAGE_LABELS: Record<JobStatus, string> = {
  queued: "Queued",
  running: "Running",
  succeeded: "Succeeded",
  failed: "Failed",
  cancelled: "Cancelled",
};

const JOB_STAGE_VARIANTS: Record<
  JobStatus,
  "secondary" | "default" | "destructive" | "outline"
> = {
  queued: "secondary",
  running: "secondary",
  succeeded: "default",
  failed: "destructive",
  cancelled: "outline",
};

type JobPollState =
  | { phase: "status"; stage: JobStatus; message: string | null }
  | { phase: "error"; message: string };

function isJobStatus(value: string): value is JobStatus {
  return (
    value === "queued" ||
    value === "running" ||
    value === "succeeded" ||
    value === "failed" ||
    value === "cancelled"
  );
}

function Spinner() {
  return (
    <svg
      className="size-4 animate-spin text-muted-foreground"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
      />
    </svg>
  );
}

function JobProgress({
  jobId,
  kind,
  target,
  onClose,
  onResolved,
}: {
  jobId: string;
  kind: ReleaseActionKind;
  target: ReleaseActionTarget;
  onClose: () => void;
  onResolved: () => void;
}) {
  const [poll, setPoll] = useState<JobPollState>({
    phase: "status",
    stage: "queued",
    message: null,
  });
  const [attempt, setAttempt] = useState(0);
  const reportedRef = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    let timer: number | undefined;

    const pollOnce = async () => {
      try {
        const response = await fetch(
          `/api/marketplace/installations/${encodeURIComponent(jobId)}`,
          { signal: controller.signal, cache: "no-store" },
        );
        const body = (await response.json()) as {
          status?: string;
          error_message?: string | null;
          message?: string;
        };
        if (!response.ok) throw new Error(body.message || "Unable to load job status");
        const stage = body.status ?? "";
        if (isJobStatus(stage)) {
          setPoll({ phase: "status", stage, message: body.error_message ?? null });
          if (TERMINAL_JOB_STAGES.has(stage)) {
            if (!reportedRef.current) {
              reportedRef.current = true;
              onResolved();
              if (stage === "succeeded") {
                toast.add({
                  title: kind === "rollback" ? "Rollback complete" : "Release uninstalled",
                  description:
                    kind === "rollback"
                      ? `${target.release_name} was rolled back successfully.`
                      : `${target.release_name} was uninstalled successfully.`,
                  type: "success",
                });
                onClose();
              }
            }
          } else {
            timer = window.setTimeout(pollOnce, POLL_MS);
          }
        } else {
          setPoll((previous) =>
            previous.phase === "status"
              ? previous
              : { phase: "status", stage: "running", message: null },
          );
          timer = window.setTimeout(pollOnce, POLL_MS);
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setPoll({
          phase: "error",
          message: error instanceof Error ? error.message : "Unable to load job status",
        });
      }
    };

    void pollOnce();
    return () => {
      controller.abort();
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [attempt, jobId, kind, onClose, onResolved, target.release_name]);

  const stage = poll.phase === "status" ? poll.stage : undefined;
  const terminal = stage !== undefined && TERMINAL_JOB_STAGES.has(stage);
  const loadingSentence =
    stage === "queued"
      ? kind === "rollback"
        ? "Rollback queued. Waiting for the background worker to start it."
        : "Uninstall queued. Waiting for the background worker to start it."
      : stage === "running"
        ? kind === "rollback"
          ? "Helm is rolling the release back."
          : "Helm is uninstalling the release."
        : null;

  return (
    <>
      <div className="grid gap-4">
        <div className="rounded-xl border border-border bg-surface-elevated p-4 shadow-sm">
          <p className="truncate text-sm font-medium text-foreground">{target.package_name}</p>
          <p className="mt-1 truncate text-sm text-muted-foreground">
            {target.cluster} · {target.namespace} · release {target.release_name}
          </p>
        </div>
        <div role="status" aria-live="polite" className="flex items-center gap-2">
          {stage !== undefined && !terminal && <Spinner />}
          {stage !== undefined && (
            <Badge variant={JOB_STAGE_VARIANTS[stage]}>{JOB_STAGE_LABELS[stage]}</Badge>
          )}
        </div>
        <p className="text-sm text-muted-foreground">
          {loadingSentence}
          {stage === "succeeded" &&
            (kind === "rollback"
              ? "Rollback succeeded. You can close this dialog."
              : "The release was uninstalled. You can close this dialog.")}
          {stage === "failed" &&
            (poll.phase === "status"
              ? kind === "rollback"
                ? "The rollback failed."
                : "The uninstall failed."
              : kind === "rollback"
                ? "The rollback failed without an error message."
                : "The uninstall failed without an error message.")}
          {stage === "cancelled" && "The action was cancelled."}
        </p>
        {stage === "failed" && poll.phase === "status" && poll.message && (
          <div
            role="alert"
            className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
          >
            {poll.message}
          </div>
        )}
        {poll.phase === "error" && (
          <div
            role="alert"
            className="flex items-center justify-between gap-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
          >
            <span>{poll.message}</span>
            <Button variant="outline" size="xs" onClick={() => setAttempt((current) => current + 1)}>
              Retry
            </Button>
          </div>
        )}
      </div>
      <DialogFooter>
        <Button type="button" onClick={onClose}>
          Close
        </Button>
      </DialogFooter>
    </>
  );
}

export function ReleaseActionDialog({
  kind,
  target,
  onClose,
  onResolved,
}: {
  kind: ReleaseActionKind;
  target: ReleaseActionTarget;
  onClose: () => void;
  onResolved: () => void;
}) {
  const [queuedJobId, setQueuedJobId] = useState<string | null>(null);
  const [posting, setPosting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const destructive = kind === "uninstall";

  const submit = () => {
    setPosting(true);
    setActionError(null);
    fetch(`/api/marketplace/installations/${encodeURIComponent(target.job_id)}/${kind}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: "{}",
      cache: "no-store",
    })
      .then(async (response) => {
        const body = (await response.json()) as { job_id?: string; message?: string };
        if (!response.ok) throw new Error(body.message || `Unable to ${kind} the release`);
        setQueuedJobId(body.job_id ?? null);
      })
      .catch((error) => {
        setActionError(
          error instanceof Error ? error.message : `Unable to ${kind} the release`,
        );
      })
      .finally(() => setPosting(false));
  };

  const handleClose = () => {
    if (posting) return;
    onClose();
  };

  return (
    <Dialog open onOpenChange={(open) => {
      if (!open) handleClose();
    }}>
      <DialogContent className="sm:max-w-lg">
        {queuedJobId ? (
          <JobProgress
            jobId={queuedJobId}
            kind={kind}
            target={target}
            onClose={onClose}
            onResolved={onResolved}
          />
        ) : (
          <>
            <DialogHeader>
              <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {destructive ? "Uninstall release" : "Roll back release"}
              </span>
              <DialogTitle className="truncate">{target.package_name}</DialogTitle>
              <p className="text-sm text-muted-foreground">
                {target.cluster} · {target.namespace} · release {target.release_name}
              </p>
            </DialogHeader>
            {actionError && (
              <div
                role="alert"
                className="flex items-center justify-between gap-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
              >
                <span>{actionError}</span>
              </div>
            )}
            <p className="text-sm text-muted-foreground">
              {destructive
                ? "This uninstalls the Helm release and removes its Kubernetes resources. This cannot be undone."
                : "This rolls the release back to the previous revision."}
            </p>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose} disabled={posting}>
                Cancel
              </Button>
              <Button
                type="button"
                variant={destructive ? "destructive" : "default"}
                onClick={submit}
                disabled={posting}
              >
                {posting ? "Submitting…" : destructive ? "Uninstall" : "Roll back"}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
