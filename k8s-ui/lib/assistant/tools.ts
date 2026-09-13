import { tool } from "ai";
import { z } from "zod";
import { backendRequest } from "./backend";
import { type AssistantContext, nameSchema, namespaceSchema, resourceSchema } from "./schemas";

export function createTools(cookie: string, context: AssistantContext, signal: AbortSignal) {
  const send = (path: string, input: Record<string, unknown>) => backendRequest(cookie, `/assistant/${path}`, { namespace: context.namespace, ...input, cluster: context.cluster }, signal);
  const namespace = namespaceSchema.optional().describe("Defaults to the selected namespace. Omit for all namespaces when no namespace is selected.");
  const resource = z.object({ resource_type: resourceSchema, namespace });
  const identity = resource.extend({ name: nameSchema });
  const target = z.object({ name: nameSchema, namespace: namespaceSchema.describe("Explicit target namespace, required for every proposed change.") });
  const read = (name: string, input: Record<string, unknown>) => send("read", { tool: name, ...input });
  const propose = (action: string, input: Record<string, unknown>) => send("proposals", { action, ...input });
  return {
    listClusters: tool({ description: "List registered cluster names/status. All other tools are locked to the selected cluster; ask the user to switch in the header for another cluster.", inputSchema: z.object({}), execute: () => read("listClusters", {}) }),
    listNamespaces: tool({ description: "Discover namespaces in the selected cluster.", inputSchema: z.object({}), execute: () => read("listNamespaces", {}) }),
    listResources: tool({ description: "List up to 100 resources with safe status and owner references. Includes PVCs, Ingresses, and metadata-only Secrets/ConfigMaps. Truncated inventory is not complete.", inputSchema: resource, execute: input => send("observe/list", input) }),
    inspectResource: tool({ description: "Inspect conditions, container restarts/termination and waiting reasons, desired/available replicas, owners and storage binding. Never returns manifests or environment/Secret values.", inputSchema: identity, execute: input => send("observe/inspect", input) }),
    getPodLogs: tool({ description: "Get a bounded credential-scrubbed Pod log excerpt. Select a container if necessary; previous=true reads the last crashed container.", inputSchema: z.object({ name: nameSchema, namespace: namespaceSchema, container: nameSchema.optional(), previous: z.boolean().optional() }), execute: input => send("observe/logs", { ...input, resource_type: "pods" }) }),
    getEvents: tool({ description: "Read namespace events, optionally filtered to a resource name and warnings. Correlate timestamps and reasons with workload failures.", inputSchema: z.object({ namespace: namespaceSchema, name: nameSchema.optional(), warnings_only: z.boolean().optional() }), execute: input => send("observe/events", input) }),
    getResourceUsage: tool({ description: "Read node metrics, or namespace workload metrics when a namespace is supplied. Report Metrics API unavailability honestly.", inputSchema: z.object({ namespace }), execute: input => read("getResourceUsage", input) }),
    listHelmReleases: tool({ description: "List live Helm releases in the selected cluster, including externally installed applications.", inputSchema: z.object({ namespace }), execute: input => read("listHelmReleases", input) }),
    getHelmHistory: tool({ description: "Read revisions of a Helm release.", inputSchema: target, execute: input => read("getHelmHistory", input) }),
    listRepositories: tool({ description: "List configured public Helm repositories for explicit upgrade source selection.", inputSchema: z.object({}), execute: () => read("listRepositories", {}) }),
    searchPackages: tool({ description: "Search Helm packages on Artifact Hub. Use returned package/repository identity; never invent a package id.", inputSchema: z.object({ query: z.string().max(120) }), execute: input => read("searchPackages", input) }),
    getPackage: tool({ description: "Read available chart versions and verified package identity.", inputSchema: z.object({ repository_name: nameSchema, package_name: nameSchema }), execute: input => read("getPackage", input) }),
    getJobStatus: tool({ description: "Check an installation/upgrade/rollback/uninstall job in this cluster. Queued or running is not success.", inputSchema: z.object({ name: z.string().uuid().describe("job_id") }), execute: input => read("getJobStatus", input) }),
    proposeScale: tool({ description: "Propose scaling a Deployment. Creates a review card ONLY; user confirmation is required and this tool cannot execute the change.", inputSchema: target.extend({ replicas: z.number().int().min(0).max(10000) }), execute: input => propose("scale", input) }),
    proposeRestart: tool({ description: "Propose restarting a Deployment, which replaces its Pods. Creates a review card; never executes.", inputSchema: target, execute: input => propose("restart", input) }),
    proposeDelete: tool({ description: "Propose deleting one supported resource. Explain impact first. Server snapshots UID; user reviews and confirms separately.", inputSchema: target.extend({ resource_type: z.enum(["pods", "deployments", "stateful-sets", "daemon-sets", "services", "jobs", "cron-jobs"]) }), execute: input => propose("delete", input) }),
    proposeInstall: tool({ description: "Propose installing a verified Artifact Hub Helm package. Requires explicit package, version, namespace and release name. Creates a confirmation card.", inputSchema: target.extend({ package_id: z.string().min(1).max(253), package_name: nameSchema, repository_name: nameSchema, version: z.string().min(1).max(64) }), execute: input => propose("install", input) }),
    proposeUpgrade: tool({ description: "Propose an upgrade with an explicitly selected configured repository id, chart and version. Creates a confirmation card; does not run Helm.", inputSchema: target.extend({ repository_id: z.string().uuid(), chart_name: nameSchema, version: z.string().min(1).max(64) }), execute: input => propose("upgrade", input) }),
    proposeRollback: tool({ description: "Propose rollback to the previous Helm revision. The reviewed revision must remain current at confirmation.", inputSchema: target, execute: input => propose("rollback", input) }),
    proposeUninstall: tool({ description: "Propose uninstalling a Helm release and its managed resources. Requires separate user confirmation.", inputSchema: target, execute: input => propose("uninstall", input) }),
  };
}
