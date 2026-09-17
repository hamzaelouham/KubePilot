import "server-only";

import { createOpenAICompatible } from "@ai-sdk/openai-compatible";
import type { LanguageModel } from "ai";
import { backendUrl } from "@/lib/backend";
import { AssistantError, backendRequest } from "./backend";
import { assistantModelsResponseSchema, type AssistantModel } from "./models";

export type ResolvedAssistantModel = {
  model: LanguageModel;
  metadata: AssistantModel;
};

export function resolveAssistantModel(
  cookie: string,
  modelId = "default",
  fetchImplementation: typeof fetch = fetch,
): LanguageModel {
  const provider = createOpenAICompatible({
    name: "kubepilot",
    baseURL: `${backendUrl()}/api/v1/assistant/inference`,
    headers: { cookie },
    fetch: fetchImplementation,
    includeUsage: true,
  });
  return provider.chatModel(modelId);
}

export async function resolveAssistantRuntime(
  cookie: string,
  modelId?: string,
  fetchImplementation: typeof fetch = fetch,
): Promise<ResolvedAssistantModel> {
  const response = assistantModelsResponseSchema.safeParse(
    await backendRequest(cookie, "/assistant/models"),
  );
  if (!response.success) {
    throw new AssistantError(503, "invalid_model_configuration", "The Assistant model service returned an invalid response.");
  }
  const metadata = modelId
    ? response.data.models.find((candidate) => candidate.id === modelId)
    : response.data.models.find((candidate) => candidate.is_default);
  if (!metadata) {
    throw new AssistantError(
      modelId ? 422 : 503,
      modelId ? "ai_model_unavailable" : "ai_not_configured",
      modelId
        ? "The selected AI model is not currently available."
        : "Configure an eligible default AI model in Settings.",
    );
  }
  return {
    model: resolveAssistantModel(cookie, metadata.id, fetchImplementation),
    metadata,
  };
}
