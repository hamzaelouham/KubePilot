"use client";

import { useEffect, useRef, useState, type RefObject } from "react";
import { Field } from "@base-ui/react/field";
import { Fieldset } from "@base-ui/react/fieldset";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toast } from "@/components/ui/toast";
import { managementRequest, managementUrl, RESOURCE_TYPES, ResourceApiError, scopeLabel, type ManagedResource, type ResourceScope } from "@/lib/resource-management";

type Props = {
  scope: ResourceScope;
  returnFocus: RefObject<HTMLButtonElement | null>;
  fallbackFocus: RefObject<HTMLDivElement | null>;
  onClose: () => void;
  onCreated: () => void;
  onRefresh: () => Promise<boolean>;
};

export function CreateResourceDialog({ scope, returnFocus, fallbackFocus, onClose, onCreated, onRefresh }: Props) {
  const [yaml, setYaml] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<ResourceApiError | null>(null);
  const [unexpectedError, setUnexpectedError] = useState<Error | null>(null);
  const [refreshFailed, setRefreshFailed] = useState(false);
  const busy = useRef(false);
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const type = RESOURCE_TYPES.find((type) => type.value === scope.resourceType)!;
  const target = scopeLabel(scope);
  if (unexpectedError) throw unexpectedError;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (busy.current || !yaml.trim() || error?.needsRefresh) return;
    busy.current = true;
    setPending(true);
    setError(null);
    try {
      const result = await managementRequest<{ status: string; resource: ManagedResource }>(managementUrl(scope), {
        method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ yaml }),
      });
      if (result?.status !== "created" || !result.resource?.uid) {
        throw new ResourceApiError("operation_outcome_unknown", "The operation outcome is unknown. Refresh inventory before trying again.");
      }
      toast.add({ type: "success", title: `${type.kind} ${result.resource.name} created`, description: target });
      if (alive.current) { onCreated(); onClose(); }
    } catch (error) {
      if (!(error instanceof ResourceApiError)) {
        if (alive.current) setUnexpectedError(error instanceof Error ? error : new Error("Unexpected resource creation failure"));
        return;
      }
      toast.add({ type: "error", title: `${type.kind} creation ${error.needsRefresh ? "needs review" : "failed"}`, description: `${target}. ${error.message}` });
      if (alive.current) setError(error);
    } finally {
      busy.current = false;
      if (alive.current) setPending(false);
    }
  }

  async function refreshBeforeClosing() {
    if (busy.current) return;
    busy.current = true;
    setPending(true);
    setRefreshFailed(false);
    try {
      const success = await onRefresh();
      if (alive.current) { if (success) onClose(); else setRefreshFailed(true); }
    }
    finally { busy.current = false; if (alive.current) setPending(false); }
  }

  return (
    <Dialog open onOpenChange={(open) => { if (!open && !busy.current) onClose(); }}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-2xl" showCloseButton={!pending}
        finalFocus={() => returnFocus.current?.isConnected && !returnFocus.current.disabled ? returnFocus.current : fallbackFocus.current}>
        <DialogHeader>
          <DialogTitle>Create {type.kind}</DialogTitle>
          <DialogDescription>{target}. This creates a new object; it does not update an existing one.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} aria-busy={pending} className="flex min-w-0 flex-col gap-5">
          <p role="status" className="sr-only">{pending ? "Resource request in progress." : ""}</p>
          <Fieldset.Root disabled={pending} className="flex min-w-0 flex-col gap-3">
            <Field.Root name="manifest" invalid={Boolean(error)} className="flex min-w-0 flex-col gap-2">
              <Field.Label className="text-sm font-medium">Resource YAML</Field.Label>
              <Field.Description className="text-sm text-muted-foreground">
                One {type.apiVersion} {type.kind} with an explicit metadata.name.
                {scope.resourceType === "namespaces" ? " Omit metadata.namespace." : ` An omitted metadata.namespace will use ${scope.namespace}.`}
                {" "}Remove server-managed fields and status from exported YAML.
              </Field.Description>
              <Field.Control render={<textarea rows={13} spellCheck={false} autoCapitalize="none" autoComplete="off" />}
                value={yaml} onValueChange={(value) => { setYaml(value); if (!error?.needsRefresh) setError(null); }} required
                className="min-h-64 w-full resize-y rounded-lg border border-input bg-background px-3 py-2 font-mono text-sm outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/50 aria-invalid:border-destructive" />
              {error ? <Field.Description role="alert" className="text-sm text-destructive">{error.message}</Field.Description> : null}
            </Field.Root>
          </Fieldset.Root>
          {error?.needsRefresh ? <p className="text-sm text-muted-foreground">Refresh and review the inventory before starting another create request. No automatic retry was made.</p> : null}
          {refreshFailed ? <p role="alert" className="text-sm text-destructive">Inventory could not be refreshed. Cancel to check the connection and current scope.</p> : null}
          <DialogFooter>
            <Button type="button" variant="outline" disabled={pending} onClick={onClose}>Cancel</Button>
            {error?.needsRefresh ? (
              <Button type="button" disabled={pending} onClick={() => void refreshBeforeClosing()}>{pending ? "Refreshing…" : "Refresh inventory and close"}</Button>
            ) : <Button type="submit" disabled={pending || !yaml.trim()}>{pending ? "Creating…" : `Create ${type.kind}`}</Button>}
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
