export const RESOURCE_TYPES = [
  { value: "pods", label: "Pods", kind: "Pod", apiVersion: "v1" },
  { value: "deployments", label: "Deployments", kind: "Deployment", apiVersion: "apps/v1" },
  { value: "namespaces", label: "Namespaces", kind: "Namespace", apiVersion: "v1" },
  { value: "services", label: "Services", kind: "Service", apiVersion: "v1" },
  { value: "stateful-sets", label: "StatefulSets", kind: "StatefulSet", apiVersion: "apps/v1" },
  { value: "daemon-sets", label: "DaemonSets", kind: "DaemonSet", apiVersion: "apps/v1" },
  { value: "jobs", label: "Jobs", kind: "Job", apiVersion: "batch/v1" },
  { value: "cron-jobs", label: "CronJobs", kind: "CronJob", apiVersion: "batch/v1" },
] as const;

export type ResourceType = typeof RESOURCE_TYPES[number]["value"];
export type ResourceScope = { cluster: string; resourceType: ResourceType; namespace: string };
export type ManagedResource = {
  cluster: string;
  cluster_id: string;
  resource_type: ResourceType;
  api_version: string;
  kind: string;
  name: string;
  namespace: string | null;
  uid: string;
  status: string;
  health: "healthy" | "warning" | "error" | "unknown";
  deletion_timestamp: string | null;
  delete_blocked_reason: string | null;
};

export function managementUrl(scope: ResourceScope, name?: string): string {
  if (!scope.cluster.trim()) throw new Error("Management requires an explicit cluster.");
  const query = new URLSearchParams({ cluster: scope.cluster });
  if (scope.resourceType !== "namespaces" && scope.namespace) query.set("namespace", scope.namespace);
  return `/api/cluster/manage-resources/${scope.resourceType}${name ? `/${encodeURIComponent(name)}` : ""}?${query}`;
}

export function scopeLabel(scope: ResourceScope): string {
  return `Cluster ${scope.cluster} · ${scope.resourceType === "namespaces" ? "cluster-wide" : `namespace ${scope.namespace || "(all)"}`}`;
}

export class ResourceApiError extends Error {
  constructor(public code: string, message: string, public status = 0) { super(message); }
  get needsRefresh() {
    return ["operation_outcome_unknown", "resource_conflict", "resource_not_found"].includes(this.code);
  }
}

export async function managementRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const mutation = init?.method === "POST" || init?.method === "DELETE";
  let response: Response;
  try {
    response = await fetch(url, { ...init, cache: "no-store" });
  } catch (error) {
    if (!(error instanceof TypeError)) throw error; // Includes aborts and unexpected failures.
    throw new ResourceApiError(mutation ? "operation_outcome_unknown" : "backend_unavailable",
      mutation ? "The response was lost. The operation may have completed; refresh inventory before trying again."
        : "Unable to reach the backend. Refresh to try again.");
  }
  let body;
  try {
    body = await response.json();
  } catch (error) {
    if (!(error instanceof SyntaxError || error instanceof TypeError)) throw error;
    throw new ResourceApiError(mutation ? "operation_outcome_unknown" : "invalid_response",
      mutation ? "The operation outcome is unknown. Refresh inventory before trying again."
        : "The backend returned an unreadable response. Refresh to try again.");
  }
  if (!response.ok) {
    // A proxy transport failure cannot prove that a write did not reach Kubernetes.
    if (mutation && response.status >= 500 && !["audit_unavailable", "cluster_unavailable", "cluster_error"].includes(body?.code)) {
      throw new ResourceApiError("operation_outcome_unknown", "The operation outcome is unknown. Refresh inventory before trying again.", response.status);
    }
    throw new ResourceApiError(typeof body?.code === "string" ? body.code : "request_failed",
      typeof body?.message === "string" ? body.message : "The request failed. Refresh your session or inventory and try again.", response.status);
  }
  return body as T;
}
