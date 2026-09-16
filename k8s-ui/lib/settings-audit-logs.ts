import { z } from "zod";

export const auditLogCategories = ["admin", "resource", "helm", "ai", "other"] as const;
export const auditLogResults = ["requested", "pending", "success", "succeeded", "failure", "failed", "unknown", "denied"] as const;

const auditLogActorSchema = z.object({
  id: z.string().uuid(),
  email: z.string(),
});

const auditLogSchema = z.object({
  id: z.string().uuid(),
  created_at: z.string(),
  actor: auditLogActorSchema.nullable(),
  action: z.string(),
  category: z.enum(auditLogCategories),
  resource_type: z.string(),
  resource_id: z.string(),
  target_user: auditLogActorSchema.nullable(),
  result: z.string(),
  context: z.unknown(),
});

const auditLogsResponseSchema = z.object({
  logs: z.array(auditLogSchema),
  page: z.number().int().min(0),
  limit: z.number().int().min(1),
  total: z.number().int().min(0),
  total_pages: z.number().int().min(1),
});

export type AuditLogCategory = (typeof auditLogCategories)[number];
export type AuditLogResult = (typeof auditLogResults)[number];
export type AuditLog = z.infer<typeof auditLogSchema>;
export type AuditLogsResponse = z.infer<typeof auditLogsResponseSchema>;

export interface AuditLogFilters {
  page: number;
  limit: number;
  category?: AuditLogCategory;
  result?: AuditLogResult;
  actor?: string;
  resource_type?: string;
  action?: string;
  date_from?: string;
  date_to?: string;
}

export class AuditLogRequestError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

function appendFilter(params: URLSearchParams, key: keyof AuditLogFilters, value: string | number | undefined) {
  if (value === undefined) return;
  const text = String(value).trim();
  if (text) params.set(key, text);
}

function auditLogQuery(filters: AuditLogFilters) {
  const params = new URLSearchParams();
  appendFilter(params, "page", filters.page);
  appendFilter(params, "limit", filters.limit);
  appendFilter(params, "category", filters.category);
  appendFilter(params, "result", filters.result);
  appendFilter(params, "actor", filters.actor);
  appendFilter(params, "resource_type", filters.resource_type);
  appendFilter(params, "action", filters.action);
  appendFilter(params, "date_from", filters.date_from);
  appendFilter(params, "date_to", filters.date_to);
  return params;
}

export async function fetchAuditLogs(filters: AuditLogFilters): Promise<AuditLogsResponse> {
  let response: Response;
  try {
    response = await fetch(`/api/settings/audit-logs?${auditLogQuery(filters).toString()}`, {
      method: "GET",
      cache: "no-store",
    });
  } catch {
    throw new AuditLogRequestError(503, "backend_unavailable", "The audit log service is unavailable.");
  }

  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const record = body && typeof body === "object" ? body as Record<string, unknown> : {};
    const detail = record.detail && typeof record.detail === "object" ? record.detail as Record<string, unknown> : {};
    const message = typeof record.message === "string" ? record.message : detail.message;
    const code = typeof record.code === "string" ? record.code : typeof detail.code === "string" ? detail.code : "audit_log_error";
    throw new AuditLogRequestError(response.status, code, typeof message === "string" ? message : "The audit log request could not be completed.");
  }
  return auditLogsResponseSchema.parse(body);
}
