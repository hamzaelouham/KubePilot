import { z } from "zod";

export const assistantModeSchema = z.enum(["direct", "agent"]);
export type AssistantMode = z.infer<typeof assistantModeSchema>;

const idSchema = z.string().uuid();

export function parseAssistantSelection(search: URLSearchParams): {
  mode: AssistantMode;
  modelId?: string;
  agentId?: string;
} {
  const agentId = idSchema.safeParse(search.get("agent")).data;
  const requestedMode = assistantModeSchema.safeParse(search.get("mode")).data;
  const mode: AssistantMode = agentId && requestedMode !== "direct" ? "agent" : requestedMode ?? "direct";
  const modelId = mode === "direct" ? idSchema.safeParse(search.get("model")).data : undefined;
  return mode === "agent" ? { mode, agentId } : { mode, modelId };
}

export function assistantIdentity(mode: AssistantMode, modelId?: string, agentId?: string) {
  return mode === "agent" ? (agentId ? { agentId } : {}) : (modelId ? { modelId } : {});
}

export function assistantSelectionUrl(mode: AssistantMode, modelId?: string, agentId?: string, current = "") {
  const search = new URLSearchParams(current);
  search.delete("mode");
  search.delete("model");
  search.delete("agent");
  search.set("mode", mode);
  if (mode === "agent" && agentId) search.set("agent", agentId);
  if (mode === "direct" && modelId) search.set("model", modelId);
  const query = search.toString();
  return query ? `?${query}` : "";
}
