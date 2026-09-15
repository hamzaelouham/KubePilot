"use client";

import { useCallback, useEffect, useState } from "react";
import {
  BrainCircuit,
  CircleAlert,
  Loader2,
  Pencil,
  Plus,
  RefreshCw,
  Star,
  Trash2,
} from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { ProviderId } from "@/lib/settings-providers";
import {
  checkModel,
  createModel,
  deleteModel,
  fetchModels,
  setDefaultModel,
  updateModel,
  type AIModel,
  type ModelCapabilities,
  type ModelWritePayload,
} from "@/lib/settings-models";

const providers: Array<{ id: ProviderId; name: string }> = [
  { id: "openai", name: "OpenAI" },
  { id: "openrouter", name: "OpenRouter" },
  { id: "ollama", name: "Ollama" },
];

const capabilityLabels: Array<{ id: keyof ModelCapabilities; label: string }> = [
  { id: "streaming", label: "Streaming" },
  { id: "tools", label: "Tool calling" },
  { id: "reasoning", label: "Reasoning" },
  { id: "vision", label: "Vision" },
  { id: "large_context", label: "Large context" },
];

const emptyCapabilities: ModelCapabilities = {
  streaming: false,
  tools: false,
  reasoning: false,
  vision: false,
  large_context: false,
};

type Feedback = { kind: "success" | "error" | "status"; message: string };

function payloadFor(model: AIModel, enabled = model.enabled): ModelWritePayload {
  return {
    provider_id: model.provider_id,
    external_model_id: model.external_model_id,
    friendly_name: model.friendly_name,
    enabled,
    capabilities: model.capabilities,
  };
}

function availabilityVariant(model: AIModel): "default" | "secondary" | "outline" {
  if (model.availability === "available") return "default";
  if (model.availability === "unavailable") return "secondary";
  return "outline";
}

function ModelEditor({
  model,
  onClose,
  onSaved,
}: {
  model: AIModel | null;
  onClose: () => void;
  onSaved: (model: AIModel) => void;
}) {
  const [form, setForm] = useState<ModelWritePayload>(() => model ? payloadFor(model) : {
    provider_id: "openai",
    external_model_id: "",
    friendly_name: "",
    enabled: false,
    capabilities: emptyCapabilities,
  });
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const externalModelId = form.external_model_id.trim();
    const friendlyName = form.friendly_name.trim();
    if (!externalModelId || !friendlyName) {
      setError("External model ID and friendly name are required.");
      return;
    }
    setError(null);
    setSaving(true);
    try {
      const saved = model
        ? await updateModel(model.id, { ...form, external_model_id: externalModelId, friendly_name: friendlyName })
        : await createModel({ ...form, external_model_id: externalModelId, friendly_name: friendlyName });
      onSaved(saved);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to save the AI model.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open onOpenChange={(open) => { if (!open && !saving) onClose(); }}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-2xl">
        <form className="flex flex-col gap-5" onSubmit={submit}>
          <DialogHeader>
            <DialogTitle>{model ? "Edit AI model" : "Add AI model"}</DialogTitle>
            <DialogDescription>
              Register an exact provider model identity and explicitly declare the capabilities KubePilot may use later.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="flex flex-col gap-2 text-sm font-medium" htmlFor="model-provider">
              Provider
              <Select
                value={form.provider_id}
                onValueChange={(value) => setForm((current) => ({ ...current, provider_id: value as ProviderId }))}
                disabled={saving || model?.is_default}
              >
                <SelectTrigger id="model-provider" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {providers.map((provider) => (
                      <SelectItem key={provider.id} value={provider.id}>{provider.name}</SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </label>

            <label className="flex flex-col gap-2 text-sm font-medium" htmlFor="model-friendly-name">
              Friendly name
              <Input
                id="model-friendly-name"
                value={form.friendly_name}
                onChange={(event) => setForm((current) => ({ ...current, friendly_name: event.target.value }))}
                maxLength={128}
                aria-invalid={Boolean(error && !form.friendly_name.trim())}
                aria-describedby={error ? "model-form-error" : undefined}
                disabled={saving}
              />
            </label>
          </div>

          <label className="flex flex-col gap-2 text-sm font-medium" htmlFor="model-external-id">
            External model ID
            <Input
              id="model-external-id"
              value={form.external_model_id}
              onChange={(event) => setForm((current) => ({ ...current, external_model_id: event.target.value }))}
              placeholder="gpt-4.1-mini or llama3.2:latest"
              maxLength={255}
              aria-invalid={Boolean(error && !form.external_model_id.trim())}
              aria-describedby={error ? "model-form-error" : undefined}
              disabled={saving || model?.is_default}
            />
            <span className="text-sm font-normal text-muted-foreground">Use the exact case-sensitive identifier reported by the provider.</span>
          </label>

          <fieldset className="flex flex-col gap-3 rounded-lg border border-border p-4" disabled={saving}>
            <legend className="px-1 text-sm font-medium">Capabilities</legend>
            <p className="text-sm text-muted-foreground">Enable only capabilities confirmed for this exact model.</p>
            <div className="grid gap-3 sm:grid-cols-2">
              {capabilityLabels.map((capability) => (
                <label key={capability.id} className="flex items-center justify-between gap-3 rounded-md border border-border px-3 py-2 text-sm" htmlFor={`model-capability-${capability.id}`}>
                  {capability.label}
                  <Switch
                    id={`model-capability-${capability.id}`}
                    checked={form.capabilities[capability.id]}
                    onCheckedChange={(checked) => setForm((current) => ({
                      ...current,
                      capabilities: { ...current.capabilities, [capability.id]: checked },
                    }))}
                  />
                </label>
              ))}
            </div>
          </fieldset>

          <label className="flex items-center justify-between gap-4 rounded-lg border border-border p-4 text-sm" htmlFor="model-enabled">
            <span className="flex flex-col gap-1">
              <span className="font-medium">Enabled</span>
              <span className="text-muted-foreground">Enabled models still require a successful availability check before selection.</span>
            </span>
            <Switch
              id="model-enabled"
              checked={form.enabled}
              onCheckedChange={(checked) => setForm((current) => ({ ...current, enabled: checked }))}
              disabled={saving || model?.is_default}
            />
          </label>

          {error ? (
            <Alert id="model-form-error" variant="destructive">
              <CircleAlert />
              <AlertTitle>Could not save model</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={saving}>Cancel</Button>
            <Button type="submit" disabled={saving}>
              {saving ? <Loader2 className="animate-spin" data-icon="inline-start" /> : null}
              {saving ? "Saving…" : model ? "Save changes" : "Add model"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function SettingsModelsView() {
  const [models, setModels] = useState<AIModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [editor, setEditor] = useState<AIModel | "create" | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<AIModel | null>(null);
  const [confirmation, setConfirmation] = useState("");
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<Feedback | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const result = await fetchModels();
      setModels(result.models);
    } catch (requestError) {
      setLoadError(requestError instanceof Error ? requestError.message : "Unable to load AI models.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetchModels()
      .then((result) => {
        if (!cancelled) setModels(result.models);
      })
      .catch((requestError: unknown) => {
        if (!cancelled) setLoadError(requestError instanceof Error ? requestError.message : "Unable to load AI models.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  function replace(saved: AIModel) {
    setModels((current) => current.map((model) => model.id === saved.id ? saved : model));
  }

  async function runAction(model: AIModel, action: "check" | "default" | "toggle") {
    setPending(`${model.id}:${action}`);
    setFeedback({ kind: "status", message: action === "check" ? `Checking ${model.friendly_name}…` : action === "default" ? `Setting ${model.friendly_name} as default…` : `Updating ${model.friendly_name}…` });
    try {
      const saved = action === "check"
        ? await checkModel(model.id)
        : action === "default"
          ? await setDefaultModel(model.id)
          : await updateModel(model.id, payloadFor(model, !model.enabled));
      if (action === "default") {
        setModels((current) => current.map((item) => item.id === saved.id ? saved : { ...item, is_default: false }));
      } else {
        replace(saved);
      }
      setFeedback({
        kind: action === "check" && saved.availability === "unknown" ? "error" : action === "check" && saved.availability === "unavailable" ? "status" : "success",
        message: action === "check" ? saved.availability_message ?? "Availability check completed." : action === "default" ? `${saved.friendly_name} is now the default model.` : `${saved.friendly_name} updated.`,
      });
    } catch (requestError) {
      setFeedback({ kind: "error", message: requestError instanceof Error ? requestError.message : "The model action could not be completed." });
    } finally {
      setPending(null);
    }
  }

  async function remove() {
    if (!deleteTarget || confirmation !== deleteTarget.external_model_id) return;
    setDeleteError(null);
    setPending(`${deleteTarget.id}:delete`);
    try {
      await deleteModel(deleteTarget.id);
      setModels((current) => current.filter((model) => model.id !== deleteTarget.id));
      setFeedback({ kind: "success", message: `${deleteTarget.friendly_name} was removed.` });
      setDeleteTarget(null);
      setConfirmation("");
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : "Unable to remove the AI model.";
      setDeleteError(message);
      setFeedback({ kind: "error", message });
    } finally {
      setPending(null);
    }
  }

  function saved(model: AIModel) {
    setModels((current) => editor === "create" ? [...current, model] : current.map((item) => item.id === model.id ? model : item));
    setFeedback({ kind: "success", message: `${model.friendly_name} was saved.` });
    setPending(null);
    setEditor(null);
  }

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-4">
          <div className="flex flex-col gap-1.5">
            <CardTitle>AI Models</CardTitle>
            <CardDescription className="max-w-3xl">
              Register exact provider model IDs, declare capabilities, and control which checked models may be selected by KubePilot.
            </CardDescription>
          </div>
          <Button type="button" onClick={() => setEditor("create")}>
            <Plus data-icon="inline-start" />
            Add model
          </Button>
        </CardHeader>
      </Card>

      {feedback ? (
        <Alert variant={feedback.kind === "error" ? "destructive" : "default"} aria-live="polite">
          {feedback.kind === "error" ? <CircleAlert /> : null}
          <AlertTitle>{feedback.kind === "error" ? "Model action failed" : feedback.kind === "status" ? "Working" : "Model registry updated"}</AlertTitle>
          <AlertDescription>{feedback.message}</AlertDescription>
        </Alert>
      ) : null}

      {loading ? (
        <Card aria-busy="true" aria-label="Loading AI models">
          <CardContent className="flex flex-col gap-3 py-6">
            {["one", "two", "three"].map((row) => <Skeleton key={row} className="h-14 w-full" />)}
          </CardContent>
        </Card>
      ) : loadError ? (
        <Alert variant="destructive">
          <CircleAlert />
          <AlertTitle>Could not load AI models</AlertTitle>
          <AlertDescription>{loadError}</AlertDescription>
          <Button type="button" variant="outline" size="sm" onClick={() => void load()}>
            <RefreshCw data-icon="inline-start" />
            Retry
          </Button>
        </Alert>
      ) : models.length === 0 ? (
        <Empty className="border border-dashed">
          <EmptyHeader>
            <EmptyMedia><BrainCircuit /></EmptyMedia>
            <EmptyTitle>No AI models registered</EmptyTitle>
            <EmptyDescription>Add a model, then check its availability before enabling it for future Assistant selection.</EmptyDescription>
          </EmptyHeader>
          <EmptyContent><Button type="button" onClick={() => setEditor("create")}>Add model</Button></EmptyContent>
        </Empty>
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Model</TableHead>
                  <TableHead>Provider</TableHead>
                  <TableHead>Capabilities</TableHead>
                  <TableHead>Availability</TableHead>
                  <TableHead>Enabled</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {models.map((model) => {
                  const busy = pending?.startsWith(`${model.id}:`) ?? false;
                  return (
                    <TableRow key={model.id}>
                      <TableCell className="max-w-64 whitespace-normal">
                        <div className="flex flex-col gap-1">
                          <div className="flex flex-wrap items-center gap-2 font-medium">
                            {model.friendly_name}
                            {model.is_default ? <Badge><Star />Default</Badge> : null}
                          </div>
                          <code className="break-all text-xs text-muted-foreground">{model.external_model_id}</code>
                        </div>
                      </TableCell>
                      <TableCell><Badge variant="outline">{model.provider_name}</Badge></TableCell>
                      <TableCell className="max-w-72 whitespace-normal">
                        <div className="flex flex-wrap gap-1">
                          {capabilityLabels.filter((capability) => model.capabilities[capability.id]).map((capability) => (
                            <Badge key={capability.id} variant="secondary">{capability.label}</Badge>
                          ))}
                          {capabilityLabels.every((capability) => !model.capabilities[capability.id]) ? <span className="text-xs text-muted-foreground">None declared</span> : null}
                        </div>
                      </TableCell>
                      <TableCell className="max-w-64 whitespace-normal">
                        <div className="flex flex-col gap-1">
                          <Badge variant={availabilityVariant(model)} className="w-fit capitalize">{model.availability}</Badge>
                          <span className="text-xs text-muted-foreground">{model.availability_message ?? "Not checked"}</span>
                          {model.availability_checked_at ? <span className="text-xs text-muted-foreground">Checked {new Date(model.availability_checked_at).toLocaleString()}</span> : null}
                        </div>
                      </TableCell>
                      <TableCell>
                        <label className="flex items-center gap-2 text-sm" htmlFor={`enabled-${model.id}`}>
                          <Switch id={`enabled-${model.id}`} checked={model.enabled} onCheckedChange={() => void runAction(model, "toggle")} disabled={busy || model.is_default} />
                          {model.enabled ? "On" : "Off"}
                        </label>
                      </TableCell>
                      <TableCell>
                        <div className="flex justify-end gap-1">
                          <Button type="button" variant="ghost" size="icon-sm" aria-label={`Check ${model.friendly_name} availability`} title="Check availability" onClick={() => void runAction(model, "check")} disabled={busy}>
                            {pending === `${model.id}:check` ? <Loader2 className="animate-spin" /> : <RefreshCw />}
                          </Button>
                          <Button type="button" variant="ghost" size="icon-sm" aria-label={`Set ${model.friendly_name} as default`} title="Set as default" onClick={() => void runAction(model, "default")} disabled={busy || model.is_default || !model.enabled || model.availability !== "available"}>
                            <Star />
                          </Button>
                          <Button type="button" variant="ghost" size="icon-sm" aria-label={`Edit ${model.friendly_name}`} title="Edit model" onClick={() => setEditor(model)} disabled={busy}>
                            <Pencil />
                          </Button>
                          <Button type="button" variant="ghost" size="icon-sm" aria-label={`Delete ${model.friendly_name}`} title="Delete model" onClick={() => { setDeleteTarget(model); setConfirmation(""); setDeleteError(null); }} disabled={busy || model.is_default}>
                            <Trash2 />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {editor ? (
        <ModelEditor
          key={editor === "create" ? "create" : editor.id}
          model={editor === "create" ? null : editor}
          onClose={() => setEditor(null)}
          onSaved={saved}
        />
      ) : null}

      <AlertDialog open={deleteTarget !== null} onOpenChange={(open) => { if (!open && pending !== `${deleteTarget?.id}:delete`) { setDeleteTarget(null); setConfirmation(""); setDeleteError(null); } }}>
        <AlertDialogContent className="sm:max-w-lg">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {deleteTarget?.friendly_name}?</AlertDialogTitle>
            <AlertDialogDescription>
              This removes the model from KubePilot&apos;s registry. It does not delete anything from the provider.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <label className="flex flex-col gap-2 text-sm font-medium" htmlFor="delete-model-confirmation">
            Type <code className="break-all">{deleteTarget?.external_model_id}</code> to confirm
            <Input id="delete-model-confirmation" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} autoComplete="off" disabled={pending === `${deleteTarget?.id}:delete`} />
          </label>
          {deleteError ? <p role="alert" className="text-sm text-destructive">{deleteError}</p> : null}
          <AlertDialogFooter>
            <AlertDialogCancel disabled={pending === `${deleteTarget?.id}:delete`}>Cancel</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={() => void remove()} disabled={!deleteTarget || confirmation !== deleteTarget.external_model_id || pending === `${deleteTarget?.id}:delete`}>
              {pending === `${deleteTarget?.id}:delete` ? <Loader2 className="animate-spin" data-icon="inline-start" /> : null}
              {pending === `${deleteTarget?.id}:delete` ? "Deleting…" : "Delete model"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
