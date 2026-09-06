"use client";

import { useEffect, useState } from "react";

export function useClusterStatus(initialCluster?: string) {
  const [cluster, setCluster] = useState(initialCluster ?? "");

  useEffect(() => {
    if (cluster) return;
    const controller = new AbortController();
    fetch("/api/cluster/status", { signal: controller.signal, cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) return;
        const body = (await response.json()) as { cluster?: string };
        if (body.cluster) setCluster(body.cluster);
      })
      .catch(() => {});
    return () => controller.abort();
  }, [cluster]);

  return cluster;
}