"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Bot, Plus, RefreshCw, Search, ArrowLeft, ChevronRight } from "lucide-react";
import { DashboardShell } from "@/components/dashboard-shell";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Empty, EmptyHeader, EmptyMedia, EmptyTitle, EmptyDescription } from "@/components/ui/empty";
import { InputGroup, InputGroupInput, InputGroupAddon } from "@/components/ui/input-group";
import { Skeleton } from "@/components/ui/skeleton";
import { AgentEditor } from "./editor";
import { SkillsCatalog, TemplatesCatalog } from "./catalog";
import { agentRequest, agentListSchema, agentModelsSchema, agentSkillListSchema, agentTemplateListSchema, agentToolListSchema, filterAgents, AgentRequestError, type AgentDefinition, type AgentModel, type AgentSkill, type AgentTemplate, type AgentTool } from "@/lib/assistant/agents";
import type { BackendUser } from "@/lib/auth-client";
import { useClusterSelection } from "@/lib/use-cluster-selection";
import { withCluster } from "@/lib/cluster-query";
import { cn } from "@/lib/utils";

export function AgentsView({ user, creating = false }: { user: BackendUser; creating?: boolean }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const selection = useClusterSelection(undefined, true);
  const [agents, setAgents] = useState<AgentDefinition[]>([]);
  const [models, setModels] = useState<AgentModel[]>([]);
  const [skills, setSkills] = useState<AgentSkill[]>([]);
  const [tools, setTools] = useState<AgentTool[]>([]);
  const [templates, setTemplates] = useState<AgentTemplate[]>([]);
  const [modelsError, setModelsError] = useState("");
  const [catalogError, setCatalogError] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [failure, setFailure] = useState<AgentRequestError | null>(null);
  const [search, setSearch] = useState("");
  const [revision, setRevision] = useState(0);
  const [announcement, setAnnouncement] = useState("");
  const [hasDraft, setHasDraft] = useState(false);
  const [panel, setPanel] = useState<"agents" | "skills" | "templates">("agents");
  const dirty = useRef(false);
  const onDirty = useCallback((value: boolean) => { dirty.current = value; setHasDraft(value); }, []);
  const admin = user.role === "admin";
  const allowLeave = useCallback(() => !dirty.current || window.confirm("Discard your unsaved agent changes?"), []);
  function navigate(path: string) { if (allowLeave()) { dirty.current = false; router.push(path); } }

  useEffect(() => {
    const unload = (event: BeforeUnloadEvent) => { if (dirty.current) event.preventDefault(); };
    const links = (event: MouseEvent) => {
      const anchor = (event.target as Element).closest?.("a[href]");
      if (anchor && dirty.current && !allowLeave()) { event.preventDefault(); event.stopPropagation(); }
    };
    window.addEventListener("beforeunload", unload);
    document.addEventListener("click", links, true);
    return () => { window.removeEventListener("beforeunload", unload); document.removeEventListener("click", links, true); };
  }, [allowLeave]);
  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      setLoading(true); setFailure(null); setModelsError(""); setCatalogError("");
      const [agentResult, modelResult, skillResult, toolResult, templateResult] = await Promise.allSettled([
        agentRequest("/api/assistant/agents", agentListSchema, "GET", undefined, controller.signal),
        admin ? agentRequest("/api/settings/models", agentModelsSchema, "GET", undefined, controller.signal) : Promise.resolve({ models: [] as AgentModel[] }),
        agentRequest("/api/assistant/agents/skills", agentSkillListSchema, "GET", undefined, controller.signal),
        agentRequest("/api/assistant/agents/tools", agentToolListSchema, "GET", undefined, controller.signal),
        agentRequest("/api/assistant/agents/templates", agentTemplateListSchema, "GET", undefined, controller.signal),
      ]);
      if (controller.signal.aborted) return;
      if (agentResult.status === "fulfilled") {
        setAgents(agentResult.value.agents);
        setSelected(previous => previous && agentResult.value.agents.some(agent => agent.id === previous) ? previous : agentResult.value.agents[0]?.id ?? null);
      } else setFailure(agentResult.reason instanceof AgentRequestError ? agentResult.reason : new AgentRequestError(500, "unexpected_error", "Could not load agent definitions."));
      if (modelResult.status === "fulfilled") setModels(modelResult.value.models);
      else setModelsError(modelResult.reason instanceof Error ? modelResult.reason.message : "Could not load models.");
      if (skillResult.status === "fulfilled") setSkills(skillResult.value.skills);
      else setCatalogError(skillResult.reason instanceof Error ? skillResult.reason.message : "Could not load skills.");
      if (toolResult.status === "fulfilled") setTools(toolResult.value.tools);
      else setCatalogError(toolResult.reason instanceof Error ? toolResult.reason.message : "Could not load tools.");
      if (templateResult.status === "fulfilled") setTemplates(templateResult.value.templates);
      else setCatalogError(templateResult.reason instanceof Error ? templateResult.reason.message : "Could not load templates.");
      setLoading(false);
    }
    void load();
    return () => controller.abort();
  }, [admin, revision]);
  const active = agents.find(agent => agent.id === selected) ?? null;
  const visible = filterAgents(agents, search);
  const enabled = agents.filter(agent => agent.enabled).length;
  const title = creating ? "Create new AI agent" : "AI Agents";
  return <DashboardShell user={user} activeResource="ai-agents" activeNamespace="" activeCluster={selection.cluster} clusters={selection.clusters}
    onSelectCluster={selection.selectCluster} onNavigate={(resource, namespace) => navigate(withCluster(`/dashboard?resource=${encodeURIComponent(resource)}&namespace=${encodeURIComponent(namespace)}`, selection.cluster))}>
    <div className="flex min-w-0 flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4"><div className="flex items-start gap-3">
        {creating ? <Button aria-label="Back to agents" variant="outline" size="icon" onClick={() => navigate("/assistant/agents")}><ArrowLeft /></Button> : <div className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary"><Bot className="size-6" /></div>}
        <div><p className="mb-1 text-xs font-medium uppercase tracking-widest text-muted-foreground">AI Assistant / Agents</p><h1 className="text-2xl font-semibold tracking-tight">{title}</h1><p className="mt-1 max-w-2xl text-sm leading-relaxed text-muted-foreground">{creating ? "Define a purpose, choose a model, and review your shared agent." : "Give your team focused agents with clear instructions and trusted models."}</p></div></div>
        {!creating && <div className="flex gap-2"><Button variant="outline" aria-label="Refresh agents" disabled={loading} onClick={() => { if (allowLeave()) { dirty.current = false; setRevision(value => value + 1); } }}><RefreshCw /></Button>{admin && <Button onClick={() => navigate("/assistant/agents/new")}><Plus data-icon="inline-start" />New agent</Button>}</div>}
      </div>
      <p role="status" className="sr-only">{announcement}</p>
      {creating && !admin ? <Alert variant="destructive"><AlertTitle>Admin access required</AlertTitle><AlertDescription>Only administrators can create shared agents. You can inspect existing agents from the list.</AlertDescription></Alert> : loading ? <div aria-label="Loading agents" aria-busy="true" className="grid gap-4 md:grid-cols-2"><Skeleton className="h-40" /><Skeleton className="h-96" /></div> : failure ? <Alert variant="destructive"><AlertTitle>{failure.status === 401 || failure.status === 403 ? "Access denied" : "Could not load agents"}</AlertTitle><AlertDescription>{failure.message}<Button variant="outline" onClick={() => setRevision(value => value + 1)}>Try again</Button></AlertDescription></Alert> : creating ?
        <AgentEditor original={null} models={models} skills={skills} tools={tools} template={templates.find(item => item.id === searchParams.get("template")) ?? null} modelsError={modelsError} editable={admin} onDirty={onDirty} onSaved={() => { dirty.current = false; router.push("/assistant/agents"); }} onDeleted={() => {}} onCancel={() => navigate("/assistant/agents")} /> : <>
          <div role="tablist" aria-label="AI Agent configuration" className="flex flex-wrap gap-2 border-b pb-3">
            {(["agents", "skills", "templates"] as const).map(item => <Button key={item} role="tab" aria-selected={panel === item} variant={panel === item ? "secondary" : "ghost"} onClick={() => { if (allowLeave()) { dirty.current = false; setPanel(item); } }}>{item === "agents" ? "Agents" : item === "skills" ? "Skills" : "Templates"}</Button>)}
          </div>
          {catalogError && <Alert><AlertTitle>Some configuration metadata is unavailable</AlertTitle><AlertDescription>{catalogError} Existing agent data remains available.</AlertDescription></Alert>}
          {panel === "skills" ? <SkillsCatalog skills={skills} editable={admin} onRefresh={() => setRevision(value => value + 1)} /> : panel === "templates" ? <TemplatesCatalog templates={templates} editable={admin} onUse={template => navigate(`/assistant/agents/new?template=${encodeURIComponent(template.id)}`)} /> : <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">{[{ label: "Total agents", value: agents.length, detail: "Shared with your team" }, { label: "Enabled", value: enabled, detail: "Configured for future use" }, { label: "Disabled", value: agents.length - enabled, detail: "Saved, not enabled" }].map(stat => <Card key={stat.label}><CardHeader><CardDescription>{stat.label}</CardDescription><CardTitle><span className="text-3xl tabular-nums">{stat.value}</span></CardTitle></CardHeader><CardContent><p className="text-xs text-muted-foreground">{stat.detail}</p></CardContent></Card>)}</div>
          <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-sm font-semibold">Agent library <span className="ml-2 font-normal text-muted-foreground">{visible.length} of {agents.length}</span></h2><InputGroup className="w-full sm:max-w-xs"><InputGroupAddon><Search /></InputGroupAddon><InputGroupInput aria-label="Search agents by name or description" aria-describedby={hasDraft ? "agent-search-help" : undefined} disabled={hasDraft} placeholder="Search agents…" value={search} onChange={event => setSearch(event.target.value)} /></InputGroup></div>
          {hasDraft && <p id="agent-search-help" className="text-xs text-muted-foreground">Save your changes or refresh to discard them before filtering the library.</p>}
          {!visible.length ? <Empty className="min-h-64 border"><EmptyHeader><EmptyMedia variant="icon"><Bot /></EmptyMedia><EmptyTitle>{agents.length ? "No matching agents" : "Your agent library starts here"}</EmptyTitle><EmptyDescription>{agents.length ? "Try another name or description." : admin ? "Create a shared agent with focused instructions and a model configured in Settings." : "An administrator can create shared agents for your team."}</EmptyDescription></EmptyHeader>{agents.length ? <Button variant="outline" onClick={() => setSearch("")}>Clear search</Button> : admin && <Button onClick={() => navigate("/assistant/agents/new")}><Plus data-icon="inline-start" />Create first agent</Button>}</Empty> :
            <div className="grid min-w-0 items-start gap-6 xl:grid-cols-[minmax(280px,0.85fr)_minmax(0,1.15fr)]"><div className="flex min-w-0 flex-col gap-3" aria-label="Agent library">{visible.map(agent => <button key={agent.id} type="button" aria-pressed={agent.id === selected} onClick={() => { if (agent.id !== selected && allowLeave()) { dirty.current = false; setSelected(agent.id); } }} className={cn("flex w-full min-w-0 items-start gap-3 rounded-xl border p-5 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring", agent.id === selected ? "border-primary/40 bg-primary/5" : "bg-card hover:bg-accent/50")}>
              <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"><Bot className="size-5" /></div><div className="flex min-w-0 flex-1 flex-col gap-2"><div className="flex flex-wrap items-start justify-between gap-2"><h3 className="break-words font-semibold">{agent.name}</h3><Badge variant={agent.enabled ? "secondary" : "outline"}>{agent.enabled ? "Enabled" : "Disabled"}</Badge></div><p className="line-clamp-2 break-words text-sm leading-relaxed text-muted-foreground">{agent.description}</p><div className="mt-2 flex items-center justify-between gap-2 text-xs text-muted-foreground"><span>{agent.model ? `${agent.model.friendly_name} · ${agent.model.provider_name}` : "Model missing"}</span><ChevronRight className="size-4 shrink-0" /></div>{agent.model && (!agent.model.enabled || agent.model.availability !== "available") && <span className="text-xs text-muted-foreground">{agent.model.enabled ? `Model ${agent.model.availability}` : "Model disabled"}</span>}</div>
            </button>)}</div>
            {active && <AgentEditor key={`${active.id}-${revision}`} original={active} models={models} skills={skills} tools={tools} modelsError={modelsError} editable={admin} onDirty={onDirty} onCancel={() => {}} onSaved={saved => { setAgents(previous => previous.map(agent => agent.id === saved.id ? saved : agent).sort((a, b) => a.name.localeCompare(b.name))); setAnnouncement("Agent saved."); }} onDeleted={() => { dirty.current = false; setAnnouncement("Agent deleted."); setRevision(value => value + 1); }} />}
            </div>}
          </>}
        </>}
    </div>
  </DashboardShell>;
}
