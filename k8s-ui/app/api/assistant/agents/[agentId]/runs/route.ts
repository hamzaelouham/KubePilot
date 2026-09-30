import { proxyAgentRuns } from "@/lib/assistant/agents-proxy";

export async function GET(request: Request, context: { params: Promise<{ agentId: string }> }) {
  const { agentId } = await context.params;
  return proxyAgentRuns(request, agentId);
}
