import "server-only";

import { createOpenAICompatible } from "@ai-sdk/openai-compatible";
import type { LanguageModel } from "ai";
import { backendUrl } from "@/lib/backend";

export function resolveAssistantModel(cookie: string, fetchImplementation: typeof fetch = fetch): LanguageModel {
  const provider = createOpenAICompatible({
    name: "kubepilot",
    baseURL: `${backendUrl()}/api/v1/assistant/inference`,
    headers: { cookie },
    fetch: fetchImplementation,
    includeUsage: true,
  });
  return provider.chatModel("default");
}
