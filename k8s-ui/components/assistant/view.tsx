"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { DashboardShell } from "@/components/dashboard-shell";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useClusterSelection } from "@/lib/use-cluster-selection";
import { withCluster } from "@/lib/cluster-query";
import type { BackendUser } from "@/lib/auth-client";
import type { AssistantContext } from "@/lib/assistant/schemas";
import { AssistantConversation } from "./conversation";

export function AssistantView({ user, initial }: { user: BackendUser; initial: Partial<AssistantContext> }) {
  const router = useRouter();
  const selection = useClusterSelection(initial.cluster, true);
  const [namespace, setNamespace] = useState(initial.namespace ?? "");
  const [resourceContext, setResourceContext] = useState({ resource: initial.resource, name: initial.name, release: initial.release });
  const active = !selection.loading && !selection.error && selection.clusters.includes(selection.cluster);
  const context = { cluster: selection.cluster, namespace: namespace || undefined, ...resourceContext };
  return <DashboardShell user={user} activeResource="assistant" activeNamespace={namespace} activeCluster={selection.cluster} clusters={selection.clusters}
    onSelectCluster={cluster => { selection.selectCluster(cluster); setNamespace(""); setResourceContext({ resource: undefined, name: undefined, release: undefined }); }}
    onNavigate={(resource, nextNamespace) => { if (resource === "assistant") { setNamespace(nextNamespace); setResourceContext({ resource: undefined, name: undefined, release: undefined }); } else router.push(withCluster(`/dashboard?resource=${encodeURIComponent(resource)}&namespace=${encodeURIComponent(nextNamespace)}`, selection.cluster)); }}>
    <div className="flex min-w-0 flex-col gap-4"><div><h1 className="text-2xl font-semibold tracking-tight">AI Assistant</h1><p className="mt-1 text-sm text-muted-foreground">Investigate, diagnose and safely operate Kubernetes with live evidence.</p></div>
      {active ? <AssistantConversation key={JSON.stringify(context)} context={context} /> : <Alert><AlertDescription>{selection.loading ? "Loading clusters…" : selection.error ?? "Select an active cluster to begin."}{!selection.loading && <Button variant="outline" onClick={selection.refreshClusters}>Refresh clusters</Button>}</AlertDescription></Alert>}
    </div>
  </DashboardShell>;
}
