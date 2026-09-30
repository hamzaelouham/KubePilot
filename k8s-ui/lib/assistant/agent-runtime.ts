import "server-only";

import type { LanguageModel } from "ai";
import { z } from "zod";
import { agentSchema } from "./agents";
import { AssistantError, backendRequest } from "./backend";
import { resolveAssistantRuntime, type ResolvedAssistantModel } from "./model-resolver";
import type { AssistantAgentConfig } from "./agent";

export type ResolvedAgentRuntime = {
  model: LanguageModel;
  metadata: ResolvedAssistantModel["metadata"];
  config: AssistantAgentConfig;
};

export async function resolveAgentRuntime(cookie: string, identity: string): Promise<ResolvedAgentRuntime> {
  const agentId = z.string().uuid().parse(identity);
  const parsed = agentSchema.safeParse(await backendRequest(cookie, `/assistant/agents/${encodeURIComponent(agentId)}`));
  if (!parsed.success) {
    throw new AssistantError(503, "invalid_agent_configuration", "The selected agent returned an invalid configuration.");
  }

  const agent = parsed.data;
  if (!agent.enabled) {
    throw new AssistantError(409, "agent_disabled", "This agent is disabled. Select an enabled agent or ask an administrator to enable it.");
  }
  if (!agent.model_id || !agent.model) {
    throw new AssistantError(409, "agent_model_unavailable", "This agent has no configured model. Ask an administrator to configure one.");
  }

  let resolved: ResolvedAssistantModel;
  try {
    resolved = await resolveAssistantRuntime(cookie, agent.model_id);
  } catch (error) {
    if (error instanceof AssistantError && ["ai_model_unavailable", "ai_not_configured", "invalid_model_configuration"].includes(error.code)) {
      throw new AssistantError(409, "agent_model_unavailable", "This agent's model is not currently available. Ask an administrator to check its provider and availability.");
    }
    throw error;
  }

  const effectiveToolIds = new Set(
    agent.capabilities
      .filter(capability => capability.status === "available" && capability.configured && capability.actor_permitted && capability.model_supported && resolved.metadata.capabilities.tools)
      .map(capability => capability.id),
  );

  return {
    model: resolved.model,
    metadata: resolved.metadata,
    config: {
      name: agent.name,
      description: agent.description,
      instructions: agent.instructions,
      skillInstructions: agent.skills.map(skill => skill.instructions),
      effectiveToolIds,
    },
  };
}
