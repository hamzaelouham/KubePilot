import { z } from "zod";

export const nameSchema = z.string().min(1).max(253).regex(/^[a-z0-9](?:[-a-z0-9.]*[a-z0-9])?$/);
export const namespaceSchema = z.string().min(1).max(63).regex(/^[a-z0-9](?:[-a-z0-9]*[a-z0-9])?$/);
export const resourceSchema = z.enum(["pods", "deployments", "stateful-sets", "daemon-sets", "services", "nodes", "namespaces", "replica-sets", "replication-controllers", "jobs", "cron-jobs", "persistent-volumes", "persistent-volume-claims", "ingresses", "configmaps", "secrets"]);
export const contextSchema = z.object({
  cluster: z.string().min(1).max(253),
  namespace: namespaceSchema.optional(),
  resource: resourceSchema.optional(),
  name: nameSchema.optional(),
  release: nameSchema.optional(),
}).strict();
export type AssistantContext = z.infer<typeof contextSchema>;
export const proposalSchema = z.object({
  proposal_id: z.string().uuid(),
  arguments: z.object({ action: z.enum(["scale", "restart", "delete", "install", "upgrade", "rollback", "uninstall"]), cluster: z.string(), namespace: z.string(), name: z.string() }).catchall(z.unknown()),
  status: z.string(), expires_at: z.string(), precondition: z.record(z.string(), z.unknown()), result: z.unknown().nullable(),
});
export type ActionProposal = z.infer<typeof proposalSchema>;

export function scrubText(value: string): string {
  return value
    .replace(/-----BEGIN [^-]+-----[\s\S]*?-----END [^-]+-----/g, "[REDACTED PEM]")
    .replace(/(bearer\s+)\S+/gi, "$1[REDACTED]")
    .replace(/((?:password|token|secret|api[_-]?key|authorization|cookie|credential)[\w-]*[\s"']*[:=][\s"']*)[^\s,;"']+/gi, "$1[REDACTED]")
    .replace(/\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g, "[REDACTED JWT]");
}

export function scrubHistory(value: unknown): unknown {
  if (typeof value === "string") return scrubText(value);
  if (Array.isArray(value)) return value.map(scrubHistory);
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).filter(([key]) => !/password|token|secret|credential|kubeconfig|authorization|cookie|^data$|^env$|^annotations$/i.test(key)).map(([key, item]) => [key, scrubHistory(item)]));
  return value;
}
