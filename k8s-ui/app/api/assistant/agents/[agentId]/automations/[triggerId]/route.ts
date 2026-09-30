import { proxyAgentAutomation } from "@/lib/assistant/agents-proxy";

export async function PUT(request: Request, context: { params: Promise<{ agentId: string; triggerId: string }> }) {
  const params = await context.params;
  return proxyAgentAutomation(request, params.agentId, params.triggerId);
}

export async function DELETE(request: Request, context: { params: Promise<{ agentId: string; triggerId: string }> }) {
  const params = await context.params;
  return proxyAgentAutomation(request, params.agentId, params.triggerId);
}
