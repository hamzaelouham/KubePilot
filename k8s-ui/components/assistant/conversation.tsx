"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport, isToolUIPart } from "ai";
import { Conversation, ConversationContent, ConversationEmptyState, ConversationScrollButton } from "@/components/ai-elements/conversation";
import { Message, MessageContent, MessageResponse } from "@/components/ai-elements/message";
import { PromptInput, PromptInputBody, PromptInputTextarea, PromptInputFooter, PromptInputSubmit } from "@/components/ai-elements/prompt-input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { fetchAssistantModels, type AssistantModel } from "@/lib/assistant/models";
import {
  createConversation,
  messagesFromConversation,
  saveConversation,
  type ConversationDetail,
  type ConversationMessage,
} from "@/lib/assistant/conversations";
import type { AssistantContext } from "@/lib/assistant/schemas";
import { AssistantModelSelector } from "./model-selector";
import { AssistantTool } from "./tool-result";
import { agentListSchema, agentRequest, type AgentDefinition } from "@/lib/assistant/agents";
import { assistantSelectionUrl, type AssistantMode } from "@/lib/assistant/mode";

function AssistantSession({
  context,
  modelId,
  agentId,
  conversationId,
  initialMessages,
  onRetry,
  onBusyChange,
  onConversationChange,
  onSaved,
  onNewConversation,
}: {
  context: AssistantContext;
  modelId?: string;
  agentId?: string;
  conversationId: string;
  initialMessages: ReturnType<typeof messagesFromConversation>;
  onRetry: () => void;
  onBusyChange: (busy: boolean) => void;
  onConversationChange: (hasMessages: boolean) => void;
  onSaved: (conversation: ConversationDetail) => void;
  onNewConversation: (selection?: { mode: AssistantMode; modelId?: string; agentId?: string }) => void;
}) {
  const [text, setText] = useState("");
  const [saveError, setSaveError] = useState<string>();
  const transport = useMemo(() => new DefaultChatTransport({
    api: "/api/assistant",
    body: () => ({ context, conversationId, ...(agentId ? { agentId } : { modelId }) }),
    fetch: async (url, init) => {
      const response = await fetch(url, init);
      if (!response.ok) {
        const body = await response.json().catch(() => null) as { message?: string } | null;
        throw new Error(body?.message ?? `Assistant request failed (${response.status}).`);
      }
      return response;
    },
  }), [agentId, context, conversationId, modelId]);
  const { messages, sendMessage, status, error, stop, clearError } = useChat({
    transport,
    messages: initialMessages as never,
    onFinish: ({ messages: finishedMessages, isError, isAbort, isDisconnect }) => {
      if (isError || isAbort || isDisconnect) return;
      const body = {
        mode: agentId ? "agent" as const : "direct" as const,
        model_id: agentId ? null : modelId ?? null,
        agent_id: agentId ?? null,
        context,
        messages: finishedMessages.map(message => ({ id: message.id, role: message.role, parts: message.parts })) as ConversationMessage[],
      };
      void saveConversation(conversationId, body).then(saved => {
        setSaveError(undefined);
        onSaved(saved);
      }).catch(saveFailure => {
        setSaveError(saveFailure instanceof Error ? saveFailure.message : "The conversation could not be saved. Refresh before trying again.");
      });
    },
  });
  const busy = status === "submitted" || status === "streaming";
  useEffect(() => { onConversationChange(messages.length > 0); }, [messages.length, onConversationChange]);
  useEffect(() => {
    onBusyChange(busy);
    return () => onBusyChange(false);
  }, [busy, onBusyChange]);
  useEffect(() => () => { void stop(); }, [stop]);
  const send = (value: string) => { if (!busy && value.trim()) { clearError(); setSaveError(undefined); void sendMessage({ text: value.trim() }); } };
  return <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-3">
    <div className="flex justify-end"><Button variant="outline" size="sm" disabled={busy} onClick={() => onNewConversation()}>New conversation</Button></div>
    <Conversation><ConversationContent>
      {!messages.length && <ConversationEmptyState title="Investigate your cluster" description="Ask about workloads, events, logs, storage or Helm applications. Every change requires your explicit review."><div className="flex flex-col gap-4"><h2 className="text-lg font-medium">Investigate your cluster</h2><p className="text-sm text-muted-foreground">Ask about live evidence, diagnose failures, and review changes before execution.</p><div className="flex flex-wrap gap-2">{["Show unhealthy workloads", "Show recent warning events", "List installed Helm applications"].map(prompt => <Button key={prompt} variant="outline" onClick={() => send(prompt)}>{prompt}</Button>)}</div></div></ConversationEmptyState>}
      {messages.map(message => <Message key={message.id} from={message.role}><MessageContent>{message.parts.map((part, index) => part.type === "text" ? <MessageResponse key={index} isAnimating={busy} components={{ img: () => null, a: ({ children }) => <span>{children}</span> }}>{part.text}</MessageResponse> : isToolUIPart(part) ? <AssistantTool key={part.toolCallId} part={part} cluster={context.cluster} disabled={busy} followUp={send} onResult={result => send(`The confirmation result for proposal ${result.proposal_id} is ${result.status}: ${JSON.stringify(result.result)}. Explain the outcome; if there is a job_id, check its status. Do not repeat the action.`)} /> : null)}</MessageContent></Message>)}
      {busy && <div role="status" className="flex items-center gap-2 text-sm text-muted-foreground"><Spinner />Inspecting operational evidence…</div>}
    </ConversationContent><ConversationScrollButton /></Conversation>
    {saveError && <Alert variant="destructive"><AlertDescription>{saveError}</AlertDescription></Alert>}
    {error && <Alert variant="destructive"><AlertDescription className="flex flex-wrap items-center justify-between gap-2"><span>{error.message}</span><Button variant="outline" size="sm" onClick={onRetry}>{agentId ? "Retry agent" : "Refresh models"}</Button></AlertDescription></Alert>}
    <PromptInput onSubmit={({ text: value }) => { send(value); setText(""); }}>
      <PromptInputBody><PromptInputTextarea aria-label="Ask KubePilot" placeholder="Why is my deployment unavailable?" value={text} onChange={event => setText(event.target.value)} maxLength={8000} disabled={busy} /></PromptInputBody>
      <PromptInputFooter><span className="text-xs text-muted-foreground">Do not paste credentials. Reads run directly; changes require confirmation.</span><PromptInputSubmit status={status} onStop={() => void stop()} disabled={!busy && !text.trim()} /></PromptInputFooter>
    </PromptInput>
  </div>;
}

export function AssistantConversation({
  context,
  initialMode,
  initialModelId,
  initialAgentId,
  conversation,
  onConversationCreated,
  onConversationSaved,
  onNewConversation,
}: {
  context: AssistantContext;
  initialMode: AssistantMode;
  initialModelId?: string;
  initialAgentId?: string;
  conversation?: ConversationDetail;
  onConversationCreated: (conversation: ConversationDetail) => void;
  onConversationSaved: (conversation: ConversationDetail) => void;
  onNewConversation: (selection?: { mode: AssistantMode; modelId?: string; agentId?: string }) => void;
}) {
  const [mode, setMode] = useState<AssistantMode>(conversation?.mode ?? initialMode);
  const [models, setModels] = useState<AssistantModel[]>([]);
  const [modelId, setModelId] = useState<string | undefined>(conversation?.model_id ?? initialModelId);
  const [agentId, setAgentId] = useState<string | undefined>(conversation?.agent_id ?? initialAgentId);
  const [agents, setAgents] = useState<AgentDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string>();
  const [conversationError, setConversationError] = useState<string>();
  const [agentsLoading, setAgentsLoading] = useState(false);
  const [agentsError, setAgentsError] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [hasMessages, setHasMessages] = useState(Boolean(conversation?.parts.length));
  const [sessionVersion, setSessionVersion] = useState(0);
  const [activeConversation, setActiveConversation] = useState(conversation);
  const [creatingConversation, setCreatingConversation] = useState(false);
  const [pendingSelection, setPendingSelection] = useState<{ mode: AssistantMode; modelId?: string; agentId?: string } | null>(null);

  useEffect(() => {
    setActiveConversation(conversation);
    setMode(conversation?.mode ?? initialMode);
    setModelId(conversation?.model_id ?? initialModelId);
    setAgentId(conversation?.agent_id ?? initialAgentId);
    setHasMessages(Boolean(conversation?.parts.length));
    setConversationError(undefined);
  }, [conversation, initialAgentId, initialMode, initialModelId]);

  const loadModels = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setLoadError(undefined);
    try {
      const available = await fetchAssistantModels(signal);
      setModels(available);
      if (initialModelId && !available.some(model => model.id === initialModelId)) {
        setModelId(initialModelId);
        setLoadError("The selected model is no longer eligible. Choose another model or start a new conversation.");
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

  useEffect(() => {
    if (activeConversation || creatingConversation || conversationError || !context.cluster || (mode === "direct" && (!modelId || Boolean(loadError))) || (mode === "agent" && !agentId)) return;
    setCreatingConversation(true);
    setConversationError(undefined);
    void createConversation({
      title: null,
      mode,
      model_id: mode === "direct" ? modelId ?? null : null,
      agent_id: mode === "agent" ? agentId ?? null : null,
      context,
    }).then(created => {
      setActiveConversation(created);
      onConversationCreated(created);
    }).catch(error => {
      setConversationError(error instanceof Error ? error.message : "The conversation could not be created. Refresh before trying again.");
    }).finally(() => setCreatingConversation(false));
  }, [activeConversation, agentId, context, conversationError, creatingConversation, loadError, mode, modelId, onConversationCreated]);

  const retry = () => { setSessionVersion(value => value + 1); if (mode === "direct") void loadModels(); else void loadAgents(); };
  const updateUrl = (nextMode: AssistantMode, nextModelId?: string, nextAgentId?: string) => window.history.replaceState(null, "", assistantSelectionUrl(nextMode, nextModelId, nextAgentId, window.location.search));
  const startNew = () => {
    if (busy) return;
    setActiveConversation(undefined);
    setHasMessages(false);
    setSessionVersion(value => value + 1);
    setConversationError(undefined);
    onNewConversation({ mode, modelId: mode === "direct" ? modelId : undefined, agentId: mode === "agent" ? agentId : undefined });
  };
  const applySelection = (nextMode: AssistantMode, nextModelId?: string, nextAgentId?: string) => {
    setMode(nextMode); setModelId(nextMode === "direct" ? nextModelId : undefined); setAgentId(nextMode === "agent" ? nextAgentId : undefined); setLoadError(undefined); setActiveConversation(undefined); setSessionVersion(value => value + 1); setHasMessages(false); updateUrl(nextMode, nextModelId, nextAgentId); onNewConversation({ mode: nextMode, modelId: nextModelId, agentId: nextAgentId });
  };
  const switchSelection = (nextMode: AssistantMode, nextModelId?: string, nextAgentId?: string) => {
    if (nextMode === mode && nextModelId === modelId && nextAgentId === agentId) return;
    if (hasMessages) { setPendingSelection({ mode: nextMode, modelId: nextModelId, agentId: nextAgentId }); return; }
    applySelection(nextMode, nextModelId, nextAgentId);
  };
  const selectedAgent = agents.find(agent => agent.id === agentId);
  const agentUnavailable = mode === "agent" && Boolean(agentId && (!selectedAgent || !selectedAgent.enabled));
  const readyConversation = activeConversation && !creatingConversation ? activeConversation : undefined;

  return <div className="flex h-[calc(100dvh-280px)] min-h-[480px] min-w-0 flex-col gap-3">
    <div className="flex flex-wrap items-center justify-between gap-3"><p className="text-sm text-muted-foreground">{context.cluster} / {context.namespace ?? "all namespaces"}{context.name ? ` / ${context.name}` : ""}{context.release ? ` / release ${context.release}` : ""}</p><div className="flex flex-wrap items-center justify-end gap-2"><Select value={mode} onValueChange={value => value && switchSelection(value as AssistantMode, value === "direct" ? modelId : undefined, value === "agent" ? agentId : undefined)} disabled={busy}><SelectTrigger aria-label="Chat mode" className="w-32"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="direct">Direct chat</SelectItem><SelectItem value="agent">Agent chat</SelectItem></SelectContent></Select>{mode === "agent" ? agentsLoading ? <div role="status" aria-label="Loading agents"><Skeleton className="h-7 w-48" /></div> : <Select value={agentId ?? ""} onValueChange={value => value && switchSelection("agent", undefined, value)} disabled={busy || Boolean(agentsError)}><SelectTrigger aria-label="Select AI agent" className="w-52"><SelectValue placeholder="Select agent" /></SelectTrigger><SelectContent>{agents.map(agent => <SelectItem key={agent.id} value={agent.id} disabled={!agent.enabled}>{agent.name}{!agent.enabled ? " · Disabled" : ""}</SelectItem>)}</SelectContent></Select> : loading ? <div role="status" aria-label="Loading models"><Skeleton className="h-7 w-40" /></div> : <AssistantModelSelector models={models} value={modelId} disabled={busy || Boolean(loadError)} onChange={value => switchSelection("direct", value)} />}</div></div>
    {mode === "direct" && loadError ? <Alert variant="destructive"><AlertDescription className="flex flex-wrap items-center justify-between gap-2"><span>{loadError}</span><Button variant="outline" size="sm" onClick={() => void loadModels()}>Retry</Button></AlertDescription></Alert> : null}
    {mode === "agent" && agentsError ? <Alert variant="destructive"><AlertDescription className="flex flex-wrap items-center justify-between gap-2"><span>{agentsError}</span><Button variant="outline" size="sm" onClick={() => void loadAgents()}>Retry</Button></AlertDescription></Alert> : null}
    {conversationError ? <Alert variant="destructive"><AlertDescription>{conversationError}</AlertDescription></Alert> : null}
    {mode === "agent" && agentUnavailable ? <Alert variant="destructive"><AlertDescription>The selected agent is unavailable or disabled. Choose an enabled agent or open a new conversation.</AlertDescription></Alert> : null}
    {mode === "agent" && selectedAgent && <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground"><Badge variant="secondary">{selectedAgent.name}</Badge><span>{selectedAgent.description}</span><Badge variant="outline">{selectedAgent.tool_ids.length} configured tools</Badge></div>}
    {mode === "direct" && !loading && !loadError && models.length === 0 ? <Alert><AlertDescription>No eligible Assistant models are configured. Ask an administrator to enable and check an available streaming model with tool support.</AlertDescription></Alert> : null}
    {mode === "direct" && !loading && !loadError && models.length > 0 && !modelId ? <Alert><AlertDescription>Select an eligible model to begin. No default model is configured.</AlertDescription></Alert> : null}
    {mode === "agent" && !agentsLoading && !agentsError && !agents.length ? <Alert><AlertDescription>No AI agents are configured yet. Ask an administrator to create an enabled agent.</AlertDescription></Alert> : null}
    {creatingConversation ? <div role="status" className="flex items-center gap-2 text-sm text-muted-foreground"><Spinner />Preparing your conversation…</div> : null}
    {readyConversation && mode === "agent" && agentId && !agentUnavailable ? <AssistantSession key={`agent-${agentId}-${readyConversation.id}-${sessionVersion}`} context={context} agentId={agentId} conversationId={readyConversation.id} initialMessages={messagesFromConversation(readyConversation)} onBusyChange={setBusy} onConversationChange={setHasMessages} onRetry={retry} onSaved={onConversationSaved} onNewConversation={startNew} /> : readyConversation && mode === "direct" && modelId && !loadError ? <AssistantSession key={`${modelId}-${readyConversation.id}-${sessionVersion}`} context={context} modelId={modelId} conversationId={readyConversation.id} initialMessages={messagesFromConversation(readyConversation)} onBusyChange={setBusy} onConversationChange={setHasMessages} onRetry={retry} onSaved={onConversationSaved} onNewConversation={startNew} /> : null}
    <AlertDialog open={pendingSelection !== null} onOpenChange={open => { if (!open) setPendingSelection(null); }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Start a new conversation?</AlertDialogTitle>
          <AlertDialogDescription>Switching the Assistant mode or selection will start a new conversation because its model instructions and available tools will change. Your current conversation remains saved.</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Keep current conversation</AlertDialogCancel>
          <AlertDialogAction onClick={() => { if (!pendingSelection) return; const selection = pendingSelection; setPendingSelection(null); applySelection(selection.mode, selection.modelId, selection.agentId); }}>Start new conversation</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </div>;
}
