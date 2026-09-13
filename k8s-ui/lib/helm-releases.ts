import { managementRequest, type ResourceApiError } from "@/lib/resource-management";

export type HelmReleaseSummary = {
  name: string;
  namespace: string;
  status: string | null;
  revision: number | null;
  chart: string | null;
  app_version: string | null;
  updated: string | null;
  description: string | null;
};

export type HelmReleaseRevision = {
  revision: number;
  updated: string | null;
  status: string | null;
  chart: string | null;
  app_version: string | null;
  description: string | null;
};

export type HelmReleaseAction = "rollback" | "uninstall" | "upgrade";

export function helmUrl(cluster: string, path = "", namespace?: string) {
  if (!cluster.trim()) throw new Error("Helm release management requires an explicit cluster.");
  const query = new URLSearchParams({ cluster });
  if (namespace !== undefined) query.set("namespace", namespace);
  return `/api/cluster/helm/releases${path}?${query}`;
}

export function helmRequest<T>(url: string, init?: RequestInit): Promise<T> {
  return managementRequest<T>(url, init);
}

export type HelmApiError = ResourceApiError;
