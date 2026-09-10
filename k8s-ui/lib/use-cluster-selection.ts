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

export function useClusterSelection(initialCluster?: string) {
  const [clusters, setClusters] = useState<string[]>([]);
  const [cluster, setCluster] = useState(() => initialCluster || readStoredCluster());

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/clusters", { signal: controller.signal, cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) return;
        const body = (await response.json()) as {
          items?: { name: string; status?: string; connection_status?: string }[];
        };
        const names = (body.items ?? [])
          .filter((item) => item.status === "active" && item.connection_status === "connected")
          .map((item) => item.name);
        setClusters(names);
        setCluster((current) => {
          if (current && names.includes(current)) return current;
          return names[0] ?? "";
        });
      })
      .catch(() => {});
    return () => controller.abort();
  }, []);

  const selectCluster = useCallback((name: string) => {
    setCluster(name);
    writeStoredCluster(name);
  }, []);

  return { cluster, clusters, selectCluster };
}
