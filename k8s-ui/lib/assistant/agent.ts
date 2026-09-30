import "server-only";
import { ToolLoopAgent, isStepCount, type LanguageModel } from "ai";
import { createTools } from "./tools";
import { instructions, type AssistantInstructionConfig } from "./instructions";
import type { AssistantContext } from "./schemas";

export type AssistantAgentConfig = AssistantInstructionConfig & {
  effectiveToolIds: ReadonlySet<string>;
};

export function createAssistant(model: LanguageModel, cookie: string, context: AssistantContext, role: string, signal: AbortSignal, toolsEnabled = true, agent?: AssistantAgentConfig) {
  const tools = toolsEnabled ? createTools(cookie, context, signal, agent?.effectiveToolIds) : {};
  const hasOperationalTools = Object.keys(tools).length > 0;
  return new ToolLoopAgent({
    model, instructions: instructions(context, role, hasOperationalTools, agent),
    tools,
    stopWhen: isStepCount(10), maxOutputTokens: 3000, maxRetries: 0,
  });
}
