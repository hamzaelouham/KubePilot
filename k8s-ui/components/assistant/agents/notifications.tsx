"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Bell, Pencil, RefreshCw, Send, Trash2 } from "lucide-react";
import { z } from "zod";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import {
  agentRequest,
  AgentRequestError,
  notificationDeliverySchema,
  notificationDestinationListSchema,
  notificationDestinationSchema,
  notificationDestinationWriteSchema,
  type NotificationDestination,
  type NotificationDestinationWrite,
} from "@/lib/assistant/agents";

const integrationListSchema = z.object({
  integrations: z.array(z.object({
    provider_id: z.string(),
    name: z.string(),
    supported: z.boolean(),
    status: z.string(),
  })),
});

const providerNames: Record<NotificationDestinationWrite["provider_id"], string> = {
  slack: "Slack",
  gmail: "Gmail",
  outlook: "Microsoft Outlook",
};

const emptyForm: NotificationDestinationWrite = {
  provider_id: "slack",
  label: "",
  destination: "",
  enabled: true,
};

type Props = {
  agentId: string;
  agentEnabled: boolean;
  editable: boolean;
};

type DeliveryState = z.infer<typeof notificationDeliverySchema>;

export function AgentNotifications({ agentId, agentEnabled, editable }: Props) {
  const [destinations, setDestinations] = useState<NotificationDestination[]>([]);
  const [connections, setConnections] = useState<Record<string, { name: string; status: string }>>({});
  const [form, setForm] = useState<NotificationDestinationWrite>(emptyForm);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [lastDelivery, setLastDelivery] = useState<DeliveryState | null>(null);
  const [deliveryRefreshing, setDeliveryRefreshing] = useState(false);
  const [removeTarget, setRemoveTarget] = useState<NotificationDestination | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const destinationResponse = await agentRequest(
        `/api/assistant/agents/${agentId}/notifications`,
        notificationDestinationListSchema,
      );
      setDestinations(destinationResponse.destinations);
      if (editable) {
        const response = await fetch("/api/settings/integrations", { cache: "no-store" });
        const payload: unknown = await response.json().catch(() => null);
        if (!response.ok) {
          throw new AgentRequestError(response.status, "integration_catalog_error", "Connection status could not be loaded.");
        }
        const parsed = integrationListSchema.safeParse(payload);
        if (!parsed.success) throw new AgentRequestError(502, "invalid_response", "Connection status was unexpected.");
        setConnections(Object.fromEntries(parsed.data.integrations.map(item => [item.provider_id, item])));
      }
    } catch (caught) {
      setError(caught instanceof AgentRequestError ? caught.message : "Notification destinations could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [agentId, editable]);

  useEffect(() => { void load(); }, [load]);

  const selectedConnection = useMemo(
    () => connections[form.provider_id],
    [connections, form.provider_id],
  );

  function resetForm() {
    setForm(emptyForm);
    setEditingId(null);
    setFormError(null);
  }

  function edit(destination: NotificationDestination) {
    setEditingId(destination.id);
    setForm({
      provider_id: destination.provider_id,
      label: destination.label,
      destination: "",
      enabled: destination.enabled,
    });
    setFormError(null);
    setNotice(null);
  }

  async function save() {
    const parsed = notificationDestinationWriteSchema.safeParse(form);
    if (!parsed.success) {
      setFormError(parsed.error.issues[0]?.message ?? "Check the destination fields.");
      return;
    }
    setPending(true);
    setFormError(null);
    setNotice(null);
    try {
      const path = editingId
        ? `/api/assistant/agents/${agentId}/notifications/${editingId}`
        : `/api/assistant/agents/${agentId}/notifications`;
      const saved = await agentRequest(
        path,
        notificationDestinationSchema,
        editingId ? "PUT" : "POST",
        parsed.data,
      );
      setDestinations(current => editingId
        ? current.map(item => item.id === saved.id ? saved : item)
        : [...current, saved].sort((a, b) => a.label.localeCompare(b.label)));
      setNotice("Notification destination saved. The target is not shown again.");
      resetForm();
    } catch (caught) {
      setFormError(caught instanceof AgentRequestError ? caught.message : "The destination could not be saved.");
    } finally {
      setPending(false);
    }
  }

  async function remove(destination: NotificationDestination) {
    setPending(true);
    setNotice(null);
    try {
      await agentRequest(
        `/api/assistant/agents/${agentId}/notifications/${destination.id}`,
        z.object({ id: z.string().uuid() }),
        "DELETE",
      );
      setDestinations(current => current.filter(item => item.id !== destination.id));
      if (editingId === destination.id) resetForm();
      setNotice("Notification destination removed.");
    } catch (caught) {
      setError(caught instanceof AgentRequestError ? caught.message : "The destination could not be removed.");
    } finally {
      setPending(false);
    }
  }

  async function sendTest(destination: NotificationDestination) {
    setPending(true);
    setError(null);
    setNotice(null);
    try {
      const delivery = await agentRequest(
        `/api/assistant/agents/${agentId}/notifications/${destination.id}/test`,
        notificationDeliverySchema,
        "POST",
      );
      setLastDelivery(delivery);
      setNotice(`Test notification queued for ${destination.label}.`);
    } catch (caught) {
      setError(caught instanceof AgentRequestError ? caught.message : "The test notification could not be queued.");
    } finally {
      setPending(false);
    }
  }

  async function refreshDelivery() {
    if (!lastDelivery) return;
    setDeliveryRefreshing(true);
    try {
      const response = await fetch(
        `/api/settings/integrations/deliveries/${encodeURIComponent(lastDelivery.delivery_id)}`,
        { cache: "no-store" },
      );
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        throw new AgentRequestError(response.status, "delivery_status_error", "Delivery status could not be refreshed.");
      }
      const parsed = notificationDeliverySchema.safeParse(payload);
      if (!parsed.success) {
        throw new AgentRequestError(502, "invalid_response", "Delivery status was unexpected.");
      }
      setLastDelivery(parsed.data);
      setNotice("Delivery status refreshed.");
    } catch (caught) {
      setError(caught instanceof AgentRequestError ? caught.message : "Delivery status could not be refreshed.");
    } finally {
      setDeliveryRefreshing(false);
    }
  }

  const deliveryRetrying = lastDelivery?.status === "queued" && lastDelivery.attempt_count > 0;
  const deliveryStatusLabel = deliveryRetrying
    ? "retrying"
    : lastDelivery?.status.replaceAll("_", " ");

  const connectionStatus = (destination: NotificationDestination) =>
    connections[destination.provider_id]?.status ?? destination.connection_status;

  return (
    <section aria-labelledby="agent-notifications-heading" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="agent-notifications-heading" className="flex items-center gap-2 text-sm font-semibold">
            <Bell className="size-4" aria-hidden="true" /> Notification destinations
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Shared targets for future agent notifications. Only an explicit administrator test sends a message in this slice.
          </p>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={() => void load()} disabled={loading || pending}>
          <RefreshCw className={loading ? "animate-spin" : ""} data-icon="inline-start" /> Refresh
        </Button>
      </div>
      {error && <Alert variant="destructive"><AlertTitle>Notification destinations unavailable</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}
      {notice && <p role="status" className="text-sm text-muted-foreground">{notice}</p>}
      {lastDelivery && <Alert><AlertTitle>Last test delivery: {deliveryStatusLabel}</AlertTitle><AlertDescription className="flex flex-wrap items-center justify-between gap-2"><span>Delivery {lastDelivery.delivery_id} · {lastDelivery.destination_hint} · Attempt {lastDelivery.attempt_count}/{lastDelivery.max_attempts}</span><Button type="button" variant="outline" size="sm" onClick={() => void refreshDelivery()} disabled={deliveryRefreshing}>{deliveryRefreshing ? "Refreshing…" : "Refresh status"}</Button></AlertDescription></Alert>}
      {loading ? <Card><CardContent className="py-8 text-sm text-muted-foreground">Loading notification destinations…</CardContent></Card> : !destinations.length ? <Card><CardContent className="py-8 text-sm text-muted-foreground">No notification destinations are configured.</CardContent></Card> : <div className="grid gap-3 md:grid-cols-2">
        {destinations.map(destination => {
          const status = connectionStatus(destination);
          const connected = status === "connected";
          return <Card key={destination.id}>
            <CardHeader className="pb-3"><div className="flex items-start justify-between gap-3"><div><CardTitle className="text-base">{destination.label}</CardTitle><CardDescription>{providerNames[destination.provider_id]} · {destination.destination_hint}</CardDescription></div><Badge variant={destination.enabled ? "secondary" : "outline"}>{destination.enabled ? "Enabled" : "Disabled"}</Badge></div></CardHeader>
            <CardContent className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
              <span>Connection: {status.replaceAll("_", " ")}</span>
              {editable && <div className="flex flex-wrap gap-2"><Button type="button" variant="outline" size="sm" onClick={() => void sendTest(destination)} disabled={pending || !destination.enabled || !agentEnabled || !connected}><Send data-icon="inline-start" />Test</Button><Button type="button" variant="ghost" size="sm" onClick={() => edit(destination)} disabled={pending}><Pencil data-icon="inline-start" />Edit</Button><Button type="button" variant="ghost" size="sm" className="text-destructive" onClick={() => setRemoveTarget(destination)} disabled={pending}><Trash2 data-icon="inline-start" />Remove</Button></div>}
            </CardContent>
          </Card>;
        })}
      </div>}
      {editable && <Card>
        <CardHeader><CardTitle className="text-base">{editingId ? "Replace destination" : "Add destination"}</CardTitle><CardDescription>The target is encrypted server-side and is never returned after saving. Connect providers from Settings Integrations.</CardDescription></CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <Field><FieldLabel htmlFor="notification-provider">Provider</FieldLabel><Select value={form.provider_id} onValueChange={value => setForm(current => ({ ...current, provider_id: value as NotificationDestinationWrite["provider_id"] }))} disabled={pending}><SelectTrigger id="notification-provider"><SelectValue /></SelectTrigger><SelectContent>{(Object.keys(providerNames) as NotificationDestinationWrite["provider_id"][]).map(provider => <SelectItem key={provider} value={provider}>{providerNames[provider]}{connections[provider]?.status !== "connected" ? " · not connected" : ""}</SelectItem>)}</SelectContent></Select><FieldDescription>{selectedConnection?.status === "connected" ? "Connected and ready for a test delivery." : "The destination can be saved, but testing requires a connected provider."}</FieldDescription></Field>
          <Field><FieldLabel htmlFor="notification-label">Label</FieldLabel><Input id="notification-label" value={form.label} disabled={pending} onChange={event => setForm(current => ({ ...current, label: event.target.value }))} placeholder="e.g. On-call channel" /></Field>
          <Field className="md:col-span-2"><FieldLabel htmlFor="notification-destination">Destination</FieldLabel><Input id="notification-destination" value={form.destination} disabled={pending} onChange={event => setForm(current => ({ ...current, destination: event.target.value }))} placeholder={form.provider_id === "slack" ? "Slack channel ID, e.g. C123ABC" : "recipient@example.com"} autoComplete="off" /><FieldDescription>{editingId ? "Enter the replacement target; the previous target cannot be recovered in the browser." : "Slack uses a channel ID. Gmail and Outlook use a recipient email address."}</FieldDescription></Field>
          <Field orientation="horizontal" className="md:col-span-2"><div className="flex flex-1 flex-col gap-1"><FieldLabel htmlFor="notification-enabled">Enable destination</FieldLabel><FieldDescription>Disabled destinations remain stored but cannot receive test or future trigger deliveries.</FieldDescription></div><Switch id="notification-enabled" checked={form.enabled} onCheckedChange={enabled => setForm(current => ({ ...current, enabled }))} disabled={pending} /></Field>
          {formError && <FieldError className="md:col-span-2" role="alert">{formError}</FieldError>}
          <div className="flex flex-wrap gap-2 md:col-span-2"><Button type="button" onClick={() => void save()} disabled={pending}>{pending ? "Saving…" : editingId ? "Replace destination" : "Save destination"}</Button>{editingId && <Button type="button" variant="outline" onClick={resetForm} disabled={pending}>Cancel</Button>}</div>
        </CardContent>
      </Card>}
      <AlertDialog open={removeTarget !== null} onOpenChange={open => { if (!open && !pending) setRemoveTarget(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove {removeTarget?.label}?</AlertDialogTitle>
            <AlertDialogDescription>Existing delivery history will remain, but this notification destination will no longer be available to the agent.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={pending}>Cancel</AlertDialogCancel>
            <AlertDialogAction variant="destructive" disabled={pending} onClick={() => { if (!removeTarget) return; const destination = removeTarget; setRemoveTarget(null); void remove(destination); }}>Remove destination</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}
