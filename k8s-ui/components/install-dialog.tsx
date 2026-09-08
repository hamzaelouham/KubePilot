"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useClusterSelection } from "@/lib/use-cluster-selection";
import { withCluster } from "@/lib/cluster-query";
import { publisherOf, type MarketplacePackage } from "@/components/package-card";

type VersionsState =
  | { status: "loading" }
  | { status: "ready"; versions: string[]; selected: string }
  | { status: "error"; message: string }
  | { status: "empty" };

type NamespacesState =
  | { status: "loading" }
  | { status: "ready"; names: string[]; selected: string }
  | { status: "error"; message: string }
  | { status: "empty" };

const RELEASE_NAME_PATTERN = /^[a-z0-9]([-a-z0-9]*[a-z0-9])?$/;
const MAX_RELEASE_NAME_LENGTH = 63;
const POLL_MS = 2000;

type JobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

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
  packageName,
  cluster,
  namespace,
  release,
  onClose,
}: {
  jobId: string;
  packageName: string;
  cluster: string;
  namespace: string;
  release: string;
  onClose: () => void;
}) {
  const [poll, setPoll] = useState<JobPollState>({
    phase: "status",
    stage: "queued",
    message: null,
  });
  const [attempt, setAttempt] = useState(0);

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
        if (!response.ok) throw new Error(body.message || "Unable to load installation status");
        const stage = body.status ?? "";
        if (isJobStatus(stage)) {
          setPoll({ phase: "status", stage, message: body.error_message ?? null });
          if (!TERMINAL_JOB_STAGES.has(stage)) {
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
          message: error instanceof Error ? error.message : "Unable to load installation status",
        });
      }
    };

    void pollOnce();
    return () => {
      controller.abort();
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [jobId, attempt]);

  const stage = poll.phase === "status" ? poll.stage : undefined;
  const terminal = stage !== undefined && TERMINAL_JOB_STAGES.has(stage);
  const loadingSentence =
    stage === "queued"
      ? "Installation queued. Waiting for the background worker to start it."
      : stage === "running"
        ? "Helm is installing the package."
        : null;

  return (
    <>
      <div className="grid gap-4">
        <div className="rounded-xl border border-border bg-surface-elevated p-4 shadow-sm">
          <p className="truncate text-sm font-medium text-foreground">{packageName}</p>
          <p className="mt-1 truncate text-sm text-muted-foreground">
            {cluster} · {namespace} · release {release}
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
          {stage === "succeeded" && "Installation succeeded. You can close this dialog."}
          {stage === "failed" &&
            (poll.phase === "status"
              ? "The installation failed."
              : "The installation failed without an error message.")}
          {stage === "cancelled" && "Installation cancelled."}
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

export function InstallDialog({
  pkg,
  onOpenChange,
}: {
  pkg: MarketplacePackage | null;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={pkg !== null} onOpenChange={onOpenChange}>
      {pkg && (
        <DialogContent className="sm:max-w-lg">
          <InstallDialogBody
            key={pkg.package_id}
            pkg={pkg}
            onClose={() => onOpenChange(false)}
          />
        </DialogContent>
      )}
    </Dialog>
  );
}

function InstallDialogBody({
  pkg,
  onClose,
}: {
  pkg: MarketplacePackage;
  onClose: () => void;
}) {
  const { cluster, clusters, selectCluster } = useClusterSelection();
  const [versions, setVersions] = useState<VersionsState>({ status: "loading" });
  const [versionRetry, setVersionRetry] = useState(0);
  const [namespaces, setNamespaces] = useState<NamespacesState>({ status: "loading" });
  const [namespaceRetry, setNamespaceRetry] = useState(0);
  const [release, setRelease] = useState("");
  const [posting, setPosting] = useState(false);
  const [installError, setInstallError] = useState<string | null>(null);
  const [queuedJobId, setQueuedJobId] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const repository = pkg.repository?.name;

    if (!repository) {
      void Promise.resolve().then(() =>
        setVersions({ status: "error", message: "Unable to determine the package repository." }),
      );
      return () => controller.abort();
    }

    fetch(
      `/api/marketplace/packages/${encodeURIComponent(repository)}/${encodeURIComponent(pkg.name)}/versions`,
      { signal: controller.signal, cache: "no-store" },
    )
      .then(async (response) => {
        if (!response.ok) throw new Error("Unable to load versions");
        const body = (await response.json()) as { versions?: string[]; message?: string };
        if (!Array.isArray(body.versions) || body.versions.length === 0) {
          setVersions({ status: "empty" });
          return;
        }
        setVersions({ status: "ready", versions: body.versions, selected: body.versions[0] });
      })
      .catch((error) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setVersions({
          status: "error",
          message: error instanceof Error ? error.message : "Unable to load versions",
        });
      });

    return () => controller.abort();
  }, [pkg, versionRetry]);

  useEffect(() => {
    const controller = new AbortController();
    if (!cluster) return () => controller.abort();

    fetch(withCluster("/api/cluster/namespaces", cluster), {
      signal: controller.signal,
      cache: "no-store",
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("Unable to load namespaces");
        const body = (await response.json()) as { items?: { name: string }[] };
        const names = (body.items ?? []).map((item) => item.name);
        if (names.length === 0) {
          setNamespaces({ status: "empty" });
          return;
        }
        setNamespaces({ status: "ready", names, selected: names[0] });
      })
      .catch((error) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setNamespaces({
          status: "error",
          message: error instanceof Error ? error.message : "Unable to load namespaces",
        });
      });

    return () => controller.abort();
  }, [cluster, namespaceRetry]);

  const retryVersions = () => {
    setVersions({ status: "loading" });
    setVersionRetry((current) => current + 1);
  };

  const retryNamespaces = () => {
    setNamespaces({ status: "loading" });
    setNamespaceRetry((current) => current + 1);
  };

  const handleClusterChange = (value: string | null) => {
    if (!value) return;
    selectCluster(value);
    setNamespaces({ status: "loading" });
  };

  const versionReady = versions.status === "ready";
  const namespacesReady = namespaces.status === "ready";
  const releaseValid =
    release.length > 0 &&
    release.length <= MAX_RELEASE_NAME_LENGTH &&
    RELEASE_NAME_PATTERN.test(release);
  const releaseError =
    release.length > 0 && !releaseValid
      ? "Use 1-63 lowercase letters, digits, or dashes; start and end with a letter or digit."
      : "";
  const submitEnabled =
    versionReady && Boolean(cluster) && namespacesReady && releaseValid;

  const submitInstall = () => {
    if (!versionReady || !namespacesReady || !cluster) return;
    setPosting(true);
    setInstallError(null);
    fetch("/api/marketplace/install", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        package_id: pkg.package_id,
        package_name: pkg.name,
        version: versions.selected,
        repository_name: pkg.repository?.name ?? "",
        cluster,
        namespace: namespaces.selected,
        release_name: release,
      }),
      cache: "no-store",
    })
      .then(async (response) => {
        const body = (await response.json()) as { job_id?: string; message?: string };
        if (!response.ok) throw new Error(body.message || "Installation request failed");
        setQueuedJobId(body.job_id ?? null);
      })
      .catch((error) => {
        setInstallError(
          error instanceof Error ? error.message : "Installation request failed",
        );
      })
      .finally(() => setPosting(false));
  };

  if (queuedJobId) {
    return (
      <JobProgress
        jobId={queuedJobId}
        packageName={pkg.name}
        cluster={cluster ?? ""}
        namespace={namespaces.status === "ready" ? namespaces.selected : ""}
        release={release}
        onClose={onClose}
      />
    );
  }

  return (
    <>
      <DialogHeader>
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Install package
        </span>
        <DialogTitle className="truncate">{pkg.name}</DialogTitle>
        <p className="text-sm text-muted-foreground">{publisherOf(pkg)}</p>
      </DialogHeader>
      {installError && (
        <div
          role="alert"
          className="flex items-center justify-between gap-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
        >
          <span>{installError}</span>
        </div>
      )}
      <div className="grid gap-4">
        <div>
          <label className="text-sm font-medium text-foreground" htmlFor="install-version">
            Version
          </label>
          {versions.status === "error" ? (
            <div
              role="alert"
              className="mt-1 flex items-center justify-between gap-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
            >
              <span>{versions.message}</span>
              <Button variant="outline" size="xs" onClick={retryVersions}>
                Retry
              </Button>
            </div>
          ) : versions.status === "empty" ? (
            <p className="mt-1 text-sm text-muted-foreground">
              This package has no available versions.
            </p>
          ) : (
            <Select
              value={versionReady ? versions.selected : null}
              onValueChange={(value) => {
                if (value !== null && versions.status === "ready") {
                  setVersions({ ...versions, selected: value });
                }
              }}
            >
              <SelectTrigger
                id="install-version"
                aria-label="Version"
                className="mt-1 w-full"
                disabled={!versionReady}
              >
                <SelectValue placeholder="Loading versions…" />
              </SelectTrigger>
              <SelectContent>
                {versions.status === "ready" &&
                  versions.versions.map((version) => (
                    <SelectItem key={version} value={version}>
                      {version}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          )}
        </div>
        <div>
          <label className="text-sm font-medium text-foreground" htmlFor="install-cluster">
            Cluster
          </label>
          {clusters.length === 0 ? (
            <p className="mt-1 text-sm text-muted-foreground">No active clusters.</p>
          ) : (
            <Select value={cluster || null} onValueChange={handleClusterChange}>
              <SelectTrigger
                id="install-cluster"
                aria-label="Cluster"
                className="mt-1 w-full"
              >
                <SelectValue placeholder="Select cluster" />
              </SelectTrigger>
              <SelectContent>
                {clusters.map((name) => (
                  <SelectItem key={name} value={name}>
                    {name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>
        <div>
          <label className="text-sm font-medium text-foreground" htmlFor="install-namespace">
            Namespace
          </label>
          {!cluster ? (
            <p className="mt-1 text-sm text-muted-foreground">
              Select a cluster to choose a namespace.
            </p>
          ) : namespaces.status === "error" ? (
            <div
              role="alert"
              className="mt-1 flex items-center justify-between gap-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
            >
              <span>{namespaces.message}</span>
              <Button variant="outline" size="xs" onClick={retryNamespaces}>
                Retry
              </Button>
            </div>
          ) : namespaces.status === "empty" ? (
            <p className="mt-1 text-sm text-muted-foreground">
              No namespaces available in this cluster.
            </p>
          ) : (
            <Select
              value={namespacesReady ? namespaces.selected : null}
              onValueChange={(value) => {
                if (value !== null && namespaces.status === "ready") {
                  setNamespaces({ ...namespaces, selected: value });
                }
              }}
            >
              <SelectTrigger
                id="install-namespace"
                aria-label="Namespace"
                className="mt-1 w-full"
                disabled={!namespacesReady}
              >
                <SelectValue placeholder="Loading namespaces…" />
              </SelectTrigger>
              <SelectContent>
                {namespaces.status === "ready" &&
                  namespaces.names.map((name) => (
                    <SelectItem key={name} value={name}>
                      {name}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          )}
        </div>
        <div>
          <label className="text-sm font-medium text-foreground" htmlFor="install-release-name">
            Release name
          </label>
          <Input
            id="install-release-name"
            type="text"
            value={release}
            onChange={(event) => setRelease(event.target.value)}
            placeholder="my-release"
            className="mt-1"
            aria-invalid={releaseError ? true : undefined}
            aria-describedby={releaseError ? "install-release-name-error" : undefined}
          />
          {releaseError && (
            <p id="install-release-name-error" role="alert" className="mt-1 text-sm text-red-600">
              {releaseError}
            </p>
          )}
        </div>
      </div>
      <DialogFooter>
        <Button type="button" disabled={!submitEnabled || posting} onClick={submitInstall}>
          {posting ? "Queuing…" : "Install"}
        </Button>
      </DialogFooter>
    </>
  );
}