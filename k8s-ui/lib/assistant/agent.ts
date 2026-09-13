import "server-only";
import { ToolLoopAgent, isStepCount, type LanguageModel } from "ai";
import { createTools } from "./tools";
import { instructions } from "./instructions";
import type { AssistantContext } from "./schemas";

export function createAssistant(model: LanguageModel, cookie: string, context: AssistantContext, role: string, signal: AbortSignal) {
  return new ToolLoopAgent({
    model, instructions: instructions(context, role),
    tools: createTools(cookie, context, signal),
    stopWhen: isStepCount(10), maxOutputTokens: 3000, maxRetries: 0,
  });
}
