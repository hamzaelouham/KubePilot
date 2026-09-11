"use client";

import { useEffect, useRef, useState, type RefObject } from "react";
import { Field } from "@base-ui/react/field";
import { AlertDialog, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/toast";
import { managementRequest, managementUrl, ResourceApiError, scopeLabel, type ManagedResource } from "@/lib/resource-management";

type Props = {
  resource: ManagedResource;
  returnFocus: RefObject<HTMLButtonElement | null>;
  fallbackFocus: RefObject<HTMLDivElement | null>;
  onClose: () => void;
  onDeleted: () => void;
  onRefresh: () => Promise<boolean>;
};

export function DeleteResourceDialog({ resource, returnFocus, fallbackFocus, onClose, onDeleted, onRefresh }: Props) {
  const [confirmation, setConfirmation] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<ResourceApiError | null>(null);
  const [unexpectedError, setUnexpectedError] = useState<Error | null>(null);
  const [refreshFailed, setRefreshFailed] = useState(false);
  const busy = useRef(false);
  const alive = useRef(true);
  const cancel = useRef<HTMLButtonElement>(null);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const scope = { cluster: resource.cluster, resourceType: resource.resource_type, namespace: resource.namespace ?? "" };
  const target = `${scopeLabel(scope)} · ${resource.kind} ${resource.name}`;
  if (unexpectedError) throw unexpectedError;
  const impact = resource.resource_type === "namespaces"
    ? "Deleting this Namespace also deletes its contents. This cannot be undone."
    : resource.resource_type === "pods"
      ? "A controller may recreate this Pod. Its running containers will be stopped."
      : "Kubernetes may also remove dependent objects. Running workloads may be interrupted.";

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (busy.current || confirmation !== resource.name || error?.needsRefresh) return;
    busy.current = true;
    setPending(true);
    setError(null);
    try {
      const result = await managementRequest<{ status: string; uid: string }>(managementUrl(scope, resource.name), {
        method: "DELETE", headers: { "content-type": "application/json" },
        body: JSON.stringify({ uid: resource.uid, confirm_name: confirmation }),
      });
      if (result?.status !== "deletion_requested" || result.uid !== resource.uid) {
        throw new ResourceApiError("operation_outcome_unknown", "The operation outcome is unknown. Refresh inventory before trying again.");
      }
      toast.add({ type: "success", title: "Deletion requested", description: `${target}. Removal may still be in progress; refresh to check.` });
      if (alive.current) { onDeleted(); onClose(); }
    } catch (error) {
      if (!(error instanceof ResourceApiError)) {
        if (alive.current) setUnexpectedError(error instanceof Error ? error : new Error("Unexpected resource deletion failure"));
        return;
      }
      toast.add({ type: "error", title: "Deletion needs review", description: `${target}. ${error.message}` });
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
    <AlertDialog open onOpenChange={(open) => { if (!open && !busy.current) onClose(); }}>
      <AlertDialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg" initialFocus={cancel}
        finalFocus={() => returnFocus.current?.isConnected && !returnFocus.current.disabled ? returnFocus.current : fallbackFocus.current}>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete {resource.kind} {resource.name}?</AlertDialogTitle>
          <AlertDialogDescription>{target}. {impact} Normal grace periods and finalizers still apply.</AlertDialogDescription>
        </AlertDialogHeader>
        <form onSubmit={submit} aria-busy={pending} className="flex min-w-0 flex-col gap-5">
          <p role="status" className="sr-only">{pending ? "Deletion request in progress." : ""}</p>
          <Field.Root name="confirmation" disabled={pending} invalid={Boolean(error)} className="flex flex-col gap-2">
            <Field.Label className="text-sm font-medium">Type {resource.name} to confirm</Field.Label>
            <Input value={confirmation} onChange={(event) => { setConfirmation(event.target.value); if (!error?.needsRefresh) setError(null); }} autoComplete="off" spellCheck={false} required />
            <Field.Description className="break-all text-xs text-muted-foreground">Object UID: {resource.uid}. A replacement object requires a new confirmation.</Field.Description>
            {error ? <Field.Description role="alert" className="text-sm text-destructive">{error.message}</Field.Description> : null}
          </Field.Root>
          {error?.needsRefresh ? <p className="text-sm text-muted-foreground">Refresh inventory and review the current object before another request. No automatic retry was made.</p> : null}
          {refreshFailed ? <p role="alert" className="text-sm text-destructive">Inventory could not be refreshed. Cancel to check the connection and current scope.</p> : null}
          <AlertDialogFooter>
            <AlertDialogCancel ref={cancel} disabled={pending}>Cancel</AlertDialogCancel>
            {error?.needsRefresh ? (
              <Button type="button" disabled={pending} onClick={() => void refreshBeforeClosing()}>{pending ? "Refreshing…" : "Refresh inventory and close"}</Button>
            ) : <Button type="submit" variant="destructive" disabled={pending || confirmation !== resource.name}>{pending ? "Requesting deletion…" : "Delete resource"}</Button>}
          </AlertDialogFooter>
        </form>
      </AlertDialogContent>
    </AlertDialog>
  );
}
