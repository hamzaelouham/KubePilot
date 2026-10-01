import { z } from "zod";
import { contextSchema } from "./schemas";

const modeSchema = z.enum(["direct", "agent"]);
const selectionSchema = z.object({
  mode: modeSchema,
  model_id: z.string().uuid().nullable(),
  agent_id: z.string().uuid().nullable(),
}).strict();
const ownerSchema = z.object({ id: z.string().uuid(), email: z.string() }).strict();
export const conversationSummarySchema = z.object({
  id: z.string().uuid(),
  title: z.string(),
  mode: modeSchema,
  model_id: z.string().uuid().nullable(),
  agent_id: z.string().uuid().nullable(),
  cluster: z.string(),
  namespace: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
  owner: ownerSchema.nullable(),
}).strict();
const conversationPartSchema = z.object({
  id: z.string().uuid(),
  sequence: z.number().int().nonnegative(),
  role: z.enum(["user", "assistant"]),
  part_type: z.string(),
  payload: z.record(z.string(), z.unknown()),
  proposal_id: z.string().uuid().nullable(),
  created_at: z.string(),
}).strict();
export const conversationDetailSchema = conversationSummarySchema.extend({
  resource: z.string().nullable(),
  name: z.string().nullable(),
  release: z.string().nullable(),
  parts: z.array(conversationPartSchema),
}).strict();
export const conversationListSchema = z.object({
  conversations: z.array(conversationSummarySchema),
  total: z.number().int().nonnegative(),
}).strict();
export const retentionSchema = z.object({ retention_days: z.number().int().min(1).max(365) }).strict();
export const purgeSchema = z.object({
  deleted: z.number().int().nonnegative(),
  cutoff: z.string(),
  retention_days: z.number().int().min(1).max(365),
}).strict();

export const conversationContextSchema = contextSchema;
export const conversationSelectionSchema = selectionSchema;
export const conversationCreateSchema = selectionSchema.extend({
  title: z.string().max(160).nullable().optional(),
  context: conversationContextSchema,
}).strict();
export const conversationRenameSchema = z.object({ title: z.string().trim().min(1).max(160) }).strict();
export const conversationSaveSchema = selectionSchema.extend({
  context: conversationContextSchema,
  messages: z.array(z.object({
    id: z.string().min(1).max(100),
    role: z.enum(["user", "assistant"]),
    parts: z.array(z.record(z.string(), z.unknown())).min(1).max(100),
  }).strict()).min(1).max(60),
}).strict();

export type ConversationSummary = z.infer<typeof conversationSummarySchema>;
export type ConversationDetail = z.infer<typeof conversationDetailSchema>;
export type ConversationContext = z.infer<typeof conversationContextSchema>;
export type ConversationSelection = z.infer<typeof conversationSelectionSchema>;
export type ConversationMessage = z.infer<typeof conversationSaveSchema>["messages"][number];

export class ConversationRequestError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message); }
}

async function request<T>(path: string, schema: z.ZodType<T>, method = "GET", body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      method,
      cache: "no-store",
      headers: body === undefined ? undefined : { "content-type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ConversationRequestError(0, "network_error", "Cannot reach KubePilot. Try refreshing.");
  }
  const data: unknown = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) {
    const failure = z.object({ code: z.string(), message: z.string() }).safeParse(data);
    throw new ConversationRequestError(response.status, failure.success ? failure.data.code : "unexpected_error", failure.success ? failure.data.message : "The conversation request failed. Refresh before trying again.");
  }
  if (response.status === 204) return undefined as T;
  const parsed = schema.safeParse(data);
  if (!parsed.success) throw new ConversationRequestError(502, "invalid_response", "KubePilot returned an unexpected conversation response.");
  return parsed.data;
}

export function listConversations(search = "") {
  const query = search.trim() ? `?search=${encodeURIComponent(search.trim())}` : "";
  return request(`/api/assistant/conversations${query}`, conversationListSchema);
}

export function createConversation(body: z.infer<typeof conversationCreateSchema>) {
  return request("/api/assistant/conversations", conversationDetailSchema, "POST", conversationCreateSchema.parse(body));
}

export function getConversation(id: string) {
  return request(`/api/assistant/conversations/${encodeURIComponent(id)}`, conversationDetailSchema);
}

export function saveConversation(id: string, body: z.infer<typeof conversationSaveSchema>) {
  return request(`/api/assistant/conversations/${encodeURIComponent(id)}/messages`, conversationDetailSchema, "PUT", conversationSaveSchema.parse(body));
}

export function renameConversation(id: string, title: string) {
  return request(`/api/assistant/conversations/${encodeURIComponent(id)}`, conversationSummarySchema, "PATCH", conversationRenameSchema.parse({ title }));
}

export function deleteConversation(id: string) {
  return request(`/api/assistant/conversations/${encodeURIComponent(id)}`, z.unknown(), "DELETE");
}

export function getRetention() {
  return request("/api/assistant/conversations/retention", retentionSchema);
}

export function updateRetention(retention_days: number) {
  return request("/api/assistant/conversations/retention", retentionSchema, "PUT", retentionSchema.parse({ retention_days }));
}

export function purgeConversations() {
  return request("/api/assistant/conversations/purge", purgeSchema, "POST");
}

export function messagesFromConversation(detail: ConversationDetail) {
  const messages: Array<{ id: string; role: "user" | "assistant"; parts: Array<Record<string, unknown>> }> = [];
  for (const part of detail.parts) {
    const previous = messages.at(-1);
    if (previous && previous.role === part.role) {
      previous.parts.push(part.payload);
    } else {
      messages.push({ id: part.id, role: part.role, parts: [part.payload] });
    }
  }
  return messages;
}
