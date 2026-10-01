"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { DashboardShell } from "@/components/dashboard-shell";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { useClusterSelection } from "@/lib/use-cluster-selection";
import { withCluster } from "@/lib/cluster-query";
import {
  deleteConversation,
  getConversation,
  listConversations,
  renameConversation,
  type ConversationDetail,
  type ConversationSummary,
} from "@/lib/assistant/conversations";
import { assistantSelectionUrl, type AssistantMode } from "@/lib/assistant/mode";
import type { BackendUser } from "@/lib/auth-client";
import { resourceSchema, type AssistantContext } from "@/lib/assistant/schemas";
import { AssistantConversation } from "./conversation";

function withConversation(id: string | undefined, mode: AssistantMode, modelId?: string, agentId?: string) {
  const selected = new URL(assistantSelectionUrl(mode, modelId, agentId, window.location.search), window.location.origin);
  if (id) selected.searchParams.set("conversation", id);
  else selected.searchParams.delete("conversation");
  return `${selected.pathname}${selected.search}`;
}

function displayDate(value: string) {
  try { return new Intl.DateTimeFormat(undefined, { dateStyle: "short", timeStyle: "short" }).format(new Date(value)); }
  catch { return value; }
}

export function AssistantView({ user, initial, mode, modelId, agentId, conversationId }: { user: BackendUser; initial: Partial<AssistantContext>; mode: AssistantMode; modelId?: string; agentId?: string; conversationId?: string }) {
  const router = useRouter();
  const selection = useClusterSelection(initial.cluster, true);
  const [namespace, setNamespace] = useState(initial.namespace ?? "");
  const [resourceContext, setResourceContext] = useState({ resource: initial.resource, name: initial.name, release: initial.release });
  const [history, setHistory] = useState<ConversationSummary[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState<string>();
  const [selectedId, setSelectedId] = useState(conversationId);
  const [selectedConversation, setSelectedConversation] = useState<ConversationDetail>();
  const [selectionMode, setSelectionMode] = useState<AssistantMode>(mode);
  const [selectionModelId, setSelectionModelId] = useState(modelId);
  const [selectionAgentId, setSelectionAgentId] = useState(agentId);
  const currentContext = useMemo(() => ({ cluster: selection.cluster, namespace: namespace || undefined, ...resourceContext }), [namespace, resourceContext, selection.cluster]);
  const context = selectedConversation ? {
    cluster: selectedConversation.cluster,
    namespace: selectedConversation.namespace ?? undefined,
    resource: resourceSchema.safeParse(selectedConversation.resource).data,
    name: selectedConversation.name ?? undefined,
    release: selectedConversation.release ?? undefined,
  } : currentContext;
  const active = !selection.loading && !selection.error && selection.clusters.includes(context.cluster);

  const refreshHistory = useCallback(() => {
    setHistoryLoading(true);
    setHistoryError(undefined);
    void listConversations().then(result => setHistory(result.conversations)).catch(error => setHistoryError(error instanceof Error ? error.message : "Conversation history could not be loaded." )).finally(() => setHistoryLoading(false));
  }, []);

  useEffect(() => {
    let cancelled = false;
    setHistoryLoading(true);
    void listConversations().then(result => {
      if (!cancelled) setHistory(result.conversations);
    }).catch(error => {
      if (!cancelled) setHistoryError(error instanceof Error ? error.message : "Conversation history could not be loaded.");
    }).finally(() => { if (!cancelled) setHistoryLoading(false); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!conversationId) return;
    let cancelled = false;
    void getConversation(conversationId).then(detail => {
      if (cancelled) return;
      setSelectedConversation(detail);
      setSelectedId(detail.id);
      setSelectionMode(detail.mode);
      setSelectionModelId(detail.model_id ?? undefined);
      setSelectionAgentId(detail.agent_id ?? undefined);
      setNamespace(detail.namespace ?? "");
      setResourceContext({ resource: resourceSchema.safeParse(detail.resource).data, name: detail.name ?? undefined, release: detail.release ?? undefined });
      if (selection.clusters.includes(detail.cluster)) selection.selectCluster(detail.cluster);
    }).catch(error => { if (!cancelled) setHistoryError(error instanceof Error ? error.message : "The selected conversation could not be opened."); });
    return () => { cancelled = true; };
  }, [conversationId, selection.clusters, selection.selectCluster]);

  const openConversation = useCallback(async (id: string) => {
    setHistoryError(undefined);
    try {
      const detail = await getConversation(id);
      setSelectedConversation(detail);
      setSelectedId(detail.id);
      setSelectionMode(detail.mode);
      setSelectionModelId(detail.model_id ?? undefined);
      setSelectionAgentId(detail.agent_id ?? undefined);
      setNamespace(detail.namespace ?? "");
      setResourceContext({ resource: resourceSchema.safeParse(detail.resource).data, name: detail.name ?? undefined, release: detail.release ?? undefined });
      if (selection.clusters.includes(detail.cluster)) selection.selectCluster(detail.cluster);
      window.history.replaceState(null, "", withConversation(detail.id, detail.mode, detail.model_id ?? undefined, detail.agent_id ?? undefined));
    } catch (error) {
      setHistoryError(error instanceof Error ? error.message : "The conversation could not be opened.");
    }
  }, [selection.clusters, selection.selectCluster]);

  const startNewConversation = useCallback((nextSelection?: { mode: AssistantMode; modelId?: string; agentId?: string }) => {
    setSelectedConversation(undefined);
    setSelectedId(undefined);
    if (nextSelection) {
      setSelectionMode(nextSelection.mode);
      setSelectionModelId(nextSelection.modelId);
      setSelectionAgentId(nextSelection.agentId);
    }
    setHistoryError(undefined);
    window.history.replaceState(null, "", withConversation(undefined, nextSelection?.mode ?? selectionMode, nextSelection?.modelId ?? selectionModelId, nextSelection?.agentId ?? selectionAgentId));
  }, [selectionAgentId, selectionMode, selectionModelId]);

  const handleCreated = useCallback((detail: ConversationDetail) => {
    setSelectedConversation(detail);
    setSelectedId(detail.id);
    setSelectionMode(detail.mode);
    setSelectionModelId(detail.model_id ?? undefined);
    setSelectionAgentId(detail.agent_id ?? undefined);
    setHistory(current => [detail, ...current.filter(item => item.id !== detail.id)]);
    window.history.replaceState(null, "", withConversation(detail.id, detail.mode, detail.model_id ?? undefined, detail.agent_id ?? undefined));
  }, []);

  const handleSaved = useCallback((detail: ConversationDetail) => {
    setSelectedConversation(detail);
    setHistory(current => [detail, ...current.filter(item => item.id !== detail.id)]);
  }, []);

  const removeConversation = async (id: string) => {
    if (!window.confirm("Delete this conversation? This removes its saved messages.")) return;
    try {
      await deleteConversation(id);
      setHistory(current => current.filter(item => item.id !== id));
      if (selectedId === id) startNewConversation();
    } catch (error) {
      setHistoryError(error instanceof Error ? error.message : "The conversation could not be deleted.");
    }
  };

  const renameHistory = async (item: ConversationSummary) => {
    const title = window.prompt("Conversation title", item.title)?.trim();
    if (!title || title === item.title) return;
    try {
      const updated = await renameConversation(item.id, title);
      setHistory(current => current.map(candidate => candidate.id === updated.id ? updated : candidate));
      setSelectedConversation(current => current?.id === updated.id ? { ...current, ...updated } : current);
    } catch (error) {
      setHistoryError(error instanceof Error ? error.message : "The conversation could not be renamed.");
    }
  };

  return <DashboardShell user={user} activeResource="assistant" activeNamespace={namespace} activeCluster={selection.cluster} clusters={selection.clusters}
    onSelectCluster={cluster => { selection.selectCluster(cluster); setNamespace(""); setResourceContext({ resource: undefined, name: undefined, release: undefined }); startNewConversation(); }}
    onNavigate={(resource, nextNamespace) => { if (resource === "assistant") { setNamespace(nextNamespace); setResourceContext({ resource: undefined, name: undefined, release: undefined }); } else router.push(withCluster(`/dashboard?resource=${encodeURIComponent(resource)}&namespace=${encodeURIComponent(nextNamespace)}`, selection.cluster)); }}>
    <div className="flex min-w-0 flex-col gap-4"><div><h1 className="text-2xl font-semibold tracking-tight">AI Assistant</h1><p className="mt-1 text-sm text-muted-foreground">Investigate, diagnose and safely operate Kubernetes with live evidence.</p></div>
      {historyError ? <Alert variant="destructive"><AlertDescription className="flex flex-wrap items-center justify-between gap-2"><span>{historyError}</span><Button variant="outline" size="sm" onClick={refreshHistory}>Retry</Button></AlertDescription></Alert> : null}
      <div className="grid min-w-0 gap-4 lg:grid-cols-[15rem_minmax(0,1fr)]">
        <aside className="rounded-xl border border-border bg-card p-3" aria-label="Conversation history">
          <div className="mb-3 flex items-center justify-between gap-2"><h2 className="text-sm font-semibold">Conversations</h2><Button variant="outline" size="sm" onClick={() => startNewConversation()}>New</Button></div>
          {historyLoading ? <div role="status" className="text-xs text-muted-foreground">Loading history…</div> : history.length === 0 ? <p className="text-xs text-muted-foreground">Your saved conversations will appear here.</p> : <div className="flex max-h-[calc(100dvh-340px)] flex-col gap-1 overflow-y-auto">{history.map(item => <div key={item.id} className={`group rounded-lg border ${selectedId === item.id ? "border-primary bg-primary/5" : "border-transparent hover:border-border"}`}><button type="button" className="w-full px-2.5 py-2 text-left" onClick={() => void openConversation(item.id)}><span className="block truncate text-sm font-medium">{item.title}</span><span className="mt-1 block truncate text-xs text-muted-foreground">{item.cluster} · {displayDate(item.updated_at)}</span></button><div className="flex justify-end gap-1 px-2 pb-1"><Button variant="ghost" size="sm" className="h-6 px-2 text-xs text-muted-foreground" onClick={() => void renameHistory(item)}>Rename</Button><Button variant="ghost" size="sm" className="h-6 px-2 text-xs text-muted-foreground" onClick={() => void removeConversation(item.id)}>Delete</Button></div></div>)}</div>}
        </aside>
        <div className="min-w-0">{selectedId && !selectedConversation ? <div role="status" className="flex items-center gap-2 text-sm text-muted-foreground"><Spinner />Opening conversation…</div> : active ? <AssistantConversation key={`${selectedId ?? "new"}-${context.cluster}-${context.namespace ?? ""}`} context={context} initialMode={selectedConversation?.mode ?? selectionMode} initialModelId={selectedConversation?.model_id ?? selectionModelId} initialAgentId={selectedConversation?.agent_id ?? selectionAgentId} conversation={selectedConversation} onConversationCreated={handleCreated} onConversationSaved={handleSaved} onNewConversation={startNewConversation} /> : <Alert><AlertDescription>{selection.loading ? "Loading clusters…" : selection.error ?? `The saved conversation's cluster (${context.cluster || "unknown"}) is not currently available.`}{!selection.loading && <Button variant="outline" onClick={selection.refreshClusters}>Refresh clusters</Button>}</AlertDescription></Alert>}</div>
      </div>
    </div>
  </DashboardShell>;
}
