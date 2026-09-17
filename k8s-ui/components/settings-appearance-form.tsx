"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Monitor, Moon, RotateCw, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchUserPreferences, themeOptions, updateUserPreferences, type ThemePreference } from "@/lib/settings-preferences";

const themeIcons = { light: Sun, dark: Moon, system: Monitor } as const;

export function AppearanceSettingsForm() {
  const { setTheme } = useTheme();
  const [selectedTheme, setSelectedTheme] = useState<ThemePreference>("system");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function loadPreferences() {
    setLoading(true);
    setError(null);
    try {
      const preferences = await fetchUserPreferences();
      setSelectedTheme(preferences.theme);
      setTheme(preferences.theme);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to load appearance preferences");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let active = true;
    fetchUserPreferences().then(
      (preferences) => {
        if (active) {
          setSelectedTheme(preferences.theme);
          setTheme(preferences.theme);
          setLoading(false);
        }
      },
      (requestError: unknown) => {
        if (active) {
          setError(requestError instanceof Error ? requestError.message : "Unable to load appearance preferences");
          setLoading(false);
        }
      }
    );
    return () => {
      active = false;
    };
  }, [setTheme]);

  async function saveTheme() {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await updateUserPreferences({ theme: selectedTheme });
      setSaved(true);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to save appearance preferences");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div aria-busy="true" aria-label="Loading appearance settings">
        <Card>
          <CardContent className="space-y-4 pt-6">
            <div className="h-5 w-40 animate-pulse rounded bg-muted" />
            <div className="h-20 w-full animate-pulse rounded bg-muted" />
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle>Appearance</CardTitle>
              <CardDescription className="mt-1 max-w-2xl">
                Choose how KubePilot should appear for your account.
              </CardDescription>
            </div>
            <Button type="button" onClick={() => void saveTheme()} disabled={saving}>
              {saving ? "Saving…" : "Save changes"}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-3" role="radiogroup" aria-label="Theme">
            {themeOptions.map(({ value, label }) => {
              const Icon = themeIcons[value];
              const selected = selectedTheme === value;
              return (
                <button
                  key={value}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  onClick={() => {
                    setSelectedTheme(value);
                    setTheme(value);
                    setSaved(false);
                  }}
                  className={`flex items-center gap-3 rounded-lg border px-4 py-3 text-left text-sm transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 ${selected ? "border-primary bg-primary/5 text-foreground" : "border-border text-muted-foreground hover:bg-muted/50"}`}
                >
                  <Icon className="size-4" />
                  <span className="font-medium">{label}</span>
                </button>
              );
            })}
          </div>
          <p className="text-sm text-muted-foreground">
            System follows your operating system preference. Your choice is also available from the account menu.
          </p>
        </CardContent>
      </Card>

      {error ? (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          <span>{error}</span>
          <Button type="button" variant="outline" size="sm" onClick={() => void loadPreferences()}>
            <RotateCw data-icon="inline-start" />
            Retry
          </Button>
        </div>
      ) : null}
      {saved ? (
        <p role="status" className="flex items-center gap-2 text-sm text-emerald-600 dark:text-emerald-400">
          <CheckCircle2 className="size-4" />
          Appearance saved.
        </p>
      ) : null}
    </div>
  );
}
