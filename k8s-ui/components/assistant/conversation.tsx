"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport, isToolUIPart } from "ai";
import { Conversation, ConversationContent, ConversationEmptyState, ConversationScrollButton } from "@/components/ai-elements/conversation";
import { Message, MessageContent, MessageResponse } from "@/components/ai-elements/message";
import { PromptInput, PromptInputBody, PromptInputTextarea, PromptInputFooter, PromptInputSubmit } from "@/components/ai-elements/prompt-input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { fetchAssistantModels, type AssistantModel } from "@/lib/assistant/models";
import type { AssistantContext } from "@/lib/assistant/schemas";
import { AssistantModelSelector } from "./model-selector";
import { AssistantTool } from "./tool-result";
import { agentListSchema, agentRequest, type AgentDefinition } from "@/lib/assistant/agents";
import { assistantSelectionUrl, type AssistantMode } from "@/lib/assistant/mode";

function AssistantSession({
  context,
  modelId,
  agentId,
  onRetry,
  onBusyChange,
  onConversationChange,
}: {
  context: AssistantContext;
  modelId?: string;
  agentId?: string;
  onRetry: () => void;
  onBusyChange: (busy: boolean) => void;
  onConversationChange: (hasMessages: boolean) => void;
}) {
  const [text, setText] = useState("");
  const transport = useMemo(() => new DefaultChatTransport({ api: "/api/assistant", body: { context, ...(agentId ? { agentId } : { modelId }) }, fetch: async (url, init) => {
    const response = await fetch(url, init);
    if (!response.ok) {
      const body = await response.json().catch(() => null) as { message?: string } | null;
      throw new Error(body?.message ?? `Assistant request failed (${response.status}).`);
    }
    return response;
  } }), [agentId, context, modelId]);
  const { messages, sendMessage, status, error, stop, setMessages, clearError } = useChat({ transport });
  const busy = status === "submitted" || status === "streaming";
  useEffect(() => { onConversationChange(messages.length > 0); }, [messages.length, onConversationChange]);
  useEffect(() => {
    onBusyChange(busy);
    return () => onBusyChange(false);
  }, [busy, onBusyChange]);
  useEffect(() => () => { void stop(); }, [stop]);
  const send = (value: string) => { if (!busy && value.trim()) { clearError(); void sendMessage({ text: value.trim() }); } };
  return <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-3">
    <div className="flex justify-end"><Button variant="outline" size="sm" disabled={busy} onClick={() => { setMessages([]); clearError(); }}>New conversation</Button></div>
    <Conversation><ConversationContent>
      {!messages.length && <ConversationEmptyState title="Investigate your cluster" description="Ask about workloads, events, logs, storage or Helm applications. Every change requires your explicit review."><div className="flex flex-col gap-4"><h2 className="text-lg font-medium">Investigate your cluster</h2><p className="text-sm text-muted-foreground">Read live evidence, diagnose failures, and review changes before execution.</p><div className="flex flex-wrap gap-2">{["Show unhealthy workloads", "Show recent warning events", "List installed Helm applications"].map(prompt => <Button key={prompt} variant="outline" onClick={() => send(prompt)}>{prompt}</Button>)}</div></div></ConversationEmptyState>}
      {messages.map(message => <Message key={message.id} from={message.role}><MessageContent>{message.parts.map((part, index) => part.type === "text" ? <MessageResponse key={index} isAnimating={busy} components={{ img: () => null, a: ({ children }) => <span>{children}</span> }}>{part.text}</MessageResponse> : isToolUIPart(part) ? <AssistantTool key={part.toolCallId} part={part} cluster={context.cluster} disabled={busy} followUp={send} onResult={result => send(`The confirmation result for proposal ${result.proposal_id} is ${result.status}: ${JSON.stringify(result.result)}. Explain the outcome; if there is a job_id, check its status. Do not repeat the action.`)} /> : null)}</MessageContent></Message>)}
      {busy && <div role="status" className="flex items-center gap-2 text-sm text-muted-foreground"><Spinner />Inspecting operational evidence…</div>}
    </ConversationContent><ConversationScrollButton /></Conversation>
    {error && <Alert variant="destructive"><AlertDescription className="flex flex-wrap items-center justify-between gap-2"><span>{error.message}</span><Button variant="outline" size="sm" onClick={onRetry}>{agentId ? "Retry agent" : "Refresh models"}</Button></AlertDescription></Alert>}
    <PromptInput onSubmit={({ text: value }) => { send(value); setText(""); }}>
      <PromptInputBody><PromptInputTextarea aria-label="Ask KubePilot" placeholder="Why is my deployment unavailable?" value={text} onChange={event => setText(event.target.value)} maxLength={8000} disabled={busy} /></PromptInputBody>
      <PromptInputFooter><span className="text-xs text-muted-foreground">Do not paste credentials. Reads run directly; changes require confirmation.</span><PromptInputSubmit status={status} onStop={() => void stop()} disabled={!busy && !text.trim()} /></PromptInputFooter>
    </PromptInput>
  </div>;
}

export function AssistantConversation({ context, initialMode, initialModelId, initialAgentId }: { context: AssistantContext; initialMode: AssistantMode; initialModelId?: string; initialAgentId?: string }) {
  const [mode, setMode] = useState<AssistantMode>(initialMode);
  const [models, setModels] = useState<AssistantModel[]>([]);
  const [modelId, setModelId] = useState<string | undefined>(initialModelId);
  const [agentId, setAgentId] = useState<string | undefined>(initialAgentId);
  const [agents, setAgents] = useState<AgentDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string>();
  const [agentsLoading, setAgentsLoading] = useState(false);
  const [agentsError, setAgentsError] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [hasMessages, setHasMessages] = useState(false);
  const [sessionVersion, setSessionVersion] = useState(0);

  const loadModels = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setLoadError(undefined);
    try {
      const available = await fetchAssistantModels(signal);
      setModels(available);
      if (initialModelId && !available.some(model => model.id === initialModelId)) {
        setModelId(undefined);
        setLoadError("The selected model is no longer eligible. Choose another model.");
      } else setModelId(current => available.some(model => model.id === current) ? current : initialModelId ?? available.find(model => model.is_default)?.id);
    } catch (error) {
      if (!signal?.aborted) { setModels([]); setModelId(undefined); setLoadError(error instanceof Error ? error.message : "The Assistant models could not be loaded."); }
    } finally { if (!signal?.aborted) setLoading(false); }
  }, [initialModelId]);

  const loadAgents = useCallback(async () => {
    setAgentsLoading(true);
    setAgentsError(undefined);
    try { setAgents((await agentRequest("/api/assistant/agents", agentListSchema)).agents); }
    catch (error) { setAgentsError(error instanceof Error ? error.message : "The AI agents could not be loaded."); }
    finally { setAgentsLoading(false); }
  }, []);

  useEffect(() => {
    if (mode !== "direct") return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => { void loadModels(controller.signal); }, 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [loadModels, mode]);
  useEffect(() => {
    if (mode !== "agent") return;
    const timer = window.setTimeout(() => { void loadAgents(); }, 0);
    return () => window.clearTimeout(timer);
  }, [loadAgents, mode]);

  const retry = () => { setSessionVersion(value => value + 1); if (mode === "direct") void loadModels(); else void loadAgents(); };
  const updateUrl = (nextMode: AssistantMode, nextModelId?: string, nextAgentId?: string) => window.history.replaceState(null, "", assistantSelectionUrl(nextMode, nextModelId, nextAgentId, window.location.search));
  const switchSelection = (nextMode: AssistantMode, nextModelId?: string, nextAgentId?: string) => {
    if (nextMode === mode && nextModelId === modelId && nextAgentId === agentId) return;
    if (hasMessages && !window.confirm("Switching Assistant modes will clear this conversation because the model instructions and available tools will change. Continue?")) return;
    setMode(nextMode); setModelId(nextMode === "direct" ? nextModelId : undefined); setAgentId(nextMode === "agent" ? nextAgentId : undefined); setLoadError(undefined); setSessionVersion(value => value + 1); setHasMessages(false); updateUrl(nextMode, nextModelId, nextAgentId);
  };
  const selectedAgent = agents.find(agent => agent.id === agentId);
  const agentUnavailable = mode === "agent" && Boolean(agentId && (!selectedAgent || !selectedAgent.enabled));

  return <div className="flex h-[calc(100dvh-280px)] min-h-[480px] min-w-0 flex-col gap-3">
    <div className="flex flex-wrap items-center justify-between gap-3"><p className="text-sm text-muted-foreground">{context.cluster} / {context.namespace ?? "all namespaces"}{context.name ? ` / ${context.name}` : ""}{context.release ? ` / release ${context.release}` : ""}</p><div className="flex flex-wrap items-center justify-end gap-2"><Select value={mode} onValueChange={value => value && switchSelection(value as AssistantMode, value === "direct" ? modelId : undefined, value === "agent" ? agentId : undefined)} disabled={busy}><SelectTrigger aria-label="Chat mode" className="w-32"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="direct">Direct chat</SelectItem><SelectItem value="agent">Agent chat</SelectItem></SelectContent></Select>{mode === "agent" ? agentsLoading ? <div role="status" aria-label="Loading agents"><Skeleton className="h-7 w-48" /></div> : <Select value={agentId ?? ""} onValueChange={value => value && switchSelection("agent", undefined, value)} disabled={busy || Boolean(agentsError)}><SelectTrigger aria-label="Select AI agent" className="w-52"><SelectValue placeholder="Select agent" /></SelectTrigger><SelectContent>{agents.map(agent => <SelectItem key={agent.id} value={agent.id} disabled={!agent.enabled}>{agent.name}{!agent.enabled ? " · Disabled" : ""}</SelectItem>)}</SelectContent></Select> : loading ? <div role="status" aria-label="Loading models"><Skeleton className="h-7 w-40" /></div> : <AssistantModelSelector models={models} value={modelId} disabled={busy || Boolean(loadError)} onChange={value => switchSelection("direct", value)} />}</div></div>
    {mode === "direct" && loadError ? <Alert variant="destructive"><AlertDescription className="flex flex-wrap items-center justify-between gap-2"><span>{loadError}</span><Button variant="outline" size="sm" onClick={() => void loadModels()}>Retry</Button></AlertDescription></Alert> : null}
    {mode === "agent" && agentsError ? <Alert variant="destructive"><AlertDescription className="flex flex-wrap items-center justify-between gap-2"><span>{agentsError}</span><Button variant="outline" size="sm" onClick={() => void loadAgents()}>Retry</Button></AlertDescription></Alert> : null}
    {mode === "agent" && agentUnavailable ? <Alert variant="destructive"><AlertDescription>The selected agent is unavailable or disabled. Choose an enabled agent to continue.</AlertDescription></Alert> : null}
    {mode === "agent" && selectedAgent && <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground"><Badge variant="secondary">{selectedAgent.name}</Badge><span>{selectedAgent.description}</span><Badge variant="outline">{selectedAgent.tool_ids.length} configured tools</Badge></div>}
    {mode === "direct" && !loading && !loadError && models.length === 0 ? <Alert><AlertDescription>No eligible Assistant models are configured. Ask an administrator to enable and check an available streaming model with tool support.</AlertDescription></Alert> : null}
    {mode === "direct" && !loading && !loadError && models.length > 0 && !modelId ? <Alert><AlertDescription>Select an eligible model to begin. No default model is configured.</AlertDescription></Alert> : null}
    {mode === "agent" && !agentsLoading && !agentsError && !agents.length ? <Alert><AlertDescription>No AI agents are configured yet. Ask an administrator to create an enabled agent.</AlertDescription></Alert> : null}
    {mode === "agent" && agentId && !agentUnavailable ? <AssistantSession key={`agent-${agentId}-${sessionVersion}`} context={context} agentId={agentId} onBusyChange={setBusy} onConversationChange={setHasMessages} onRetry={retry} /> : mode === "direct" && modelId ? <AssistantSession key={`${modelId}-${sessionVersion}`} context={context} modelId={modelId} onBusyChange={setBusy} onConversationChange={setHasMessages} onRetry={retry} /> : null}
  </div>;
}
