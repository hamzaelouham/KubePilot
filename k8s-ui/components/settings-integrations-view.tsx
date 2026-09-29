"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { LucideIcon } from "lucide-react";
import {
  Blocks,
  BookOpen,
  CheckCircle2,
  Clock,
  CircleAlert,
  GitBranch,
  Info,
  Mail,
  MessageSquare,
  Search,
  ShieldCheck,
  Sparkles,
  RefreshCw,
  Users,
  Webhook,
} from "lucide-react";
import { cn } from "cn";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

type Category = "All" | "Notifications" | "Communication" | "Source Control" | "Automation";
type ConnectionStatus = "not_connected" | "authorizing" | "connected" | "error" | "revoked" | "not_supported";
type Action = "connect" | "test" | "disconnect" | "learn";

type Integration = {
  id: string;
  name: string;
  category: Exclude<Category, "All">;
  description: string;
  securityHint: string;
  icon: LucideIcon;
  iconClassName: string;
  iconBackground: string;
};

type IntegrationState = {
  provider_id: string;
  name: string;
  supported: boolean;
  configured: boolean;
  status: ConnectionStatus;
  external_account_label: string | null;
  granted_scopes: string[];
  last_tested_at: string | null;
  last_error_code: string | null;
};

type DeliveryStatus = "queued" | "running" | "succeeded" | "failed" | "outcome_unknown";

type DeliveryItem = {
  delivery_id: string;
  provider_id: string;
  event_type: string;
  destination_hint: string;
  status: DeliveryStatus;
  attempt_count: number;
  max_attempts: number;
  next_attempt_at: string;
  last_error_code: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
};

const categories: Category[] = ["All", "Notifications", "Communication", "Source Control", "Automation"];

const integrations: Integration[] = [
  {
    id: "slack",
    name: "Slack",
    category: "Communication",
    description: "Send alerts, notifications and updates to Slack channels.",
    securityHint: "Uses scoped OAuth 2.0",
    icon: MessageSquare,
    iconClassName: "text-[#36c5f0]",
    iconBackground: "bg-[#e8f8fc]",
  },
  {
    id: "github",
    name: "GitHub",
    category: "Source Control",
    description: "Integrate with GitHub for automation and notifications.",
    securityHint: "Connector contract planned",
    icon: GitBranch,
    iconClassName: "text-foreground",
    iconBackground: "bg-muted",
  },
  {
    id: "teams",
    name: "Microsoft Teams",
    category: "Communication",
    description: "Send alerts and messages to Teams channels.",
    securityHint: "Connector contract planned",
    icon: Users,
    iconClassName: "text-[#6264a7]",
    iconBackground: "bg-[#efefff]",
  },
  {
    id: "gmail",
    name: "Gmail",
    category: "Notifications",
    description: "Send email notifications and reports.",
    securityHint: "Uses scoped OAuth 2.0",
    icon: Mail,
    iconClassName: "text-[#ea4335]",
    iconBackground: "bg-[#fff0ee]",
  },
  {
    id: "outlook",
    name: "Microsoft Outlook",
    category: "Notifications",
    description: "Send email notifications using Microsoft 365.",
    securityHint: "Uses scoped OAuth 2.0",
    icon: Mail,
    iconClassName: "text-[#0078d4]",
    iconBackground: "bg-[#eaf5ff]",
  },
  {
    id: "webhooks",
    name: "Webhooks",
    category: "Automation",
    description: "Send events to custom webhook endpoints.",
    securityHint: "Connector contract planned",
    icon: Webhook,
    iconClassName: "text-[#e91e63]",
    iconBackground: "bg-[#fff0f6]",
  },
];

function StatusBadge({ state, loaded }: { state?: IntegrationState; loaded: boolean }) {
  const connected = state?.status === "connected";
  const label = !loaded
    ? "Loading"
    : !state?.supported
      ? "Coming soon"
      : !state.configured
        ? "Needs credentials"
        : state.status === "error"
          ? "Needs attention"
          : state.status === "revoked"
            ? "Disconnected"
            : connected
              ? "Connected"
              : "Not connected";

  return (
    <Badge variant={connected ? "secondary" : "outline"} className={connected ? "text-emerald-700 dark:text-emerald-300" : "text-muted-foreground"}>
      <span className={cn("size-1.5 rounded-full", connected ? "bg-emerald-600" : "bg-muted-foreground/50")} aria-hidden="true" />
      {label}
    </Badge>
  );
}

function IntegrationCard({
  integration,
  state,
  loaded,
  busy,
  onAction,
}: {
  integration: Integration;
  state?: IntegrationState;
  loaded: boolean;
  busy: boolean;
  onAction: (integration: Integration, action: Action) => void;
}) {
  const Icon = integration.icon;
  const connected = state?.status === "connected";
  const supported = state?.supported ?? (integration.id === "slack" || integration.id === "gmail" || integration.id === "outlook");
  const configured = state?.configured ?? false;

  return (
    <Card className="h-full">
      <CardContent className="flex h-full min-w-0 items-start gap-4 p-4">
        <div className={cn("flex size-12 shrink-0 items-center justify-center rounded-xl", integration.iconBackground)} aria-hidden="true">
          <Icon className={cn("size-7", integration.iconClassName)} strokeWidth={1.8} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-heading text-base font-semibold text-foreground">{integration.name}</h3>
            <StatusBadge state={state} loaded={loaded} />
          </div>
          <p className="mt-2 max-w-sm text-sm leading-5 text-muted-foreground">{integration.description}</p>
          {state?.external_account_label ? (
            <p className="mt-2 truncate text-xs text-foreground" title={state.external_account_label}>
              Connected account: {state.external_account_label}
            </p>
          ) : null}
          <p className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground">
            <ShieldCheck className="size-3.5 text-primary" aria-hidden="true" />
            {integration.securityHint}
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-2">
          {!loaded || busy ? (
            <Button type="button" variant="outline" size="sm" disabled>
              {busy ? "Working…" : "Loading…"}
            </Button>
          ) : !supported ? (
            <Button type="button" variant="outline" size="sm" disabled>
              Coming soon
            </Button>
          ) : connected ? (
            <>
              <Button type="button" variant="outline" size="sm" onClick={() => onAction(integration, "test")}>
                Test connection
              </Button>
              <Button type="button" variant="link" size="sm" className="h-6 px-1 text-destructive" onClick={() => onAction(integration, "disconnect")}>
                Disconnect
              </Button>
            </>
          ) : (
            <Button type="button" variant={configured ? "default" : "outline"} size="sm" onClick={() => onAction(integration, configured ? "connect" : "learn")}>
              {configured ? "Connect" : "Configure credentials"}
            </Button>
          )}
          {!supported || connected || !loaded ? null : (
            <Button type="button" variant="link" size="sm" className="h-6 px-1" onClick={() => onAction(integration, "learn")}>
              Learn more
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export function SettingsIntegrationsView() {
  const [category, setCategory] = useState<Category>("All");
  const [query, setQuery] = useState("");
  const [states, setStates] = useState<Record<string, IntegrationState>>({});
  const [loaded, setLoaded] = useState(false);
  const [loadingError, setLoadingError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(() => callbackNoticeFromLocation());
  const [busyProvider, setBusyProvider] = useState<string | null>(null);
  const [deliveries, setDeliveries] = useState<DeliveryItem[]>([]);
  const [deliveryLoading, setDeliveryLoading] = useState(true);
  const [deliveryError, setDeliveryError] = useState<string | null>(null);
  const [retryingDelivery, setRetryingDelivery] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/settings/integrations", { cache: "no-store" })
      .then(async (response) => {
        const payload = await response.json().catch(() => null);
        if (!response.ok) throw new Error(safeErrorMessage(payload, "The integration catalog could not be loaded"));
        return payload;
      })
      .then((payload) => {
        if (cancelled) return;
        const nextStates = Object.fromEntries(
          (payload.integrations ?? []).map((item: IntegrationState) => [item.provider_id, item]),
        ) as Record<string, IntegrationState>;
        setStates(nextStates);
        setLoaded(true);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setLoadingError(error instanceof Error ? error.message : "The integration catalog could not be loaded");
        setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const loadDeliveries = useCallback(async () => {
    setDeliveryLoading(true);
    setDeliveryError(null);
    try {
      const response = await fetch("/api/settings/integrations/deliveries?limit=20", { cache: "no-store" });
      const payload = await response.json().catch(() => null);
      if (!response.ok) throw new Error(safeErrorMessage(payload, "The delivery history could not be loaded"));
      setDeliveries((payload.items ?? []) as DeliveryItem[]);
    } catch (error: unknown) {
      setDeliveryError(error instanceof Error ? error.message : "The delivery history could not be loaded");
    } finally {
      setDeliveryLoading(false);
    }
  }, []);

  useEffect(() => {
    const task = Promise.resolve().then(() => loadDeliveries());
    return () => {
      void task.catch(() => undefined);
    };
  }, [loadDeliveries]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const connection = params.get("connection");
    if (connection) window.history.replaceState({}, "", window.location.pathname);
  }, []);

  const filteredIntegrations = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return integrations.filter((integration) => {
      const matchesCategory = category === "All" || integration.category === category;
      const matchesQuery = !normalizedQuery || `${integration.name} ${integration.category} ${integration.description}`.toLowerCase().includes(normalizedQuery);
      return matchesCategory && matchesQuery;
    });
  }, [category, query]);

  const connectedIntegrations = filteredIntegrations.filter((integration) => states[integration.id]?.status === "connected");
  const availableIntegrations = filteredIntegrations.filter((integration) => states[integration.id]?.status !== "connected");

  async function handleAction(integration: Integration, action: Action) {
    if (action === "learn") {
      setNotice(integration.id === "teams" || integration.id === "github" || integration.id === "webhooks"
        ? `${integration.name} is cataloged for a future connector contract.`
        : `Configure the ${integration.name} OAuth application credentials in Settings Credentials before connecting.`);
      return;
    }
    setBusyProvider(integration.id);
    try {
      const response = await fetch(
        action === "connect"
          ? `/api/settings/integrations/${integration.id}/authorize`
          : action === "test"
            ? `/api/settings/integrations/${integration.id}/test`
            : `/api/settings/integrations/${integration.id}`,
        { method: action === "disconnect" ? "DELETE" : "POST", cache: "no-store" },
      );
      const payload = await response.json().catch(() => null);
      if (!response.ok) throw new Error(safeErrorMessage(payload, `The ${integration.name} action failed`));
      if (action === "connect" && typeof payload.authorization_url === "string") {
        window.location.assign(payload.authorization_url);
        return;
      }
      if (payload.provider_id) {
        setStates((current) => ({ ...current, [payload.provider_id]: payload }));
      }
      setNotice(action === "test" ? `${integration.name} connection test succeeded.` : `${integration.name} was disconnected.`);
      void loadDeliveries();
    } catch (error: unknown) {
      setNotice(error instanceof Error ? error.message : `The ${integration.name} action failed`);
    } finally {
      setBusyProvider(null);
    }
  }

  function renderSection(title: string, description: string, items: Integration[], emptyMessage: string) {
    return (
      <section aria-labelledby={`${title.toLowerCase().replaceAll(" ", "-")}-heading`} className="space-y-3">
        <div>
          <h2 id={`${title.toLowerCase().replaceAll(" ", "-")}-heading`} className="font-heading text-lg font-semibold text-foreground">{title} ({items.length})</h2>
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        </div>
        {items.length ? (
          <div className="grid gap-4 xl:grid-cols-2">
            {items.map((integration) => (
              <IntegrationCard key={integration.id} integration={integration} state={states[integration.id]} loaded={loaded} busy={busyProvider === integration.id} onAction={handleAction} />
            ))}
          </div>
        ) : (
          <Card>
            <CardContent className="py-8 text-center text-sm text-muted-foreground">{emptyMessage}</CardContent>
          </Card>
        )}
      </section>
    );
  }

  async function retryDelivery(deliveryId: string) {
    setRetryingDelivery(deliveryId);
    try {
      const response = await fetch(`/api/settings/integrations/deliveries/${encodeURIComponent(deliveryId)}/retry`, {
        method: "POST",
        cache: "no-store",
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) throw new Error(safeErrorMessage(payload, "The delivery could not be retried"));
      setNotice("The delivery was queued for retry.");
      await loadDeliveries();
    } catch (error: unknown) {
      setNotice(error instanceof Error ? error.message : "The delivery could not be retried");
    } finally {
      setRetryingDelivery(null);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex size-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary" aria-hidden="true">
            <Blocks className="size-6" />
          </div>
          <div>
            <h2 className="font-heading text-2xl font-semibold tracking-tight text-foreground">Integrations</h2>
            <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">Connect KubePilot with external services for notifications, communication, and automation.</p>
            <p className="mt-3 flex max-w-2xl items-start gap-2 text-xs leading-5 text-muted-foreground">
              <Info className="mt-0.5 size-3.5 shrink-0 text-primary" aria-hidden="true" />
              <span>Connection and delivery status are managed by the backend. Message content and credentials never reach the browser.</span>
            </p>
          </div>
        </div>
        <Button type="button" variant="outline" onClick={() => setNotice("Integration documentation will be linked here when the first connector is shipped.")}>
          <BookOpen data-icon="inline-start" />
          View documentation
        </Button>
      </div>

      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex flex-wrap gap-2" role="group" aria-label="Filter integrations by category">
          {categories.map((item) => (
            <Button key={item} type="button" variant={category === item ? "default" : "outline"} size="sm" aria-pressed={category === item} onClick={() => setCategory(item)}>
              {item}
            </Button>
          ))}
        </div>
        <div className="relative w-full xl:max-w-xs">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search integrations…" aria-label="Search integrations" className="pl-9" />
        </div>
      </div>

      {loadingError ? (
        <div role="alert" className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <span>{loadingError}</span>
        </div>
      ) : null}

      {notice ? (
        <div role="status" aria-live="polite" className="flex items-start gap-2 rounded-lg border border-primary/20 bg-primary/5 px-4 py-3 text-sm text-muted-foreground">
          <Info className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
          <span>{notice}</span>
        </div>
      ) : null}

      {renderSection("Connected", "Services that are currently connected to your KubePilot environment.", connectedIntegrations, loaded ? "No connected integrations match the current filters." : "Loading connection status…")}
      {renderSection("Available integrations", "Connect additional services to extend KubePilot’s capabilities.", availableIntegrations, "No available integrations match the current filters.")}

      <section aria-labelledby="delivery-history-heading" className="space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 id="delivery-history-heading" className="font-heading text-lg font-semibold text-foreground">Delivery activity</h2>
            <p className="mt-1 text-sm text-muted-foreground">Recent notification delivery status without message content or provider secrets.</p>
          </div>
          <Button type="button" variant="outline" size="sm" onClick={() => void loadDeliveries()} disabled={deliveryLoading}>
            <RefreshCw className={cn("size-4", deliveryLoading && "animate-spin")} data-icon="inline-start" />
            Refresh
          </Button>
        </div>
        {deliveryError ? (
          <div role="alert" className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
            <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            <span>{deliveryError}</span>
          </div>
        ) : deliveryLoading ? (
          <Card aria-busy="true"><CardContent className="flex items-center gap-2 py-8 text-sm text-muted-foreground"><Clock className="size-4 animate-pulse" aria-hidden="true" />Loading delivery history…</CardContent></Card>
        ) : deliveries.length === 0 ? (
          <Card><CardContent className="py-8 text-center text-sm text-muted-foreground">No deliveries have been queued.</CardContent></Card>
        ) : (
          <div className="space-y-2">
            {deliveries.map((delivery) => (
              <Card key={delivery.delivery_id}>
                <CardContent className="flex flex-wrap items-center gap-3 p-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium text-foreground">{providerName(delivery.provider_id)}</span>
                      <DeliveryStatusBadge status={delivery.status} retrying={delivery.status === "queued" && delivery.attempt_count > 0} />
                    </div>
                    <p className="mt-1 truncate text-sm text-muted-foreground">{delivery.event_type} · {delivery.destination_hint}</p>
                    <p className="mt-1 text-xs text-muted-foreground">Attempt {delivery.attempt_count}/{delivery.max_attempts} · {formatDate(delivery.created_at)}{delivery.last_error_code ? ` · ${delivery.last_error_code}` : ""}</p>
                  </div>
                  {delivery.status === "failed" ? (
                    <Button type="button" variant="outline" size="sm" onClick={() => void retryDelivery(delivery.delivery_id)} disabled={retryingDelivery === delivery.delivery_id}>
                      {retryingDelivery === delivery.delivery_id ? "Retrying…" : "Retry"}
                    </Button>
                  ) : null}
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>

      <Card className="border-primary/20 bg-primary/5">
        <CardHeader className="flex-row items-center gap-3 space-y-0">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary" aria-hidden="true">
            <Sparkles className="size-5" />
          </div>
          <div>
            <CardTitle className="text-base">Looking for more integrations?</CardTitle>
            <CardDescription className="mt-1">More connectors can be added as KubePilot’s notification and automation workflows grow.</CardDescription>
          </div>
          <Button type="button" variant="outline" size="sm" className="ml-auto" onClick={() => setNotice("Tell the KubePilot team which service should be supported next.")}>
            Request an integration
          </Button>
        </CardHeader>
      </Card>

      {filteredIntegrations.length === 0 ? (
        <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
          <CircleAlert className="size-4" aria-hidden="true" />
          Try a different search or category.
        </div>
      ) : null}

      <div className="sr-only" aria-live="polite">
        <CheckCircle2 aria-hidden="true" />
        {connectedIntegrations.length} connected integrations shown.
      </div>
    </div>
  );
}

function safeErrorMessage(payload: unknown, fallback: string): string {
  if (typeof payload === "object" && payload !== null && "detail" in payload) {
    const detail = payload.detail;
    if (typeof detail === "object" && detail !== null && "message" in detail && typeof detail.message === "string") {
      return detail.message;
    }
  }
  return fallback;
}

function DeliveryStatusBadge({ status, retrying }: { status: DeliveryStatus; retrying: boolean }) {
  const label = status === "outcome_unknown" ? "Outcome unknown" : retrying ? "Retrying" : status[0].toUpperCase() + status.slice(1);
  const className = status === "succeeded"
    ? "text-emerald-700 dark:text-emerald-300"
    : status === "failed" || status === "outcome_unknown"
      ? "text-destructive"
      : "text-muted-foreground";
  return <Badge variant={status === "succeeded" ? "secondary" : "outline"} className={className}>{label}</Badge>;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function providerName(provider: string): string {
  return integrations.find((integration) => integration.id === provider)?.name ?? provider;
}

function callbackNoticeFromLocation(): string | null {
  if (typeof window === "undefined") return null;
  const params = new URLSearchParams(window.location.search);
  const connection = params.get("connection");
  const provider = params.get("provider");
  const errorCode = params.get("error");
  if (connection === "connected" && provider) {
    return `${providerName(provider)} is connected. Delivery workflows will be added separately.`;
  }
  if (connection === "error") {
    return `The ${providerName(provider ?? "integration")} connection could not be completed${errorCode ? ` (${errorCode})` : ""}.`;
  }
  if (connection === "backend_unavailable") return "The integration service is unavailable. Try again later.";
  return null;
}
