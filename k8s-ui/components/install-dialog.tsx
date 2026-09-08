"use client";

import { useEffect, useState } from "react";
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
          <InstallDialogBody key={pkg.package_id} pkg={pkg} />
        </DialogContent>
      )}
    </Dialog>
  );
}

function InstallDialogBody({ pkg }: { pkg: MarketplacePackage }) {
  const { cluster, clusters, selectCluster } = useClusterSelection();
  const [versions, setVersions] = useState<VersionsState>({ status: "loading" });
  const [versionRetry, setVersionRetry] = useState(0);
  const [namespaces, setNamespaces] = useState<NamespacesState>({ status: "loading" });
  const [namespaceRetry, setNamespaceRetry] = useState(0);
  const [release, setRelease] = useState("");

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

  return (
    <>
      <DialogHeader>
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Install package
        </span>
        <DialogTitle className="truncate">{pkg.name}</DialogTitle>
        <p className="text-sm text-muted-foreground">{publisherOf(pkg)}</p>
      </DialogHeader>
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
        <Button type="button" disabled={!submitEnabled}>
          Install
        </Button>
      </DialogFooter>
    </>
  );
}