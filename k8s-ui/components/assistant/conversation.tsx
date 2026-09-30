"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport, isToolUIPart } from "ai";
import { Conversation, ConversationContent, ConversationEmptyState, ConversationScrollButton } from "@/components/ai-elements/conversation";
import { Message, MessageContent, MessageResponse } from "@/components/ai-elements/message";
import { PromptInput, PromptInputBody, PromptInputTextarea, PromptInputFooter, PromptInputSubmit } from "@/components/ai-elements/prompt-input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { fetchAssistantModels, type AssistantModel } from "@/lib/assistant/models";
import type { AssistantContext } from "@/lib/assistant/schemas";
import { AssistantModelSelector } from "./model-selector";
import { AssistantTool } from "./tool-result";

function AssistantSession({
  context,
  modelId,
  agentId,
  onRetry,
  onBusyChange,
}: {
  context: AssistantContext;
  modelId?: string;
  agentId?: string;
  onRetry: () => void;
  onBusyChange: (busy: boolean) => void;
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

export function AssistantConversation({ context, agentId }: { context: AssistantContext; agentId?: string }) {
  const [models, setModels] = useState<AssistantModel[]>([]);
  const [modelId, setModelId] = useState<string>();
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [sessionVersion, setSessionVersion] = useState(0);

  const loadModels = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setLoadError(undefined);
    try {
      const available = await fetchAssistantModels(signal);
      setModels(available);
      setModelId((current) => available.some((model) => model.id === current)
        ? current
        : available.find((model) => model.is_default)?.id);
    } catch (error) {
      if (!signal?.aborted) {
        setModels([]);
        setModelId(undefined);
        setLoadError(error instanceof Error ? error.message : "The Assistant models could not be loaded.");
      }
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (agentId) {
      setLoading(false);
      setLoadError(undefined);
      setModels([]);
      setModelId(undefined);
      return;
    }
    const controller = new AbortController();
    fetchAssistantModels(controller.signal)
      .then((available) => {
        if (controller.signal.aborted) return;
        setModels(available);
        setModelId((current) => available.some((model) => model.id === current)
          ? current
          : available.find((model) => model.is_default)?.id);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setModels([]);
        setModelId(undefined);
        setLoadError(error instanceof Error ? error.message : "The Assistant models could not be loaded.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [agentId]);

  const retry = () => {
    setSessionVersion(value => value + 1);
    if (!agentId) void loadModels();
  };

  return <div className="flex h-[calc(100dvh-280px)] min-h-[480px] min-w-0 flex-col gap-3">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <p className="text-sm text-muted-foreground">{context.cluster} / {context.namespace ?? "all namespaces"}{context.name ? ` / ${context.name}` : ""}{context.release ? ` / release ${context.release}` : ""}</p>
      {agentId ? <span className="rounded-md border px-2 py-1 text-xs font-medium text-muted-foreground">Selected agent</span> : loading ? <div role="status" aria-label="Loading models"><Skeleton className="h-7 w-40" /></div> : <AssistantModelSelector models={models} value={modelId} disabled={busy || Boolean(loadError)} onChange={setModelId} />}
    </div>
    {!agentId && loadError ? <Alert variant="destructive"><AlertDescription className="flex flex-wrap items-center justify-between gap-2"><span>{loadError}</span><Button variant="outline" size="sm" onClick={() => void loadModels()}>Retry</Button></AlertDescription></Alert> : null}
    {!agentId && !loading && !loadError && models.length === 0 ? <Alert><AlertDescription>No eligible Assistant models are configured. Ask an administrator to enable and check an available streaming model with tool support.</AlertDescription></Alert> : null}
    {!agentId && !loading && !loadError && models.length > 0 && !modelId ? <Alert><AlertDescription>Select an eligible model to begin. No default model is configured.</AlertDescription></Alert> : null}
    {agentId ? <AssistantSession key={`agent-${agentId}-${sessionVersion}`} context={context} agentId={agentId} onBusyChange={setBusy} onRetry={retry} /> : modelId ? <AssistantSession key={`${modelId}-${sessionVersion}`} context={context} modelId={modelId} onBusyChange={setBusy} onRetry={retry} /> : null}
  </div>;
}
