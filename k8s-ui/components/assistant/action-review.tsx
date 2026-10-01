"use client";

import { useState } from "react";
import Link from "next/link";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { type ActionProposal, proposalSchema } from "@/lib/assistant/schemas";

const actionLabels: Record<ActionProposal["arguments"]["action"], string> = {
  scale: "scale",
  restart: "restart",
  delete: "deletion",
  install: "Helm installation",
  upgrade: "Helm upgrade",
  rollback: "Helm rollback",
  uninstall: "Helm uninstall",
};

export function ActionReview({ id, cluster, disabled, onResult }: { id: string; cluster: string; disabled: boolean; onResult: (result: ActionProposal) => void }) {
  const [proposal, setProposal] = useState<ActionProposal | null>(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [confirmation, setConfirmation] = useState("");
  const [expired, setExpired] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const load = async () => {
    setBusy(true); setError(null);
    try {
      const response = await fetch(`/api/assistant/proposals/${encodeURIComponent(id)}`, { cache: "no-store" });
      const data: unknown = await response.json();
      if (!response.ok) throw new Error(z.object({ message: z.string() }).parse(data).message);
      const loaded = proposalSchema.parse(data);
      setProposal(loaded); setExpired(Date.parse(loaded.expires_at) <= Date.now()); setConfirmation(""); setOpen(true);
    } catch (error) { setError(error instanceof Error ? error.message : "Unable to load this proposal."); }
    finally { setBusy(false); }
  };
  const decide = async (approved: boolean) => {
    if (!proposal) return;
    setBusy(true); setError(null);
    try {
      const response = await fetch(`/api/assistant/proposals/${encodeURIComponent(id)}`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ cluster, confirm_name: approved ? confirmation : proposal.arguments.name, approved }),
      });
      const data: unknown = await response.json();
      if (!response.ok) throw new Error(z.object({ message: z.string() }).parse(data).message);
      const result = proposalSchema.parse(data);
      setProposal(result); setOpen(false); onResult(result);
    } catch (error) { setError(error instanceof Error ? error.message : "The operation result is unknown. Refresh the proposal before any further action."); }
    finally { setBusy(false); }
  };
  const pending = !proposal || proposal.status === "pending";
  const actionLabel = proposal ? actionLabels[proposal.arguments.action] : "operation";
  return <div className="flex flex-col gap-3">
    <div className="flex flex-wrap items-center gap-2">
      <Badge variant="outline">{pending ? "Waiting for confirmation" : proposal.status}</Badge>
      <Button variant="outline" disabled={busy || disabled} onClick={() => void load()}>{busy ? <Spinner data-icon="inline-start" /> : null}{pending ? "Review proposed action" : "View operation result"}</Button>
      {proposal?.result && typeof proposal.result === "object" && "job_id" in proposal.result ? <Button variant="outline" nativeButton={false} render={<Link href={`/background-jobs?cluster=${encodeURIComponent(cluster)}`} />}>Track background job</Button> : null}
    </div>
    {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
    <Dialog open={open} onOpenChange={value => { if (!busy) setOpen(value); }}>
      <DialogContent>
        <DialogHeader><DialogTitle>Review proposed {actionLabel}</DialogTitle><DialogDescription>This side effect requires explicit approval for this exact target and action. These parameters were loaded from the backend proposal. Closing this dialog does not approve it.</DialogDescription></DialogHeader>
        {proposal && <div className="flex flex-col gap-4">
          <dl className="grid grid-cols-2 gap-2 text-sm">{Object.entries(proposal.arguments).map(([key, value]) => <div key={key}><dt className="text-muted-foreground">{key.replaceAll("_", " ")}</dt><dd className="break-all font-medium">{String(value)}</dd></div>)}</dl>
          <p className="text-sm text-muted-foreground">Expires {new Date(proposal.expires_at).toLocaleTimeString()}. Status: {proposal.status}.</p>
          {proposal.status === "pending" ? <label className="grid gap-2 text-sm font-medium" htmlFor={`confirm-${id}`}>Type {proposal.arguments.name} to confirm<Input id={`confirm-${id}`} autoComplete="off" value={confirmation} onChange={event => setConfirmation(event.target.value)} /></label> : <pre className="max-h-52 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(proposal.result, null, 2)}</pre>}
          {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
        </div>}
        <DialogFooter><Button variant="outline" onClick={() => setOpen(false)} disabled={busy}>Close</Button>{proposal?.status === "pending" && <><Button variant="outline" disabled={busy || disabled} onClick={() => void decide(false)}>Reject action</Button><Button variant="destructive" disabled={busy || disabled || confirmation !== proposal.arguments.name || proposal.arguments.cluster !== cluster || expired} onClick={() => void decide(true)}>{busy ? <Spinner data-icon="inline-start" /> : null}Approve and execute</Button></>}</DialogFooter>
      </DialogContent>
    </Dialog>
  </div>;
}
