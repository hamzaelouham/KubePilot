import { z } from "zod";

export const credentialSchema = z.object({
  credential_key: z.string().min(1),
  display_name: z.string().min(1),
  description: z.string(),
  category: z.enum(["provider", "integration"]),
  configured: z.boolean(),
  updated_at: z.string().nullable(),
}).strict();

export const credentialsResponseSchema = z.object({
  credentials: z.array(credentialSchema),
}).strict();

export type CredentialMetadata = z.infer<typeof credentialSchema>;

async function credentialRequest<T>(path: string, init: RequestInit, schema: z.ZodType<T>): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      cache: "no-store",
      headers: { ...(init.body === undefined ? {} : { "content-type": "application/json" }), ...init.headers },
    });
  } catch {
    throw new Error("The credential service is unavailable.");
  }

  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const record = body && typeof body === "object" ? body as Record<string, unknown> : {};
    const detail = record.detail && typeof record.detail === "object" ? record.detail as Record<string, unknown> : {};
    const message = typeof record.message === "string" ? record.message : detail.message;
    throw new Error(typeof message === "string" ? message : "The credential request could not be completed.");
  }
  const parsed = schema.safeParse(body);
  if (!parsed.success) throw new Error("The credential service returned an invalid response.");
  return parsed.data;
}

export function fetchCredentials() {
  return credentialRequest("/api/settings/credentials", { method: "GET" }, credentialsResponseSchema);
}

export function saveCredential(credentialKey: string, value: string) {
  return credentialRequest(`/api/settings/credentials/${encodeURIComponent(credentialKey)}`, {
    method: "PUT",
    body: JSON.stringify({ value }),
  }, credentialSchema);
}

export function deleteCredential(credentialKey: string) {
  return credentialRequest(`/api/settings/credentials/${encodeURIComponent(credentialKey)}`, {
    method: "DELETE",
  }, credentialSchema);
}
