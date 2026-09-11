"use client";

import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "kubepilot.cluster";

export function readStoredCluster(): string {
  if (typeof window === "undefined") return "";
  try {
    return window.localStorage.getItem(STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}

export function writeStoredCluster(cluster: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, cluster);
  } catch {
    // Storage may be unavailable (private mode, quota); selection still works in memory.
  }
}

export function useClusterSelection(initialCluster?: string, preserveInvalidSelection = false) {
  const [clusters, setClusters] = useState<string[]>([]);
  const [cluster, setCluster] = useState(() => initialCluster || readStoredCluster());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [unexpectedError, setUnexpectedError] = useState<Error | null>(null);
  const [revision, setRevision] = useState(0);
  const refreshClusters = useCallback(() => {
    setLoading(true);
    setError(null);
    setRevision((value) => value + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/clusters", { signal: controller.signal, cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) {
          if (!controller.signal.aborted) setError(response.status === 403
            ? "You do not have access to the registered clusters."
            : "Unable to load registered clusters. Refresh to try again.");
          return;
        }
        const body = (await response.json()) as {
          items?: { name: string; status?: string }[];
        };
        const names = (body.items ?? [])
          .filter((item) => item.status === "active")
          .map((item) => item.name);
        if (controller.signal.aborted) return;
        setClusters(names);
        setCluster((current) => {
          if (current && (preserveInvalidSelection || names.includes(current))) return current;
          return names[0] ?? "";
        });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        if (!(error instanceof TypeError || error instanceof SyntaxError)) {
          setUnexpectedError(error instanceof Error ? error : new Error("Unexpected cluster selection failure"));
          return;
        }
        setError("Unable to load registered clusters. Refresh to try again.");
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [preserveInvalidSelection, revision]);

  const selectCluster = useCallback((name: string) => {
    setCluster(name);
    writeStoredCluster(name);
  }, []);

  if (unexpectedError) throw unexpectedError;
  return { cluster, clusters, selectCluster, loading, error, refreshClusters };
}
