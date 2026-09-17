import "server-only";
import { ToolLoopAgent, isStepCount, type LanguageModel } from "ai";
import { createTools } from "./tools";
import { instructions } from "./instructions";
import type { AssistantContext } from "./schemas";

export function createAssistant(model: LanguageModel, cookie: string, context: AssistantContext, role: string, signal: AbortSignal, toolsEnabled = true) {
  return new ToolLoopAgent({
    model, instructions: instructions(context, role, toolsEnabled),
    tools: toolsEnabled ? createTools(cookie, context, signal) : {},
    stopWhen: isStepCount(10), maxOutputTokens: 3000, maxRetries: 0,
  });
}
