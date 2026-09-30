import { proxyAgentNotifications } from "@/lib/assistant/agents-proxy";

type Context = { params: Promise<{ agentId: string; destinationId: string }> };

export async function PUT(request: Request, context: Context) {
  const params = await context.params;
  return proxyAgentNotifications(request, params.agentId, params.destinationId);
}

export async function DELETE(request: Request, context: Context) {
  const params = await context.params;
  return proxyAgentNotifications(request, params.agentId, params.destinationId);
}
