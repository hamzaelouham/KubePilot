"use client";

import { useMemo, useState } from "react";
import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport, isToolUIPart } from "ai";
import { Conversation, ConversationContent, ConversationEmptyState, ConversationScrollButton } from "@/components/ai-elements/conversation";
import { Message, MessageContent, MessageResponse } from "@/components/ai-elements/message";
import { PromptInput, PromptInputBody, PromptInputTextarea, PromptInputFooter, PromptInputSubmit } from "@/components/ai-elements/prompt-input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import type { AssistantContext } from "@/lib/assistant/schemas";
import { AssistantTool } from "./tool-result";

export function AssistantConversation({ context }: { context: AssistantContext }) {
  const [text, setText] = useState("");
  const transport = useMemo(() => new DefaultChatTransport({ api: "/api/assistant", body: { context }, fetch: async (url, init) => {
    const response = await fetch(url, init);
    if (!response.ok) {
      const body = await response.json().catch(() => null) as { message?: string } | null;
      throw new Error(body?.message ?? `Assistant request failed (${response.status}).`);
    }
    return response;
  } }), [context]);
  const { messages, sendMessage, status, error, stop, setMessages, clearError } = useChat({ transport });
  const busy = status === "submitted" || status === "streaming";
  const send = (value: string) => { if (!busy && value.trim()) { clearError(); void sendMessage({ text: value.trim() }); } };
  return <div className="flex h-[calc(100dvh-280px)] min-h-[480px] min-w-0 flex-col gap-3">
    <div className="flex flex-wrap items-center justify-between gap-2"><p className="text-sm text-muted-foreground">{context.cluster} / {context.namespace ?? "all namespaces"}{context.name ? ` / ${context.name}` : ""}{context.release ? ` / release ${context.release}` : ""}</p><Button variant="outline" size="sm" disabled={busy} onClick={() => { setMessages([]); clearError(); }}>New conversation</Button></div>
    <Conversation><ConversationContent>
      {!messages.length && <ConversationEmptyState title="Investigate your cluster" description="Ask about workloads, events, logs, storage or Helm applications. Every change requires your explicit review."><div className="flex flex-col gap-4"><h2 className="text-lg font-medium">Investigate your cluster</h2><p className="text-sm text-muted-foreground">Read live evidence, diagnose failures, and review changes before execution.</p><div className="flex flex-wrap gap-2">{["Show unhealthy workloads", "Show recent warning events", "List installed Helm applications"].map(prompt => <Button key={prompt} variant="outline" onClick={() => send(prompt)}>{prompt}</Button>)}</div></div></ConversationEmptyState>}
      {messages.map(message => <Message key={message.id} from={message.role}><MessageContent>{message.parts.map((part, index) => part.type === "text" ? <MessageResponse key={index} isAnimating={busy} components={{ img: () => null, a: ({ children }) => <span>{children}</span> }}>{part.text}</MessageResponse> : isToolUIPart(part) ? <AssistantTool key={part.toolCallId} part={part} cluster={context.cluster} disabled={busy} followUp={send} onResult={result => send(`The confirmation result for proposal ${result.proposal_id} is ${result.status}: ${JSON.stringify(result.result)}. Explain the outcome; if there is a job_id, check its status. Do not repeat the action.`)} /> : null)}</MessageContent></Message>)}
      {busy && <div role="status" className="flex items-center gap-2 text-sm text-muted-foreground"><Spinner />Inspecting operational evidence…</div>}
    </ConversationContent><ConversationScrollButton /></Conversation>
    {error && <Alert variant="destructive"><AlertDescription>{error.message}</AlertDescription></Alert>}
    <PromptInput onSubmit={({ text: value }) => { send(value); setText(""); }}>
      <PromptInputBody><PromptInputTextarea aria-label="Ask KubePilot" placeholder="Why is my deployment unavailable?" value={text} onChange={event => setText(event.target.value)} maxLength={8000} disabled={busy} /></PromptInputBody>
      <PromptInputFooter><span className="text-xs text-muted-foreground">Do not paste credentials. Reads run directly; changes require confirmation.</span><PromptInputSubmit status={status} onStop={() => void stop()} disabled={!busy && !text.trim()} /></PromptInputFooter>
    </PromptInput>
  </div>;
}
