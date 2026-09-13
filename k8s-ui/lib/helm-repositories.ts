import { managementRequest, type ResourceApiError } from "@/lib/resource-management";

export type HelmRepository = {
  id: string;
  name: string;
  url: string;
  created_by_id: string | null;
  updated_by_id: string | null;
  created_at: string;
  updated_at: string;
};

export function helmRepositoryUrl(repositoryId?: string) {
  return `/api/helm/repositories${repositoryId ? `/${encodeURIComponent(repositoryId)}` : ""}`;
}

export function helmRepositoryRequest<T>(url: string, init?: RequestInit) {
  return managementRequest<T>(url, init);
}

export type HelmRepositoryApiError = ResourceApiError;
