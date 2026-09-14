"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, CircleAlert, KeyRound, Loader2, RotateCw, Wifi } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  fetchProviders,
  saveProvider,
  testProvider,
  type ApiKeyAction,
  type ProviderId,
  type ProviderSummary,
} from "@/lib/settings-providers";

type FormState = { baseUrl: string; apiKey: string; clearApiKey: boolean };
type Feedback = { kind: "success" | "error" | "status"; message: string };

const providerHelp: Record<ProviderId, string> = {
  openai: "Use an OpenAI-compatible API base URL for your organization.",
  openrouter: "Use the OpenRouter OpenAI-compatible API base URL.",
  ollama: "Use the URL of the Ollama service reachable by the KubePilot backend.",
};

function initialForm(provider: ProviderSummary): FormState {
  return { baseUrl: provider.base_url ?? "", apiKey: "", clearApiKey: false };
}

export function SettingsProvidersView() {
  const [providers, setProviders] = useState<ProviderSummary[]>([]);
  const [forms, setForms] = useState<Record<string, FormState>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState<ProviderId | null>(null);
  const [testing, setTesting] = useState<ProviderId | null>(null);
  const [feedback, setFeedback] = useState<Record<string, Feedback>>({});

  async function loadProviders() {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchProviders();
      setProviders(result.providers);
      setForms(Object.fromEntries(result.providers.map((provider) => [provider.provider_id, initialForm(provider)])));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to load AI providers.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadProviders();
  }, []);

  function updateForm(providerId: ProviderId, changes: Partial<FormState>) {
    setForms((current) => ({ ...current, [providerId]: { ...current[providerId], ...changes } }));
    setFeedback((current) => {
      const next = { ...current };
      delete next[providerId];
      return next;
    });
  }

  async function handleSave(provider: ProviderSummary) {
    const form = forms[provider.provider_id];
    if (!form) return;
    setSaving(provider.provider_id);
    setFeedback((current) => ({ ...current, [provider.provider_id]: { kind: "status", message: "Saving provider configuration…" } }));
    try {
      const apiKeyAction: ApiKeyAction = form.clearApiKey ? "clear" : form.apiKey.trim() ? "replace" : "unchanged";
      const saved = await saveProvider(provider.provider_id, {
        base_url: form.baseUrl.trim(),
        api_key_action: apiKeyAction,
        ...(apiKeyAction === "replace" ? { api_key: form.apiKey } : {}),
      });
      setProviders((current) => current.map((item) => item.provider_id === saved.provider_id ? saved : item));
      setForms((current) => ({ ...current, [provider.provider_id]: { ...current[provider.provider_id], apiKey: "", clearApiKey: false } }));
      setFeedback((current) => ({ ...current, [provider.provider_id]: { kind: "success", message: `${provider.name} configuration saved.` } }));
    } catch (requestError) {
      setFeedback((current) => ({ ...current, [provider.provider_id]: { kind: "error", message: requestError instanceof Error ? requestError.message : "Unable to save provider configuration." } }));
    } finally {
      setSaving(null);
    }
  }

  async function handleTest(provider: ProviderSummary) {
    setTesting(provider.provider_id);
    setFeedback((current) => ({ ...current, [provider.provider_id]: { kind: "status", message: "Testing provider connection…" } }));
    try {
      const result = await testProvider(provider.provider_id);
      setFeedback((current) => ({
        ...current,
        [provider.provider_id]: {
          kind: result.status === "connected" ? "success" : result.status === "not_configured" ? "status" : "error",
          message: result.message,
        },
      }));
    } catch (requestError) {
      setFeedback((current) => ({ ...current, [provider.provider_id]: { kind: "error", message: requestError instanceof Error ? requestError.message : "Unable to test provider connection." } }));
    } finally {
      setTesting(null);
    }
  }

  if (loading) {
    return (
      <div className="space-y-6" aria-busy="true" aria-label="Loading AI provider settings">
        {["one", "two", "three"].map((item) => (
          <Card key={item}>
            <CardContent className="space-y-4 pt-6">
              <div className="h-5 w-40 animate-pulse rounded bg-muted" />
              <div className="h-8 w-full animate-pulse rounded bg-muted" />
              <div className="h-8 w-2/3 animate-pulse rounded bg-muted" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
        <span>{error}</span>
        <Button type="button" variant="outline" size="sm" onClick={() => void loadProviders()}>
          <RotateCw data-icon="inline-start" />
          Retry
        </Button>
      </div>
    );
  }

  if (providers.length === 0) {
    return <Card><CardContent className="py-10 text-center text-sm text-muted-foreground">No AI providers are registered.</CardContent></Card>;
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>AI Providers</CardTitle>
          <CardDescription className="max-w-3xl">
            Configure the provider endpoints available to KubePilot. Credentials are stored securely by the backend and are never shown again.
          </CardDescription>
        </CardHeader>
      </Card>

      {providers.map((provider) => {
        const form = forms[provider.provider_id] ?? initialForm(provider);
        const currentFeedback = feedback[provider.provider_id];
        const isSaving = saving === provider.provider_id;
        const isTesting = testing === provider.provider_id;
        const statusConfigured = provider.status === "configured";
        return (
          <Card key={provider.provider_id}>
            <CardHeader>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <CardTitle>{provider.name}</CardTitle>
                    <Badge variant={statusConfigured ? "secondary" : "outline"}>
                      {statusConfigured ? "Configured" : "Not configured"}
                    </Badge>
                  </div>
                  <CardDescription className="mt-1 max-w-2xl">{providerHelp[provider.provider_id]}</CardDescription>
                </div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Wifi className="size-4" aria-hidden="true" />
                  {provider.api_key_configured ? "Credential saved" : provider.credential_required ? "Credential required" : "No credential required"}
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label htmlFor={`${provider.provider_id}-base-url`} className="text-sm font-medium text-foreground">Base URL</label>
                <Input
                  id={`${provider.provider_id}-base-url`}
                  type="url"
                  value={form.baseUrl}
                  onChange={(event) => updateForm(provider.provider_id, { baseUrl: event.target.value })}
                  placeholder="https://provider.example/v1"
                  autoComplete="url"
                  maxLength={2048}
                  aria-describedby={`${provider.provider_id}-base-url-help`}
                  disabled={isSaving || isTesting}
                />
                <p id={`${provider.provider_id}-base-url-help`} className="text-sm text-muted-foreground">The backend validates this URL before saving or connecting.</p>
              </div>

              {provider.credential_required ? (
                <div className="space-y-2">
                  <label htmlFor={`${provider.provider_id}-api-key`} className="flex items-center gap-2 text-sm font-medium text-foreground">
                    <KeyRound className="size-4" aria-hidden="true" />
                    API key
                  </label>
                  <Input
                    id={`${provider.provider_id}-api-key`}
                    type="password"
                    value={form.apiKey}
                    onChange={(event) => updateForm(provider.provider_id, { apiKey: event.target.value, clearApiKey: false })}
                    placeholder={provider.api_key_configured ? "Leave blank to keep the saved key" : "Enter API key"}
                    autoComplete="new-password"
                    maxLength={100_000}
                    aria-describedby={`${provider.provider_id}-api-key-help`}
                    disabled={isSaving || isTesting}
                  />
                  <p id={`${provider.provider_id}-api-key-help`} className="text-sm text-muted-foreground">The saved key is write-only. It will not be returned or displayed after saving.</p>
                  {provider.api_key_configured ? (
                    <label className="flex items-center gap-2 text-sm text-muted-foreground">
                      <input
                        type="checkbox"
                        checked={form.clearApiKey}
                        onChange={(event) => updateForm(provider.provider_id, { clearApiKey: event.target.checked, apiKey: "" })}
                        disabled={isSaving || isTesting}
                      />
                      Clear saved API key
                    </label>
                  ) : null}
                </div>
              ) : null}

              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
                <div aria-live="polite" className="flex min-h-6 items-center gap-2 text-sm">
                  {currentFeedback?.kind === "success" ? <CheckCircle2 className="size-4 text-emerald-600" aria-hidden="true" /> : null}
                  {currentFeedback?.kind === "error" ? <CircleAlert className="size-4 text-destructive" aria-hidden="true" /> : null}
                  {currentFeedback?.kind === "status" && (isSaving || isTesting) ? <Loader2 className="size-4 animate-spin text-primary" aria-hidden="true" /> : null}
                  <span className={currentFeedback?.kind === "error" ? "text-destructive" : currentFeedback?.kind === "success" ? "text-emerald-600 dark:text-emerald-400" : "text-muted-foreground"}>{currentFeedback?.message}</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button type="button" variant="outline" onClick={() => void handleTest(provider)} disabled={isSaving || isTesting}>
                    {isTesting ? <Loader2 className="animate-spin" data-icon="inline-start" /> : <Wifi data-icon="inline-start" />}
                    {isTesting ? "Testing…" : "Test connection"}
                  </Button>
                  <Button type="button" onClick={() => void handleSave(provider)} disabled={isSaving || isTesting}>
                    {isSaving ? <Loader2 className="animate-spin" data-icon="inline-start" /> : null}
                    {isSaving ? "Saving…" : "Save changes"}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
