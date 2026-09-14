import { z } from "zod";

export const providerIds = ["openai", "openrouter", "ollama"] as const;
export type ProviderId = (typeof providerIds)[number];
export type ApiKeyAction = "unchanged" | "replace" | "clear";

const providerSchema = z.object({
  provider_id: z.enum(providerIds),
  name: z.string(),
  base_url: z.string().nullable(),
  credential_required: z.boolean(),
  api_key_configured: z.boolean(),
  status: z.enum(["configured", "not_configured"]),
  updated_at: z.string().nullable(),
});

const providersResponseSchema = z.object({ providers: z.array(providerSchema) });
const providerTestSchema = z.object({
  provider_id: z.enum(providerIds),
  status: z.enum(["connected", "not_configured", "blocked", "failed"]),
  message: z.string(),
});

export type ProviderSummary = z.infer<typeof providerSchema>;
export type ProviderTestResult = z.infer<typeof providerTestSchema>;

async function providerRequest<T>(path: string, init: RequestInit, schema: z.ZodType<T>): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      cache: "no-store",
      headers: { "content-type": "application/json", ...init.headers },
    });
  } catch {
    throw new Error("The AI provider service is unavailable.");
  }

  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const record = body && typeof body === "object" ? body as Record<string, unknown> : {};
    const detail = record.detail && typeof record.detail === "object" ? record.detail as Record<string, unknown> : {};
    const message = typeof record.message === "string" ? record.message : detail.message;
    throw new Error(typeof message === "string" ? message : "The provider request could not be completed.");
  }
  return schema.parse(body);
}

export function fetchProviders() {
  return providerRequest("/api/settings/providers", { method: "GET" }, providersResponseSchema);
}

export function saveProvider(
  providerId: ProviderId,
  payload: { base_url: string; api_key_action: ApiKeyAction; api_key?: string },
) {
  return providerRequest(`/api/settings/providers/${encodeURIComponent(providerId)}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  }, providerSchema);
}

export function testProvider(providerId: ProviderId) {
  return providerRequest(`/api/settings/providers/${encodeURIComponent(providerId)}`, {
    method: "POST",
    body: "{}",
  }, providerTestSchema);
}
