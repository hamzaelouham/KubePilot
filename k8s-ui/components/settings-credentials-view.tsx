"use client";

import { useEffect, useState } from "react";
import { KeyRound, Loader2, RotateCw, ShieldCheck, Trash2 } from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  deleteCredential,
  fetchCredentials,
  saveCredential,
  type CredentialMetadata,
} from "@/lib/settings-credentials";

type PendingAction = { credentialKey: string; action: "save" | "delete" } | null;
type Feedback = { kind: "success" | "error"; message: string };

const categoryLabels: Record<CredentialMetadata["category"], string> = {
  provider: "Provider credentials",
  integration: "Integration credentials",
};

function updatedLabel(value: string | null) {
  if (!value) return "Never updated";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Update time unavailable" : `Updated ${date.toLocaleString()}`;
}

export function SettingsCredentialsView() {
  const [credentials, setCredentials] = useState<CredentialMetadata[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [secretValue, setSecretValue] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingAction>(null);
  const [feedback, setFeedback] = useState<Record<string, Feedback>>({});
  const [deleteTarget, setDeleteTarget] = useState<CredentialMetadata | null>(null);
  const [confirmation, setConfirmation] = useState("");
  const [deleteError, setDeleteError] = useState<string | null>(null);

  async function loadCredentials() {
    setLoading(true);
    setLoadError(null);
    try {
      const result = await fetchCredentials();
      setCredentials(result.credentials);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "Unable to load credentials.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadCredentials();
  }, []);

  function openEditor(credential: CredentialMetadata) {
    setEditingKey(credential.credential_key);
    setSecretValue("");
    setValidationError(null);
    setFeedback((current) => {
      const next = { ...current };
      delete next[credential.credential_key];
      return next;
    });
  }

  function closeEditor() {
    if (pending?.action === "save") return;
    setEditingKey(null);
    setSecretValue("");
    setValidationError(null);
  }

  async function save(credential: CredentialMetadata) {
    if (!secretValue.trim()) {
      setValidationError("Enter a non-blank credential value.");
      return;
    }
    setValidationError(null);
    setPending({ credentialKey: credential.credential_key, action: "save" });
    try {
      const saved = await saveCredential(credential.credential_key, secretValue);
      setCredentials((current) => current.map((item) => item.credential_key === saved.credential_key ? saved : item));
      setEditingKey(null);
      setSecretValue("");
      setFeedback((current) => ({
        ...current,
        [saved.credential_key]: {
          kind: "success",
          message: credential.configured ? "Credential rotated successfully." : "Credential configured successfully.",
        },
      }));
    } catch (error) {
      setFeedback((current) => ({
        ...current,
        [credential.credential_key]: {
          kind: "error",
          message: error instanceof Error ? error.message : "Unable to save the credential.",
        },
      }));
    } finally {
      setPending(null);
    }
  }

  function openDelete(credential: CredentialMetadata) {
    setDeleteTarget(credential);
    setConfirmation("");
    setDeleteError(null);
  }

  async function remove() {
    if (!deleteTarget || confirmation !== deleteTarget.display_name) return;
    setPending({ credentialKey: deleteTarget.credential_key, action: "delete" });
    setDeleteError(null);
    try {
      const removed = await deleteCredential(deleteTarget.credential_key);
      setCredentials((current) => current.map((item) => item.credential_key === removed.credential_key ? removed : item));
      setFeedback((current) => ({
        ...current,
        [removed.credential_key]: { kind: "success", message: "Credential deleted." },
      }));
      setDeleteTarget(null);
      setConfirmation("");
    } catch (error) {
      setDeleteError(error instanceof Error ? error.message : "Unable to delete the credential.");
    } finally {
      setPending(null);
    }
  }

  if (loading) {
    return (
      <div className="space-y-4" aria-busy="true" aria-label="Loading credentials">
        {["one", "two"].map((item) => (
          <Card key={item}>
            <CardContent className="space-y-4 pt-6">
              <div className="h-5 w-48 animate-pulse rounded bg-muted" />
              <div className="h-4 w-2/3 animate-pulse rounded bg-muted" />
              <div className="h-9 w-32 animate-pulse rounded bg-muted" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  if (loadError) {
    return (
      <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
        <span>{loadError}</span>
        <Button type="button" variant="outline" size="sm" onClick={() => void loadCredentials()}>
          <RotateCw data-icon="inline-start" />
          Retry
        </Button>
      </div>
    );
  }

  if (credentials.length === 0) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          No credentials are registered. Provider and integration modules register credentials when they support secure configuration.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle>Secrets &amp; Credentials</CardTitle>
              <CardDescription className="mt-1 max-w-3xl">
                Configure API keys and integration secrets registered by KubePilot. Saved values are encrypted and can never be viewed again.
              </CardDescription>
            </div>
            <Badge variant="secondary" className="gap-1.5">
              <ShieldCheck className="size-3.5" aria-hidden="true" />
              Admin only
            </Badge>
          </div>
        </CardHeader>
      </Card>

      {(["provider", "integration"] as const).map((category) => {
        const items = credentials.filter((credential) => credential.category === category);
        if (items.length === 0) return null;
        return (
          <section key={category} aria-labelledby={`${category}-credentials-heading`} className="space-y-3">
            <h2 id={`${category}-credentials-heading`} className="text-sm font-semibold uppercase tracking-[0.12em] text-muted-foreground">
              {categoryLabels[category]}
            </h2>
            <div className="grid gap-4 xl:grid-cols-2">
              {items.map((credential) => {
                const isEditing = editingKey === credential.credential_key;
                const isSaving = pending?.credentialKey === credential.credential_key && pending.action === "save";
                const currentFeedback = feedback[credential.credential_key];
                return (
                  <Card key={credential.credential_key}>
                    <CardHeader>
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="flex min-w-0 gap-3">
                          <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                            <KeyRound className="size-5" aria-hidden="true" />
                          </div>
                          <div className="min-w-0">
                            <CardTitle className="text-base">{credential.display_name}</CardTitle>
                            <CardDescription className="mt-1">{credential.description}</CardDescription>
                          </div>
                        </div>
                        <Badge variant={credential.configured ? "secondary" : "outline"}>
                          {credential.configured ? "Configured" : "Not configured"}
                        </Badge>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-muted-foreground">
                        <code className="rounded bg-muted px-2 py-1">{credential.credential_key}</code>
                        <span>{updatedLabel(credential.updated_at)}</span>
                      </div>

                      {isEditing ? (
                        <div className="space-y-3 rounded-lg border border-border bg-muted/20 p-4">
                          <div className="space-y-2">
                            <label htmlFor={`${credential.credential_key}-value`} className="text-sm font-medium">
                              {credential.configured ? "New credential value" : "Credential value"}
                            </label>
                            <Input
                              id={`${credential.credential_key}-value`}
                              type="password"
                              autoComplete="new-password"
                              value={secretValue}
                              onChange={(event) => {
                                setSecretValue(event.target.value);
                                setValidationError(null);
                                setFeedback((current) => {
                                  const next = { ...current };
                                  delete next[credential.credential_key];
                                  return next;
                                });
                              }}
                              maxLength={100_000}
                              aria-invalid={Boolean(validationError)}
                              aria-describedby={`${credential.credential_key}-help${validationError ? ` ${credential.credential_key}-error` : ""}`}
                              disabled={isSaving}
                              autoFocus
                            />
                            <p id={`${credential.credential_key}-help`} className="text-xs text-muted-foreground">
                              The value is write-only and will be cleared from this form after saving.
                            </p>
                            {validationError ? <p id={`${credential.credential_key}-error`} role="alert" className="text-sm text-destructive">{validationError}</p> : null}
                            {currentFeedback?.kind === "error" ? <p role="alert" className="text-sm text-destructive">{currentFeedback.message}</p> : null}
                          </div>
                          <div className="flex flex-wrap justify-end gap-2">
                            <Button type="button" variant="outline" onClick={closeEditor} disabled={isSaving}>Cancel</Button>
                            <Button type="button" onClick={() => void save(credential)} disabled={isSaving}>
                              {isSaving ? <Loader2 className="animate-spin" data-icon="inline-start" /> : null}
                              {isSaving ? "Saving…" : credential.configured ? "Rotate credential" : "Save credential"}
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
                          <div aria-live="polite" className={`min-h-5 text-sm ${currentFeedback?.kind === "error" ? "text-destructive" : "text-emerald-600 dark:text-emerald-400"}`}>
                            {currentFeedback?.message}
                          </div>
                          <div className="flex flex-wrap gap-2">
                            {credential.configured ? (
                              <Button type="button" variant="outline" onClick={() => openDelete(credential)} disabled={pending !== null}>
                                <Trash2 data-icon="inline-start" />
                                Delete
                              </Button>
                            ) : null}
                            <Button type="button" onClick={() => openEditor(credential)} disabled={pending !== null || editingKey !== null}>
                              {credential.configured ? "Rotate" : "Configure"}
                            </Button>
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          </section>
        );
      })}

      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open && pending?.action !== "delete") {
            setDeleteTarget(null);
            setConfirmation("");
            setDeleteError(null);
          }
        }}
      >
        <AlertDialogContent className="sm:max-w-lg">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {deleteTarget?.display_name}?</AlertDialogTitle>
            <AlertDialogDescription>
              This permanently removes the saved value. Providers or integrations that depend on it will stop working until it is configured again.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="space-y-2">
            <label htmlFor="credential-delete-confirmation" className="text-sm font-medium">
              Type <span className="font-semibold text-foreground">{deleteTarget?.display_name}</span> to confirm
            </label>
            <Input
              id="credential-delete-confirmation"
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)}
              autoComplete="off"
              disabled={pending?.action === "delete"}
              autoFocus
            />
            {deleteError ? <p role="alert" className="text-sm text-destructive">{deleteError}</p> : null}
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={pending?.action === "delete"}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => void remove()}
              disabled={!deleteTarget || confirmation !== deleteTarget.display_name || pending?.action === "delete"}
            >
              {pending?.action === "delete" ? <Loader2 className="animate-spin" data-icon="inline-start" /> : null}
              {pending?.action === "delete" ? "Deleting…" : "Delete credential"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
