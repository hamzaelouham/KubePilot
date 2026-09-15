import { z } from "zod";
import { providerIds, type ProviderId } from "@/lib/settings-providers";

export const modelCapabilitiesSchema = z.object({
  streaming: z.boolean(),
  tools: z.boolean(),
  reasoning: z.boolean(),
  vision: z.boolean(),
  large_context: z.boolean(),
});

export const modelSchema = z.object({
  id: z.string().uuid(),
  provider_id: z.enum(providerIds),
  provider_name: z.string(),
  external_model_id: z.string(),
  friendly_name: z.string(),
  enabled: z.boolean(),
  is_default: z.boolean(),
  capabilities: modelCapabilitiesSchema,
  availability: z.enum(["unknown", "available", "unavailable"]),
  availability_message: z.string().nullable(),
  availability_checked_at: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});

const modelsResponseSchema = z.object({ models: z.array(modelSchema) });

export type ModelCapabilities = z.infer<typeof modelCapabilitiesSchema>;
export type AIModel = z.infer<typeof modelSchema>;
export type ModelWritePayload = {
  provider_id: ProviderId;
  external_model_id: string;
  friendly_name: string;
  enabled: boolean;
  capabilities: ModelCapabilities;
};

async function modelRequest<T>(path: string, init: RequestInit, schema: z.ZodType<T>): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      cache: "no-store",
      headers: { "content-type": "application/json", ...init.headers },
    });
  } catch {
    throw new Error("The AI model service is unavailable.");
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const record = body && typeof body === "object" ? body as Record<string, unknown> : {};
    const detail = record.detail && typeof record.detail === "object" ? record.detail as Record<string, unknown> : {};
    const message = typeof record.message === "string" ? record.message : detail.message;
    throw new Error(typeof message === "string" ? message : "The model request could not be completed.");
  }
  return schema.parse(body);
}

export function fetchModels() {
  return modelRequest("/api/settings/models", { method: "GET" }, modelsResponseSchema);
}

export function createModel(payload: ModelWritePayload) {
  return modelRequest("/api/settings/models", { method: "POST", body: JSON.stringify(payload) }, modelSchema);
}

export function updateModel(modelId: string, payload: ModelWritePayload) {
  return modelRequest(`/api/settings/models/${encodeURIComponent(modelId)}`, { method: "PUT", body: JSON.stringify(payload) }, modelSchema);
}

export function deleteModel(modelId: string) {
  return modelRequest(`/api/settings/models/${encodeURIComponent(modelId)}`, { method: "DELETE" }, modelSchema);
}

export function checkModel(modelId: string) {
  return modelRequest(`/api/settings/models/${encodeURIComponent(modelId)}/check`, { method: "POST", body: "{}" }, modelSchema);
}

export function setDefaultModel(modelId: string) {
  return modelRequest(`/api/settings/models/${encodeURIComponent(modelId)}/default`, { method: "POST", body: "{}" }, modelSchema);
}
