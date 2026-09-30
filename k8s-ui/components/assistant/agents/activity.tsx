"use client";

import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { agentRequest, agentRunListSchema, type AgentRun } from "@/lib/assistant/agents";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Empty, EmptyHeader, EmptyMedia, EmptyTitle, EmptyDescription } from "@/components/ui/empty";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export function AgentActivity({ agentId }: { agentId: string }) {
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setLoading(true); setError("");
    try { const result = await agentRequest(`/api/assistant/agents/${agentId}/runs?limit=100`, agentRunListSchema); setRuns(result.runs); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Activity could not be loaded."); }
    finally { setLoading(false); }
  }, [agentId]);
  useEffect(() => { const timer = window.setTimeout(() => void load(), 0); return () => window.clearTimeout(timer); }, [load]);
  return <div className="flex flex-col gap-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-sm font-semibold">Run activity</h2><p className="mt-1 text-sm text-muted-foreground">Execution status, timing, safe result codes, and audit-relevant metadata.</p></div><Button type="button" variant="outline" size="sm" onClick={() => void load()} disabled={loading}><RefreshCw className={loading ? "animate-spin" : ""} data-icon="inline-start" />Refresh</Button></div>{error && <Alert variant="destructive"><AlertTitle>Activity unavailable</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}{loading ? <Card><CardContent className="py-8 text-sm text-muted-foreground">Loading run history…</CardContent></Card> : !runs.length ? <Empty className="border"><EmptyHeader><EmptyMedia variant="icon">◷</EmptyMedia><EmptyTitle>No runs yet</EmptyTitle><EmptyDescription>Manual tests and configured automation runs will appear here.</EmptyDescription></EmptyHeader></Empty> : <div className="overflow-x-auto rounded-lg border"><Table><TableHeader><TableRow><TableHead>Status</TableHead><TableHead>Trigger</TableHead><TableHead>Namespace</TableHead><TableHead>Created</TableHead><TableHead>Result</TableHead></TableRow></TableHeader><TableBody>{runs.map(run => <TableRow key={run.id}><TableCell><Badge variant={run.status === "succeeded" ? "secondary" : run.status === "failed" ? "destructive" : "outline"}>{run.status}</Badge></TableCell><TableCell>{run.trigger_type.replace("kubernetes_event", "Kubernetes event")}</TableCell><TableCell>{run.namespace ?? "All namespaces"}</TableCell><TableCell className="whitespace-nowrap text-muted-foreground">{new Date(run.created_at).toLocaleString()}</TableCell><TableCell>{run.result_code ?? run.error_message ?? "—"}</TableCell></TableRow>)}</TableBody></Table></div>}</div>;
}
