"use client";

import { useMemo, useState } from "react";
import type { LucideIcon } from "lucide-react";
import {
  Blocks,
  BookOpen,
  CheckCircle2,
  CircleAlert,
  GitBranch,
  Info,
  Mail,
  MessageSquare,
  Search,
  ShieldCheck,
  Sparkles,
  Users,
  Webhook,
} from "lucide-react";
import { cn } from "cn";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

type Category = "All" | "Notifications" | "Communication" | "Source Control" | "Automation";

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

const categories: Category[] = ["All", "Notifications", "Communication", "Source Control", "Automation"];

const integrations: Integration[] = [
  {
    id: "slack",
    name: "Slack",
    category: "Communication",
    description: "Send alerts, notifications and updates to Slack channels.",
    securityHint: "Uses secure OAuth 2.0",
    icon: MessageSquare,
    iconClassName: "text-[#36c5f0]",
    iconBackground: "bg-[#e8f8fc]",
  },
  {
    id: "github",
    name: "GitHub",
    category: "Source Control",
    description: "Integrate with GitHub for automation and notifications.",
    securityHint: "Uses secure OAuth 2.0",
    icon: GitBranch,
    iconClassName: "text-foreground",
    iconBackground: "bg-muted",
  },
  {
    id: "teams",
    name: "Microsoft Teams",
    category: "Communication",
    description: "Send alerts and messages to Teams channels.",
    securityHint: "Uses secure OAuth 2.0",
    icon: Users,
    iconClassName: "text-[#6264a7]",
    iconBackground: "bg-[#efefff]",
  },
  {
    id: "gmail",
    name: "Gmail",
    category: "Notifications",
    description: "Send email notifications and reports.",
    securityHint: "Uses secure OAuth 2.0",
    icon: Mail,
    iconClassName: "text-[#ea4335]",
    iconBackground: "bg-[#fff0ee]",
  },
  {
    id: "outlook",
    name: "Microsoft Outlook",
    category: "Notifications",
    description: "Send email notifications using Microsoft 365.",
    securityHint: "Uses secure OAuth 2.0",
    icon: Mail,
    iconClassName: "text-[#0078d4]",
    iconBackground: "bg-[#eaf5ff]",
  },
  {
    id: "webhooks",
    name: "Webhooks",
    category: "Automation",
    description: "Send events to custom webhook endpoints.",
    securityHint: "Supports HMAC signatures",
    icon: Webhook,
    iconClassName: "text-[#e91e63]",
    iconBackground: "bg-[#fff0f6]",
  },
];

const initialConnections: Record<string, boolean> = {
  slack: true,
  github: true,
};

function StatusBadge({ connected }: { connected: boolean }) {
  return (
    <Badge variant={connected ? "secondary" : "outline"} className={connected ? "text-emerald-700 dark:text-emerald-300" : "text-muted-foreground"}>
      <span className={cn("size-1.5 rounded-full", connected ? "bg-emerald-600" : "bg-muted-foreground/50")} aria-hidden="true" />
      {connected ? "Connected" : "Not connected"}
    </Badge>
  );
}

function IntegrationCard({
  integration,
  connected,
  onAction,
}: {
  integration: Integration;
  connected: boolean;
  onAction: (integration: Integration, action: "connect" | "manage" | "learn") => void;
}) {
  const Icon = integration.icon;

  return (
    <Card className="h-full">
      <CardContent className="flex h-full min-w-0 items-start gap-4 p-4">
        <div className={cn("flex size-12 shrink-0 items-center justify-center rounded-xl", integration.iconBackground)} aria-hidden="true">
          <Icon className={cn("size-7", integration.iconClassName)} strokeWidth={1.8} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-heading text-base font-semibold text-foreground">{integration.name}</h3>
            <StatusBadge connected={connected} />
          </div>
          <p className="mt-2 max-w-sm text-sm leading-5 text-muted-foreground">{integration.description}</p>
          <p className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground">
            <ShieldCheck className="size-3.5 text-primary" aria-hidden="true" />
            {integration.securityHint}
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-2">
          <Button type="button" variant={connected ? "outline" : "default"} size="sm" onClick={() => onAction(integration, connected ? "manage" : "connect")}>
            {connected ? "Manage" : "Connect"}
          </Button>
          {!connected ? (
            <Button type="button" variant="link" size="sm" className="h-6 px-1" onClick={() => onAction(integration, "learn")}>
              Learn more
            </Button>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}

export function SettingsIntegrationsView() {
  const [category, setCategory] = useState<Category>("All");
  const [query, setQuery] = useState("");
  const [connections, setConnections] = useState(initialConnections);
  const [notice, setNotice] = useState<string | null>(null);

  const filteredIntegrations = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return integrations.filter((integration) => {
      const matchesCategory = category === "All" || integration.category === category;
      const matchesQuery = !normalizedQuery || `${integration.name} ${integration.category} ${integration.description}`.toLowerCase().includes(normalizedQuery);
      return matchesCategory && matchesQuery;
    });
  }, [category, query]);

  const connectedIntegrations = filteredIntegrations.filter((integration) => connections[integration.id]);
  const availableIntegrations = filteredIntegrations.filter((integration) => !connections[integration.id]);

  function handleAction(integration: Integration, action: "connect" | "manage" | "learn") {
    if (action === "connect") {
      setConnections((current) => ({ ...current, [integration.id]: true }));
      setNotice(`${integration.name} is connected in this UI preview. Backend authorization will be added with the integration contract.`);
      return;
    }
    if (action === "manage") {
      setNotice(`${integration.name} is ready for configuration. Connection settings will be wired to the backend integration service next.`);
      return;
    }
    setNotice(`${integration.name} will support scoped permissions and a guided connection flow.`);
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
              <IntegrationCard key={integration.id} integration={integration} connected={Boolean(connections[integration.id])} onAction={handleAction} />
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
              <span>Preview catalog: connection actions are local to this page and are not persisted or authorized with an external service yet.</span>
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

      {notice ? (
        <div role="status" aria-live="polite" className="flex items-start gap-2 rounded-lg border border-primary/20 bg-primary/5 px-4 py-3 text-sm text-muted-foreground">
          <Info className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
          <span>{notice}</span>
        </div>
      ) : null}

      {renderSection("Connected", "Services that are currently connected to your KubePilot environment.", connectedIntegrations, "No connected integrations match the current filters.")}
      {renderSection("Available integrations", "Connect additional services to extend KubePilot’s capabilities.", availableIntegrations, "No available integrations match the current filters.")}

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
