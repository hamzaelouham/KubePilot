"use client";

import { FormEvent, useEffect, useState } from "react";
import { CheckCircle2, RotateCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { fetchUserPreferences, updateUserPreferences } from "@/lib/settings-preferences";

export function GeneralSettingsForm() {
  const [defaultNamespace, setDefaultNamespace] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function loadPreferences() {
    setLoading(true);
    setError(null);
    try {
      const preferences = await fetchUserPreferences();
      setDefaultNamespace(preferences.default_namespace ?? "");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to load preferences");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadPreferences();
  }, []);

  async function savePreferences(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await updateUserPreferences({ default_namespace: defaultNamespace.trim() || null });
      setSaved(true);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to save preferences");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="space-y-6" aria-busy="true" aria-label="Loading general settings">
        <Card>
          <CardContent className="space-y-4 pt-6">
            <div className="h-5 w-40 animate-pulse rounded bg-muted" />
            <div className="h-8 w-full animate-pulse rounded bg-muted" />
            <div className="h-8 w-2/3 animate-pulse rounded bg-muted" />
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
              <CardTitle>Application preferences</CardTitle>
              <CardDescription className="mt-1 max-w-2xl">
                Manage runtime preferences for your KubePilot account.
              </CardDescription>
            </div>
            <Button type="submit" form="general-settings-form" disabled={saving}>
              {saving ? "Saving…" : "Save changes"}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <form id="general-settings-form" className="space-y-2" onSubmit={savePreferences}>
            <label htmlFor="default-namespace" className="text-sm font-medium text-foreground">
              Default namespace
            </label>
            <Input
              id="default-namespace"
              value={defaultNamespace}
              onChange={(event) => {
                setDefaultNamespace(event.target.value);
                setSaved(false);
              }}
              placeholder="default"
              maxLength={63}
              autoComplete="off"
              aria-describedby="default-namespace-help"
            />
            <p id="default-namespace-help" className="text-sm text-muted-foreground">
              Used as the default namespace where existing KubePilot views support a saved preference. Leave blank to use the application default.
            </p>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Deployment-managed configuration</CardTitle>
          <CardDescription>
            Infrastructure and bootstrap settings remain managed by Kubernetes and are not editable here.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm leading-6 text-muted-foreground">
            KubePilot does not expose process environment variables or infrastructure secrets through the Settings interface.
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
          Preferences saved.
        </p>
      ) : null}
    </div>
  );
}
