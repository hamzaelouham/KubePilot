"use client";

import { useEffect } from "react";
import { useTheme } from "next-themes";
import { fetchUserPreferences } from "@/lib/settings-preferences";

export function ThemePreferenceSync() {
  const { setTheme } = useTheme();

  useEffect(() => {
    let cancelled = false;

    fetchUserPreferences()
      .then((preferences) => {
        if (!cancelled) setTheme(preferences.theme);
      })
      .catch(() => {
        // Keep next-themes' local preference when the user is logged out or the API is unavailable.
      });

    return () => {
      cancelled = true;
    };
  }, [setTheme]);

  return null;
}
