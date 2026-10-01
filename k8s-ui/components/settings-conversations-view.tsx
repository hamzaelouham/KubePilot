"use client";

import { useCallback, useEffect, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  deleteConversation,
  getConversation,
  getRetention,
  listConversations,
  purgeConversations,
  renameConversation,
  updateRetention,
  type ConversationDetail,
  type ConversationSummary,
} from "@/lib/assistant/conversations";

function date(value: string) {
  try { return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)); }
  catch { return value; }
}

export function SettingsConversationsView() {
  const [items, setItems] = useState<ConversationSummary[]>([]);
  const [selected, setSelected] = useState<ConversationDetail>();
  const [search, setSearch] = useState("");
  const [retention, setRetention] = useState("30");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string>();
  const [notice, setNotice] = useState<string>();

  const refresh = useCallback(async (query = search) => {
    setLoading(true);
    setError(undefined);
    try {
      const [conversationResult, retentionResult] = await Promise.all([listConversations(query), getRetention()]);
      setItems(conversationResult.conversations);
      setRetention(String(retentionResult.retention_days));
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Conversation administration could not be loaded.");
    } finally { setLoading(false); }
  }, [search]);

  useEffect(() => { void refresh(""); }, [refresh]);

  const inspect = async (id: string) => {
    setWorking(true); setError(undefined); setNotice(undefined);
    try { setSelected(await getConversation(id)); }
    catch (failure) { setError(failure instanceof Error ? failure.message : "The conversation could not be opened."); }
    finally { setWorking(false); }
  };

  const saveTitle = async () => {
    if (!selected) return;
    setWorking(true); setError(undefined); setNotice(undefined);
    try {
      const updated = await renameConversation(selected.id, selected.title);
      setSelected(current => current ? { ...current, ...updated } : current);
      setItems(current => current.map(item => item.id === updated.id ? updated : item));
      setNotice("Conversation title updated.");
    } catch (failure) { setError(failure instanceof Error ? failure.message : "The conversation title could not be updated."); }
    finally { setWorking(false); }
  };

  const remove = async (id: string) => {
    if (!window.confirm("Delete this conversation and its saved messages?")) return;
    setWorking(true); setError(undefined); setNotice(undefined);
    try {
      await deleteConversation(id);
      setItems(current => current.filter(item => item.id !== id));
      if (selected?.id === id) setSelected(undefined);
      setNotice("Conversation deleted.");
    } catch (failure) { setError(failure instanceof Error ? failure.message : "The conversation could not be deleted."); }
    finally { setWorking(false); }
  };

  const saveRetention = async () => {
    const value = Number(retention);
    if (!Number.isInteger(value) || value < 1 || value > 365) { setError("Retention must be a whole number from 1 to 365 days."); return; }
    setWorking(true); setError(undefined); setNotice(undefined);
    try { const result = await updateRetention(value); setRetention(String(result.retention_days)); setNotice("Conversation retention updated."); }
    catch (failure) { setError(failure instanceof Error ? failure.message : "Retention could not be updated."); }
    finally { setWorking(false); }
  };

  const purge = async () => {
    if (!window.confirm("Purge all conversations older than the configured retention period?")) return;
    setWorking(true); setError(undefined); setNotice(undefined);
    try { const result = await purgeConversations(); setNotice(`${result.deleted} expired conversation${result.deleted === 1 ? "" : "s"} purged.`); await refresh(); }
    catch (failure) { setError(failure instanceof Error ? failure.message : "Expired conversations could not be purged."); }
    finally { setWorking(false); }
  };

  return <div className="space-y-6">
    <div><h2 className="text-xl font-semibold">Assistant conversations</h2><p className="mt-1 text-sm text-muted-foreground">Inspect and manage account-backed conversation records. Administrative access and mutations are audited.</p></div>
    {error ? <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert> : null}
    {notice ? <Alert><AlertDescription>{notice}</AlertDescription></Alert> : null}
    <Card><CardHeader><CardTitle>Retention</CardTitle><CardDescription>Expired conversations are removed by the worker and can also be purged manually. Allowed range: 1–365 days.</CardDescription></CardHeader><CardContent className="flex flex-wrap items-end gap-3"><label className="grid gap-1 text-sm"><span>Days</span><Input type="number" min={1} max={365} value={retention} onChange={event => setRetention(event.target.value)} className="w-28" /></label><Button disabled={working} onClick={() => void saveRetention()}>Save retention</Button><Button variant="outline" disabled={working} onClick={() => void purge()}>Purge expired</Button></CardContent></Card>
    <Card><CardHeader><CardTitle>All conversations</CardTitle><CardDescription>Search by title, cluster, namespace, or owner email.</CardDescription></CardHeader><CardContent className="space-y-4"><form className="flex gap-2" onSubmit={event => { event.preventDefault(); void refresh(search); }}><Input aria-label="Search conversations" placeholder="Search conversations" value={search} onChange={event => setSearch(event.target.value)} /><Button type="submit" variant="outline" disabled={loading}>Search</Button></form>{loading ? <div role="status" className="text-sm text-muted-foreground">Loading conversations…</div> : items.length === 0 ? <p className="text-sm text-muted-foreground">No conversations match this search.</p> : <div className="divide-y rounded-lg border">{items.map(item => <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 p-3"><div className="min-w-0"><p className="truncate font-medium">{item.title}</p><p className="truncate text-xs text-muted-foreground">{item.owner?.email ?? "Unknown owner"} · {item.cluster} · updated {date(item.updated_at)}</p></div><div className="flex gap-2"><Button variant="outline" size="sm" disabled={working} onClick={() => void inspect(item.id)}>Open</Button><Button variant="outline" size="sm" disabled={working} onClick={() => void remove(item.id)}>Delete</Button></div></div>)}</div>}</CardContent></Card>
    {selected ? <Card><CardHeader><CardTitle>Conversation record</CardTitle><CardDescription>{selected.owner?.email ?? "Unknown owner"} · {selected.parts.length} saved parts · created {date(selected.created_at)}</CardDescription></CardHeader><CardContent className="space-y-4"><div className="flex flex-wrap gap-2"><Input aria-label="Conversation title" value={selected.title} onChange={event => setSelected(current => current ? { ...current, title: event.target.value } : current)} /><Button disabled={working || !selected.title.trim()} onClick={() => void saveTitle()}>Rename</Button><Button variant="outline" disabled={working} onClick={() => void remove(selected.id)}>Delete</Button></div><div className="max-h-[28rem] space-y-3 overflow-y-auto rounded-lg border p-3">{selected.parts.map(part => <div key={part.id} className="rounded-md bg-muted/50 p-3"><p className="mb-1 text-xs font-medium uppercase text-muted-foreground">{part.role} · {part.part_type}</p><pre className="whitespace-pre-wrap break-words text-xs">{JSON.stringify(part.payload, null, 2)}</pre></div>)}</div></CardContent></Card> : null}
  </div>;
}
