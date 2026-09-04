"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export const REFRESH_INTERVAL_MS = 30_000;

export function formatLastUpdated(value: Date | null): string {
  return value ? value.toLocaleTimeString() : "—";
}

export function usePolling(run: () => Promise<unknown>, enabled = true): { refresh: () => void; lastUpdated: Date | null } {
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const busyRef = useRef(false);

  const execute = useCallback(() => {
    if (busyRef.current) return;
    busyRef.current = true;
    Promise.resolve()
      .then(() => run())
      .catch(() => {})
      .finally(() => {
        busyRef.current = false;
        setLastUpdated(new Date());
      });
  }, [run]);

  const refresh = useCallback(() => execute(), [execute]);

  useEffect(() => {
    if (!enabled) return;

    let interval: ReturnType<typeof setInterval> | undefined;
    const arm = () => {
      if (interval) clearInterval(interval);
      interval = setInterval(execute, REFRESH_INTERVAL_MS);
    };
    const onVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        execute();
        arm();
      } else {
        if (interval) clearInterval(interval);
        interval = undefined;
      }
    };

    arm();
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      if (interval) clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [enabled, execute]);

  return { refresh, lastUpdated };
}
