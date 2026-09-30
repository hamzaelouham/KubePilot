"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, Check, LoaderCircle, Play, Trash2 } from "lucide-react";
import { z } from "zod";
import { Agent, AgentContent, AgentHeader, AgentInstructions } from "@/components/ai-elements/agent";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle, AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Field, FieldGroup, FieldLabel, FieldDescription, FieldError } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { agentRequest, agentSchema, AgentRequestError, applyTemplate, draftOf, emptyAgent, validateAgent, type AgentDefinition, type AgentDraft, type AgentErrors, type AgentModel, type AgentSkill, type AgentTemplate, type AgentTool } from "@/lib/assistant/agents";
import { cn } from "@/lib/utils";

type Props = {
  original: AgentDefinition | null; models: AgentModel[]; editable: boolean;
  skills: AgentSkill[]; tools: AgentTool[]; template?: AgentTemplate | null;
  modelsError: string; onSaved: (agent: AgentDefinition) => void;
  onDeleted: () => void; onCancel: () => void; onDirty: (dirty: boolean) => void; onRun?: () => void;
};

export function AgentEditor({ original, models, editable, skills, tools, template, modelsError, onSaved, onDeleted, onCancel, onDirty, onRun }: Props) {
  const initial = original ? draftOf(original) : template ? applyTemplate({ ...emptyAgent }, template) : { ...emptyAgent };
  const [draft, setDraft] = useState<AgentDraft>(() => initial);
  const [baseline, setBaseline] = useState(() => JSON.stringify(initial));
  const [step, setStep] = useState(original ? 2 : 0);
  const [errors, setErrors] = useState<AgentErrors>({});
  const [failure, setFailure] = useState<AgentRequestError | null>(null);
  const [pending, setPending] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [notice, setNotice] = useState("");
  const busy = useRef(false);
  const form = useRef<HTMLFormElement>(null);
  const dirty = JSON.stringify(draft) !== baseline;
  const creating = !original;
  const denied = failure?.status === 401 || failure?.status === 403;
  const uncertain = !!failure && (failure.status === 0 || failure.status >= 500);
  const canEdit = editable && !denied;
  const model = models.find(item => item.id === draft.model_id) ?? (original?.model_id === draft.model_id ? original.model : null);
  const choices = original?.model && !models.some(item => item.id === original.model_id) ? [...models, original.model] : models;

  useEffect(() => { onDirty(dirty); }, [dirty, onDirty]);
  useEffect(() => {
    if (Object.keys(errors).length) form.current?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus();
  }, [errors]);

  function change<K extends keyof AgentDraft>(key: K, value: AgentDraft[K]) {
    setDraft(previous => ({ ...previous, [key]: value }));
    setErrors(previous => ({ ...previous, [key]: undefined }));
    setNotice("");
    if (!uncertain && !denied) setFailure(null);
  }
  function toggleAssignment(key: "skill_ids" | "tool_ids", value: string, checked: boolean) {
    setDraft(previous => {
      const current = previous[key] as string[];
      return { ...previous, [key]: checked ? [...current, value] : current.filter(item => item !== value) };
    });
    setNotice("");
    if (!uncertain && !denied) setFailure(null);
  }
  async function submit() {
    if (busy.current || !canEdit || uncertain) return;
    const found = validateAgent(draft, original, choices, step);
    if (Object.keys(found).length) {
      if (creating) setStep(found.name || found.description || found.instructions ? 0 : 1);
      setErrors(found); return;
    }
    if (creating && step < 2) { setStep(step + 1); return; }
    busy.current = true; setPending(true); setFailure(null);
    try {
      const saved = await agentRequest(`/api/assistant/agents${original ? `/${original.id}` : ""}`, agentSchema, original ? "PUT" : "POST", draft);
      setDraft(draftOf(saved)); setBaseline(JSON.stringify(draftOf(saved))); onDirty(false);
      setNotice("Changes saved."); onSaved(saved);
    } catch (error) {
      setFailure(error instanceof AgentRequestError ? error : new AgentRequestError(500, "unexpected_error", "Unexpected error. Refresh stored state before trying again."));
    } finally { busy.current = false; setPending(false); }
  }
  async function remove() {
    if (!original || busy.current || uncertain) return;
    busy.current = true; setPending(true); setFailure(null);
    try {
      await agentRequest(`/api/assistant/agents/${original.id}`, z.object({ id: z.string().uuid() }), "DELETE");
      onDirty(false); setDeleteOpen(false); onDeleted();
    } catch (error) {
      setFailure(error instanceof AgentRequestError ? error : new AgentRequestError(500, "unexpected_error", "Unexpected deletion error. Refresh before retrying."));
    } finally { busy.current = false; setPending(false); }
  }
  async function reconcile() {
    setPending(true); busy.current = true;
    try {
      if (original) {
        const current = await agentRequest(`/api/assistant/agents/${original.id}`, agentSchema);
        // Keep the local draft; the refreshed record lets the user compare before retrying.
        setNotice(`Stored state refreshed: ${current.name}, ${current.enabled ? "enabled" : "disabled"}. Your draft is retained.`);
      } else {
        const current = await agentRequest("/api/assistant/agents", z.object({ agents: z.array(agentSchema) }));
        const matching = current.agents.find(agent => agent.name === draft.name.trim());
        if (matching) {
          setNotice("An agent with this name is already stored. Return to the list to review it before creating another.");
          setFailure(new AgentRequestError(409, "agent_conflict", "Name already stored. Review the agent list."));
          return;
        }
        setNotice("Stored state refreshed. No agent with this name exists; you may retry.");
      }
      setFailure(null);
    } catch (error) { setFailure(error instanceof AgentRequestError ? error : new AgentRequestError(500, "unexpected_error", "Could not refresh stored state.")); }
    finally { setPending(false); busy.current = false; }
  }
  const basic = <FieldGroup>
    <Field data-invalid={!!errors.name}><FieldLabel htmlFor="agent-name">Agent name</FieldLabel>
      <Input id="agent-name" value={draft.name} disabled={!canEdit || pending} aria-invalid={!!errors.name} aria-describedby="agent-name-help agent-name-error" onChange={e => change("name", e.target.value)} placeholder="e.g. Cluster troubleshooter" />
      <FieldDescription id="agent-name-help">A unique name for your shared agent. Up to 128 characters.</FieldDescription><FieldError id="agent-name-error" role="alert">{errors.name}</FieldError></Field>
    <Field data-invalid={!!errors.description}><FieldLabel htmlFor="agent-description">Description</FieldLabel>
      <Textarea id="agent-description" rows={3} value={draft.description} disabled={!canEdit || pending} aria-invalid={!!errors.description} aria-describedby="agent-description-error" onChange={e => change("description", e.target.value)} placeholder="Describe the agent’s purpose and when to use it." />
      <FieldError id="agent-description-error" role="alert">{errors.description}</FieldError></Field>
    <Field data-invalid={!!errors.instructions}><FieldLabel htmlFor="agent-instructions">Instructions</FieldLabel>
      <Textarea id="agent-instructions" rows={7} value={draft.instructions} disabled={!canEdit || pending} aria-invalid={!!errors.instructions} aria-describedby="agent-instructions-help agent-instructions-error" onChange={e => change("instructions", e.target.value)} placeholder="Define the agent’s focus, approach, and expected response." />
      <FieldDescription id="agent-instructions-help">Instructions guide behavior; they never grant permissions. Do not include secrets.</FieldDescription><FieldError id="agent-instructions-error" role="alert">{errors.instructions}</FieldError></Field>
  </FieldGroup>;
  const modelFields = <FieldGroup>
    {modelsError && <Alert><AlertTitle>Model list unavailable</AlertTitle><AlertDescription>{modelsError} Existing configuration is preserved.</AlertDescription></Alert>}
    <Field data-invalid={!!errors.model_id}><FieldLabel htmlFor="agent-model">Model</FieldLabel>
      <Select value={draft.model_id} onValueChange={value => change("model_id", value || null)} disabled={!canEdit || pending}>
        <SelectTrigger id="agent-model" className="w-full" aria-invalid={!!errors.model_id} aria-describedby="agent-model-help agent-model-error"><SelectValue placeholder={original && !draft.model_id ? "Model missing" : "Select a model"} /></SelectTrigger>
        <SelectContent><SelectGroup>{choices.map(item => <SelectItem key={item.id} value={item.id}>{item.friendly_name} · {item.provider_name}{!item.enabled ? " · Disabled" : item.availability !== "available" ? ` · ${item.availability}` : ""}</SelectItem>)}</SelectGroup></SelectContent>
      </Select>
      <FieldDescription id="agent-model-help">Models are managed in Settings. {editable && <Link href="/settings/models">Manage models</Link>}</FieldDescription>
      <FieldError id="agent-model-error" role="alert">{errors.model_id}</FieldError>
    </Field>
    {!choices.length && !modelsError && <Alert><AlertTitle>{original ? "Model missing" : "No models configured"}</AlertTitle><AlertDescription>{editable ? "Add a model in Settings before creating or enabling an agent." : "Ask an administrator to configure a model."}</AlertDescription></Alert>}
    {model && <div className="flex flex-wrap gap-2"><Badge variant="outline">{model.enabled ? model.availability : "Model disabled"}</Badge><Badge variant="secondary">{model.capabilities.tools ? "Tool support" : "Conversational"}</Badge></div>}
    <Field orientation="horizontal"><div className="flex flex-1 flex-col gap-1"><FieldLabel htmlFor="agent-enabled">Enable agent</FieldLabel><FieldDescription>Configuration only. This does not start a run or schedule.</FieldDescription></div>
      <Switch id="agent-enabled" checked={draft.enabled} onCheckedChange={checked => change("enabled", checked)} disabled={!canEdit || pending} /></Field>
  </FieldGroup>;
  const capabilityFields = <div className="flex flex-col gap-5">
    <div><h2 className="text-sm font-semibold">Skills and capabilities</h2><p className="mt-1 text-sm text-muted-foreground">Assignments describe future agent behavior. They do not grant access or execute tools.</p></div>
    <div className="grid gap-3 md:grid-cols-2">
      <Card><CardHeader><CardTitle className="text-base">Reusable skills</CardTitle><CardDescription>Select shared instruction blocks in their composition order.</CardDescription></CardHeader><CardContent className="flex flex-col gap-2">
        {!skills.length ? <p className="text-sm text-muted-foreground">No skills are configured yet.</p> : skills.map(skill => <label key={skill.id} className="flex items-start gap-3 rounded-md border p-3 text-sm"><input type="checkbox" checked={draft.skill_ids.includes(skill.id)} disabled={!canEdit || pending} onChange={event => toggleAssignment("skill_ids", skill.id, event.target.checked)} /><span className="min-w-0"><span className="block font-medium">{skill.name}</span><span className="block text-muted-foreground">{skill.description}</span></span></label>)}
      </CardContent></Card>
      <Card><CardHeader><CardTitle className="text-base">Supported tools</CardTitle><CardDescription>Effective status is recomputed from the model and your current permissions.</CardDescription></CardHeader><CardContent className="flex flex-col gap-2">
        {!tools.length ? <p className="text-sm text-muted-foreground">Tool catalog unavailable.</p> : tools.map(tool => {
          const capability = original?.capabilities.find(item => item.id === tool.id);
          const status = capability?.status ?? (!model ? "model_missing" : !model.enabled || model.availability !== "available" ? "model_unavailable" : !model.capabilities.tools ? "model_no_tools" : "pending_check");
          const selected = draft.tool_ids.includes(tool.id);
          return <label key={tool.id} className="flex items-start gap-3 rounded-md border p-3 text-sm"><input type="checkbox" checked={selected} disabled={!canEdit || pending} onChange={event => toggleAssignment("tool_ids", tool.id, event.target.checked)} /><span className="min-w-0 flex-1"><span className="flex flex-wrap items-center gap-2 font-medium"><span>{tool.label}</span><Badge variant={selected && status === "available" ? "secondary" : "outline"}>{selected ? status.replaceAll("_", " ") : "not configured"}</Badge></span><span className="block text-muted-foreground">{tool.description}</span></span></label>;
        })}
      </CardContent></Card>
    </div>
  </div>;
  return <div className={cn("grid min-w-0 gap-6", creating && "xl:grid-cols-[minmax(0,1fr)_320px]")}>
    <form ref={form} onSubmit={event => { event.preventDefault(); void submit(); }} noValidate className="min-w-0">
      <Card>
        <CardHeader><div className="flex items-center justify-between gap-3"><CardTitle>{creating ? ["Basic information", "Choose a model", "Review your agent"][step] : "Agent configuration"}</CardTitle><Badge variant={draft.enabled ? "secondary" : "outline"}>{draft.enabled ? "Enabled" : "Disabled"}</Badge></div>
          <CardDescription>{creating ? "Build a focused agent for your team’s Kubernetes work." : "Shared across this KubePilot installation. Changes are audited."}</CardDescription></CardHeader>
        <CardContent className="flex flex-col gap-6">
          {creating && <ol aria-label="Creation progress" className="flex flex-wrap gap-4">{["Basic information", "Model", "Review"].map((label, index) => <li key={label} aria-current={step === index ? "step" : undefined} className={cn("flex items-center gap-2 text-sm", step === index ? "font-medium text-primary" : "text-muted-foreground")}><span className={cn("flex size-7 items-center justify-center rounded-full", step === index ? "bg-primary text-primary-foreground" : "bg-muted")}>{step > index ? <Check className="size-4" /> : index + 1}</span>{label}</li>)}</ol>}
          {failure && <Alert variant="destructive"><AlertTitle>{denied ? "Access denied" : failure.status === 404 ? "Agent no longer exists" : "Changes not confirmed"}</AlertTitle><AlertDescription>{failure.message}{uncertain && <Button type="button" variant="outline" disabled={pending} onClick={() => void reconcile()}>Refresh stored state</Button>}</AlertDescription></Alert>}
          {notice && <p role="status" className="text-sm text-muted-foreground">{notice}</p>}
          {(!creating || step === 0) && basic}
          {!creating && <Separator />}
          {(!creating || step === 1) && modelFields}
          {(!creating || step === 2) && capabilityFields}
          {creating && step === 2 && <div className="flex flex-col gap-5"><AgentPreview draft={draft} model={model} /><Alert><AlertDescription>Creating this shared definition does not execute an AI request or change your cluster.</AlertDescription></Alert></div>}
          {original && <div className="grid grid-cols-1 gap-3 text-xs text-muted-foreground sm:grid-cols-2"><p>Created {new Date(original.created_at).toLocaleString()}</p><p>Updated {new Date(original.updated_at).toLocaleString()}</p></div>}
        </CardContent>
        <CardFooter className="flex flex-wrap justify-between gap-3">
          {creating ? <Button type="button" variant="outline" disabled={pending} onClick={step ? () => setStep(step - 1) : onCancel}>{step ? <><ArrowLeft data-icon="inline-start" />Back</> : "Cancel"}</Button> : canEdit ?
            <AlertDialog open={deleteOpen} onOpenChange={open => { if (!pending) setDeleteOpen(open); }}><AlertDialogTrigger render={<Button type="button" variant="outline" disabled={pending || uncertain} />}><Trash2 data-icon="inline-start" />Delete agent</AlertDialogTrigger><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>Delete {original.name}?</AlertDialogTitle><AlertDialogDescription>This removes the shared definition for everyone. Audit records are retained. This cannot be undone.</AlertDialogDescription></AlertDialogHeader>{failure && <p role="alert" className="text-sm text-destructive">{failure.message}</p>}<AlertDialogFooter><AlertDialogCancel disabled={pending}>Cancel</AlertDialogCancel><AlertDialogAction variant="destructive" disabled={pending || uncertain || denied} onClick={() => void remove()}>{pending ? "Deleting…" : "Delete agent"}</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog> : <p className="text-sm text-muted-foreground">Only admins can change shared agents.</p>}
          {original?.enabled && onRun && <Button type="button" variant="secondary" disabled={pending || uncertain} onClick={onRun}><Play data-icon="inline-start" />Run in Assistant</Button>}
          {canEdit && <Button type="submit" disabled={pending || uncertain || (!creating && !dirty)}>{pending ? <><LoaderCircle className="animate-spin" data-icon="inline-start" />Saving…</> : creating ? step < 2 ? <>Next<ArrowRight data-icon="inline-end" /></> : "Create agent" : "Save changes"}</Button>}
        </CardFooter>
      </Card>
    </form>
    {creating && <aside className="flex min-w-0 flex-col gap-4"><Card><CardHeader><CardTitle>Preview</CardTitle><CardDescription>Your agent’s identity, as you build it.</CardDescription></CardHeader><CardContent><AgentPreview draft={draft} model={model} /></CardContent></Card><p className="px-2 text-sm leading-relaxed text-muted-foreground">Start with a clear purpose and precise instructions. Skills, capabilities, and agent execution will build on this configuration.</p></aside>}
  </div>;
}

function AgentPreview({ draft, model }: { draft: AgentDraft; model: AgentModel | null | undefined }) {
  return <Agent className="min-w-0 break-words"><AgentHeader name={draft.name || "Your new agent"} /><AgentContent><p className="text-sm leading-relaxed text-muted-foreground">{draft.description || "Add a description to explain how this agent helps your team."}</p><div className="my-4 flex flex-wrap gap-2"><Badge variant="outline">{model?.friendly_name ?? "No model selected"}</Badge><Badge variant="secondary">{draft.enabled ? "Enabled" : "Disabled"}</Badge></div>{draft.instructions && <AgentInstructions className="whitespace-pre-wrap">{draft.instructions}</AgentInstructions>}</AgentContent></Agent>;
}
