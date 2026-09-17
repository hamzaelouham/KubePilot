import { z } from "zod";
import { modelCapabilitiesSchema } from "@/lib/settings-models";
import { providerIds } from "@/lib/settings-providers";

export const assistantModelSchema = z.object({
  id: z.string().uuid(),
  provider_id: z.enum(providerIds),
  provider_name: z.string().min(1),
  external_model_id: z.string().min(1),
  friendly_name: z.string().min(1),
  capabilities: modelCapabilitiesSchema,
  is_default: z.boolean(),
});

export const assistantModelsResponseSchema = z.object({
  models: z.array(assistantModelSchema),
});

export type AssistantModel = z.infer<typeof assistantModelSchema>;

export async function fetchAssistantModels(signal?: AbortSignal): Promise<AssistantModel[]> {
  let response: Response;
  try {
    response = await fetch("/api/assistant/models", { cache: "no-store", signal });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new Error("The Assistant model service is unavailable.");
  }

  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401) throw new Error("Sign in again to load Assistant models.");
    if (response.status === 403) throw new Error("You do not have permission to use Assistant models.");
    const parsed = z.object({ message: z.string() }).safeParse(body);
    const detail = z.object({ detail: z.union([
      z.string(),
      z.object({ message: z.string() }).transform((value) => value.message),
    ]) }).safeParse(body);
    throw new Error(
      parsed.success
        ? parsed.data.message
        : detail.success
          ? detail.data.detail
          : "The Assistant models could not be loaded.",
    );
  }

  const parsed = assistantModelsResponseSchema.safeParse(body);
  if (!parsed.success) {
    throw new Error("The Assistant model service returned an invalid response.");
  }
  return parsed.data.models;
}
