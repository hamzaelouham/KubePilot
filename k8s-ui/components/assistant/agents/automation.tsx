"use client";

import { useCallback, useEffect, useState } from "react";
import { Pause, Play, Plus, Trash2 } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  agentRequest,
  agentRetentionSchema,
  automationTriggerListSchema,
  automationTriggerSchema,
  automationTriggerWriteSchema,
  notificationDestinationListSchema,
  type AgentRequestError,
  type AutomationTrigger,
  type AutomationTriggerWrite,
  type NotificationDestination,
} from "@/lib/assistant/agents";

type Cluster = { id: string; name: string; status: string };
type Owner = { id: string; email: string; role: string; is_active: boolean };
type State = { status: "loading" } | { status: "ready" } | { status: "error"; message: string };

const emptyTrigger = (ownerId: string, clusterId: string): AutomationTriggerWrite => ({
  trigger_type: "schedule",
  cluster_id: clusterId,
  namespace: null,
  cron_expression: "0 12 * * *",
  timezone: "UTC",
  event_kind: null,
  event_name: null,
  event_type: null,
  event_reason: null,
  owner_id: ownerId,
  notification_destination_ids: [],
  enabled: false,
});

export function AgentAutomation({ agentId, agentEnabled, editable, currentUserId }: { agentId: string; agentEnabled: boolean; editable: boolean; currentUserId: string }) {
  const [state, setState] = useState<State>({ status: "loading" });
  const [triggers, setTriggers] = useState<AutomationTrigger[]>([]);
  const [destinations, setDestinations] = useState<NotificationDestination[]>([]);
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [owners, setOwners] = useState<Owner[]>([]);
  const [retention, setRetention] = useState(30);
  const [draft, setDraft] = useState<AutomationTriggerWrite | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<AgentRequestError | Error | null>(null);
  const [notice, setNotice] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<AutomationTrigger | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    setState({ status: "loading" });
    try {
      const [automation, destinationList, clusterResponse, userResponse, retentionValue] = await Promise.all([
        agentRequest(`/api/assistant/agents/${agentId}/automations`, automationTriggerListSchema, "GET", undefined, signal),
        agentRequest(`/api/assistant/agents/${agentId}/notifications`, notificationDestinationListSchema, "GET", undefined, signal),
        fetch("/api/clusters", { cache: "no-store", signal }).then(async response => response.json() as Promise<{ items: Cluster[] }>),
        fetch("/api/users", { cache: "no-store", signal }).then(async response => response.json() as Promise<{ items: Owner[] }>),
        agentRequest("/api/assistant/agents/automation/retention", agentRetentionSchema, "GET", undefined, signal),
      ]);
      setTriggers(automation.triggers);
      setDestinations(destinationList.destinations);
      setClusters((clusterResponse.items ?? []).filter(item => item.status === "active"));
      setOwners((userResponse.items ?? []).filter(item => item.is_active && item.role !== "viewer"));
      setRetention(retentionValue.retention_days);
      setState({ status: "ready" });
    } catch (error) {
      if (signal?.aborted) return;
      setFailure(error instanceof Error ? error : new Error("Unable to load automation settings."));
      setState({ status: "error", message: error instanceof Error ? error.message : "Unable to load automation settings." });
    }
  }, [agentId]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const openNew = () => {
    setFailure(null);
    setNotice("");
    setEditingId(null);
    setDraft(emptyTrigger(currentUserId, clusters[0]?.id ?? ""));
  };
  const openEdit = (trigger: AutomationTrigger) => {
    setFailure(null);
    setNotice("");
    setEditingId(trigger.id);
    setDraft({ ...trigger });
  };
  const update = <K extends keyof AutomationTriggerWrite>(key: K, value: AutomationTriggerWrite[K]) => {
    setDraft(current => current ? { ...current, [key]: value } : current);
  };
  const save = async () => {
    if (!draft) return;
    setPending(true);
    setFailure(null);
    setNotice("");
    const parsed = automationTriggerWriteSchema.safeParse(draft);
    if (!parsed.success || (draft.trigger_type === "schedule" && !draft.cron_expression?.trim())) {
      setFailure(new Error("Choose a valid trigger definition before saving."));
      setPending(false);
      return;
    }
    try {
      const saved = await agentRequest(
        editingId ? `/api/assistant/agents/${agentId}/automations/${editingId}` : `/api/assistant/agents/${agentId}/automations`,
        automationTriggerSchema,
        editingId ? "PUT" : "POST",
        parsed.data,
      );
      setTriggers(current => editingId ? current.map(item => item.id === saved.id ? saved : item) : [saved, ...current]);
      setDraft(null);
      setNotice("Automation trigger saved.");
    } catch (error) {
      setFailure(error instanceof Error ? error : new Error("Automation trigger could not be saved."));
    } finally {
      setPending(false);
    }
  };
  const toggle = async (trigger: AutomationTrigger) => {
    const body: AutomationTriggerWrite = { ...trigger, enabled: !trigger.enabled };
    setPending(true);
    setFailure(null);
    try {
      const saved = await agentRequest(`/api/assistant/agents/${agentId}/automations/${trigger.id}`, automationTriggerSchema, "PUT", body);
      setTriggers(current => current.map(item => item.id === saved.id ? saved : item));
      setNotice(saved.enabled ? "Automation resumed." : "Automation paused.");
    } catch (error) {
      setFailure(error instanceof Error ? error : new Error("Automation state could not be changed."));
    } finally {
      setPending(false);
    }
  };
  const remove = async (trigger: AutomationTrigger) => {
    setPending(true);
    try {
      await agentRequest(`/api/assistant/agents/${agentId}/automations/${trigger.id}`, automationTriggerSchema.pick({ id: true }), "DELETE");
      setTriggers(current => current.filter(item => item.id !== trigger.id));
      setNotice("Automation removed.");
    } catch (error) {
      setFailure(error instanceof Error ? error : new Error("Automation could not be removed."));
    } finally {
      setPending(false);
    }
  };
  const saveRetention = async () => {
    try {
      await agentRequest("/api/assistant/agents/automation/retention", agentRetentionSchema, "PUT", { retention_days: retention });
      setNotice("Run retention saved.");
    } catch (error) {
      setFailure(error instanceof Error ? error : new Error("Run retention could not be saved."));
    }
  };

  if (!editable) return null;
  if (state.status === "loading") return <Card><CardContent className="p-6 text-sm text-muted-foreground">Loading automation settings…</CardContent></Card>;
  if (state.status === "error") return <Alert variant="destructive"><AlertTitle>Automation unavailable</AlertTitle><AlertDescription>{state.message}</AlertDescription></Alert>;

  return <Card>
    <CardHeader className="flex-row items-start justify-between gap-4"><div><CardTitle>Schedules and events</CardTitle><CardDescription>Run this agent automatically for read-only investigation and configured notifications. Resource changes always require the Assistant approval flow.</CardDescription></div><Button type="button" variant="outline" size="sm" onClick={openNew} disabled={pending || !agentEnabled || !clusters.length}><Plus data-icon="inline-start" />Add trigger</Button></CardHeader>
    <CardContent className="flex flex-col gap-5">
      {!agentEnabled && <Alert><AlertTitle>Enable the agent first</AlertTitle><AlertDescription>Paused automation cannot run while this agent is disabled.</AlertDescription></Alert>}
      {failure && <Alert variant="destructive"><AlertTitle>Automation update failed</AlertTitle><AlertDescription>{failure.message}</AlertDescription></Alert>}
      {notice && <p role="status" className="text-sm text-muted-foreground">{notice}</p>}
      <div className="rounded-lg border p-4"><div className="flex flex-wrap items-end justify-between gap-3"><div><p className="font-medium">Run retention</p><p className="text-sm text-muted-foreground">Terminal agent runs and bounded logs are kept for this many days.</p></div><div className="flex items-center gap-2"><Input aria-label="Run retention days" type="number" min={1} max={365} value={retention} onChange={event => setRetention(Number(event.target.value))} className="w-24" /><span className="text-sm text-muted-foreground">days</span><Button type="button" variant="outline" size="sm" onClick={() => void saveRetention()} disabled={pending || retention < 1 || retention > 365}>Save</Button></div></div></div>
      {draft && <div className="rounded-lg border border-primary/30 bg-primary/5 p-4"><div className="mb-4 flex items-center justify-between gap-3"><div><p className="font-medium">{editingId ? "Edit trigger" : "New trigger"}</p><p className="text-sm text-muted-foreground">Five-field cron example: <code>0 12 * * *</code>.</p></div><Badge variant={draft.enabled ? "secondary" : "outline"}>{draft.enabled ? "Enabled" : "Paused"}</Badge></div><div className="grid gap-4 md:grid-cols-2">
        <label className="grid gap-2 text-sm font-medium">Trigger type<select className="h-9 rounded-md border bg-background px-3 font-normal" value={draft.trigger_type} onChange={event => update("trigger_type", event.target.value as AutomationTriggerWrite["trigger_type"])}><option value="schedule">Schedule</option><option value="kubernetes_event">Kubernetes event</option></select></label>
        <label className="grid gap-2 text-sm font-medium">Cluster<select className="h-9 rounded-md border bg-background px-3 font-normal" value={draft.cluster_id} onChange={event => update("cluster_id", event.target.value)}>{clusters.map(cluster => <option key={cluster.id} value={cluster.id}>{cluster.name}</option>)}</select></label>
        <label className="grid gap-2 text-sm font-medium">Namespace <span className="font-normal text-muted-foreground">optional</span><Input value={draft.namespace ?? ""} onChange={event => update("namespace", event.target.value || null)} placeholder="production" /></label>
        <label className="grid gap-2 text-sm font-medium">Designated owner<select className="h-9 rounded-md border bg-background px-3 font-normal" value={draft.owner_id} onChange={event => update("owner_id", event.target.value)}>{owners.map(owner => <option key={owner.id} value={owner.id}>{owner.email} · {owner.role}</option>)}</select></label>
        {draft.trigger_type === "schedule" ? <><label className="grid gap-2 text-sm font-medium">Cron expression<Input value={draft.cron_expression ?? ""} onChange={event => update("cron_expression", event.target.value || null)} placeholder="0 12 * * *" /></label><label className="grid gap-2 text-sm font-medium">Timezone<Input value={draft.timezone} onChange={event => update("timezone", event.target.value)} placeholder="Africa/Casablanca" /></label></> : <><label className="grid gap-2 text-sm font-medium">Event kind <Input value={draft.event_kind ?? ""} onChange={event => update("event_kind", event.target.value || null)} placeholder="Pod" /></label><label className="grid gap-2 text-sm font-medium">Event reason <Input value={draft.event_reason ?? ""} onChange={event => update("event_reason", event.target.value || null)} placeholder="BackOff" /></label><label className="grid gap-2 text-sm font-medium">Event name <Input value={draft.event_name ?? ""} onChange={event => update("event_name", event.target.value || null)} placeholder="optional-pod-name" /></label><label className="grid gap-2 text-sm font-medium">Event type <Input value={draft.event_type ?? ""} onChange={event => update("event_type", event.target.value || null)} placeholder="Warning" /></label></>}
        <div className="md:col-span-2"><p className="mb-2 text-sm font-medium">Notification destinations</p><div className="grid gap-2 sm:grid-cols-2">{destinations.map(destination => <label key={destination.id} className="flex items-start gap-2 rounded-md border p-3 text-sm"><input type="checkbox" checked={draft.notification_destination_ids.includes(destination.id)} disabled={!destination.enabled || destination.connection_status !== "connected"} onChange={event => update("notification_destination_ids", event.target.checked ? [...draft.notification_destination_ids, destination.id] : draft.notification_destination_ids.filter(id => id !== destination.id))} /><span><span className="block font-medium">{destination.label}</span><span className="block text-xs text-muted-foreground">{destination.provider_id} · {destination.connection_status}</span></span></label>)}{!destinations.length && <p className="text-sm text-muted-foreground">Configure a notification destination above before enabling a trigger.</p>}</div><p className="mt-2 text-xs text-muted-foreground">Only enabled, connected destinations can receive unattended reports.</p></div>
        <label className="flex items-center gap-2 text-sm md:col-span-2"><input type="checkbox" checked={draft.enabled} disabled={!agentEnabled || !draft.notification_destination_ids.length} onChange={event => update("enabled", event.target.checked)} />Enable trigger</label>
      </div><div className="mt-4 flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setDraft(null)} disabled={pending}>Cancel</Button><Button type="button" onClick={() => void save()} disabled={pending || !draft.cluster_id || !draft.owner_id}>{pending ? "Saving…" : "Save trigger"}</Button></div></div>}
      {triggers.length === 0 && !draft ? <p className="rounded-lg border border-dashed p-5 text-sm text-muted-foreground">No automated triggers configured. Add a schedule to check workload health and notify Slack.</p> : <div className="grid gap-3">{triggers.map(trigger => <div key={trigger.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-4"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><p className="font-medium">{trigger.trigger_type === "schedule" ? trigger.cron_expression : "Kubernetes event"}</p><Badge variant={trigger.enabled ? "secondary" : "outline"}>{trigger.enabled ? "Enabled" : "Paused"}</Badge></div><p className="mt-1 text-sm text-muted-foreground">{trigger.trigger_type === "schedule" ? trigger.timezone : [trigger.event_type, trigger.event_reason, trigger.event_kind].filter(Boolean).join(" · ") || "Any matching event"} · {clusters.find(cluster => cluster.id === trigger.cluster_id)?.name ?? "Cluster unavailable"}</p></div><div className="flex items-center gap-2"><Button type="button" variant="outline" size="sm" onClick={() => void toggle(trigger)} disabled={pending || (!trigger.enabled && !agentEnabled)}>{trigger.enabled ? <Pause data-icon="inline-start" /> : <Play data-icon="inline-start" />}{trigger.enabled ? "Pause" : "Resume"}</Button><Button type="button" variant="outline" size="sm" onClick={() => openEdit(trigger)} disabled={pending}>Edit</Button><Button type="button" variant="ghost" size="icon-sm" aria-label={`Remove ${trigger.trigger_type} trigger`} onClick={() => setDeleteTarget(trigger)} disabled={pending}><Trash2 /></Button></div></div>)}</div>}
    </CardContent>
    <AlertDialog open={deleteTarget !== null} onOpenChange={open => { if (!open && !pending) setDeleteTarget(null); }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Remove automation trigger?</AlertDialogTitle>
          <AlertDialogDescription>Existing run history will be retained, but this trigger will no longer run.</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={pending}>Cancel</AlertDialogCancel>
          <AlertDialogAction variant="destructive" disabled={pending} onClick={() => { if (!deleteTarget) return; const trigger = deleteTarget; setDeleteTarget(null); void remove(trigger); }}>Remove trigger</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </Card>;
}
