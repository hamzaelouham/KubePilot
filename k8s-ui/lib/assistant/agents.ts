import { z } from "zod";

const text = z.string().trim().min(1, "This field is required.").refine(value => !value.includes("\0"), "Remove null characters.");
export const agentWriteSchema = z.object({
  name: text.refine(value => [...value].length <= 128, "Use 128 characters or fewer."),
  description: text,
  instructions: text,
  model_id: z.string().uuid().nullable(),
  enabled: z.boolean(),
  skill_ids: z.array(z.string().uuid()).default([]),
  tool_ids: z.array(z.string().min(1)).default([]),
}).strict();
export const agentModelSchema = z.object({
  id: z.string().uuid(), friendly_name: z.string(), provider_name: z.string(),
  enabled: z.boolean(), availability: z.enum(["unknown", "available", "unavailable"]),
  capabilities: z.object({ streaming: z.boolean(), tools: z.boolean() }),
});
export const agentSchema = agentWriteSchema.extend({
  id: z.string().uuid(), model: agentModelSchema.nullable(),
  created_by_id: z.string().uuid().nullable(), updated_by_id: z.string().uuid().nullable(),
  created_at: z.string(), updated_at: z.string(),
  skills: z.array(z.object({ id: z.string().uuid(), name: z.string(), description: z.string(), instructions: z.string() })).default([]),
  capabilities: z.array(z.object({
    id: z.string(), label: z.string(), description: z.string(), kind: z.string(), required_permission: z.string(),
    configured: z.boolean(), model_supported: z.boolean(), actor_permitted: z.boolean(), status: z.string(),
  })).default([]),
});
export const agentListSchema = z.object({ agents: z.array(agentSchema) });
export const agentModelsSchema = z.object({ models: z.array(agentModelSchema) });
export const agentSkillSchema = z.object({
  id: z.string().uuid(), name: z.string(), description: z.string(), instructions: z.string(),
  created_by_id: z.string().uuid().nullable(), updated_by_id: z.string().uuid().nullable(),
  created_at: z.string(), updated_at: z.string(), assigned_agent_count: z.number().int().nonnegative(),
});
export const agentSkillWriteSchema = z.object({ name: text, description: text, instructions: text }).strict();
export const agentSkillListSchema = z.object({ skills: z.array(agentSkillSchema) });
export const agentToolSchema = z.object({ id: z.string(), label: z.string(), description: z.string(), kind: z.string(), required_permission: z.string() });
export const agentToolListSchema = z.object({ tools: z.array(agentToolSchema) });
export const agentTemplateSchema = z.object({ id: z.string(), name: z.string(), description: z.string(), instructions: z.string(), tool_ids: z.array(z.string()) });
export const agentTemplateListSchema = z.object({ templates: z.array(agentTemplateSchema) });
export type AgentDefinition = z.infer<typeof agentSchema>;
export type AgentDraft = z.infer<typeof agentWriteSchema>;
export type AgentModel = z.infer<typeof agentModelSchema>;
export type AgentSkill = z.infer<typeof agentSkillSchema>;
export type AgentSkillWrite = z.infer<typeof agentSkillWriteSchema>;
export type AgentTool = z.infer<typeof agentToolSchema>;
export type AgentTemplate = z.infer<typeof agentTemplateSchema>;
export const emptyAgent: AgentDraft = { name: "", description: "", instructions: "", model_id: null, enabled: false, skill_ids: [], tool_ids: [] };
export function draftOf(agent: AgentDraft): AgentDraft {
  return { name: agent.name, description: agent.description, instructions: agent.instructions, model_id: agent.model_id, enabled: agent.enabled, skill_ids: agent.skill_ids ?? [], tool_ids: agent.tool_ids ?? [] };
}
export function applyTemplate(draft: AgentDraft, template: AgentTemplate): AgentDraft {
  return { ...draft, name: template.name, description: template.description, instructions: template.instructions, skill_ids: [], tool_ids: [...template.tool_ids] };
}
export type AgentErrors = Partial<Record<keyof AgentDraft, string>>;
export function validateAgent(draft: AgentDraft, original: AgentDefinition | null, models: AgentModel[], step = 2): AgentErrors {
  const errors: AgentErrors = {};
  const parsed = agentWriteSchema.safeParse(draft);
  if (!parsed.success) for (const issue of parsed.error.issues) errors[issue.path[0] as keyof AgentDraft] = issue.message;
  if (step === 0) { delete errors.model_id; delete errors.enabled; return errors; }
  if (!draft.model_id && (!original || original.model_id || draft.enabled)) errors.model_id = "Select a model.";
  const model = models.find(model => model.id === draft.model_id);
  if (draft.model_id && !model && draft.model_id !== original?.model_id) errors.model_id = "Select an existing model.";
  if (draft.enabled && (!original?.enabled || original.model_id !== draft.model_id) && (!model?.enabled || model.availability !== "available")) errors.model_id = "Choose an enabled, available model before enabling this agent.";
  return errors;
}
export function filterAgents(agents: AgentDefinition[], search: string) {
  const query = search.trim().toLocaleLowerCase();
  return agents.filter(agent => `${agent.name} ${agent.description}`.toLocaleLowerCase().includes(query));
}
export class AgentRequestError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message); }
}
export async function agentRequest<T, B = AgentDraft>(path: string, schema: z.ZodType<T>, method = "GET", body?: B, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, { method, cache: "no-store", headers: { "content-type": "application/json" }, body: body ? JSON.stringify(body) : undefined, signal });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new AgentRequestError(0, "network_error", method === "GET" ? "Cannot reach KubePilot. Try refreshing." : "The result could not be confirmed. Refresh stored state before trying again.");
  }
  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const failure = z.object({ code: z.string(), message: z.string() }).safeParse(data);
    throw new AgentRequestError(response.status, failure.success ? failure.data.code : "unexpected_error", failure.success ? failure.data.message : "An unexpected server error occurred. Refresh before trying again.");
  }
  const parsed = schema.safeParse(data);
  if (!parsed.success) throw new AgentRequestError(502, "invalid_response", "KubePilot returned an unexpected response. Refresh before trying again.");
  return parsed.data;
}
