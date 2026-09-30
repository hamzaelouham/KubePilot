import { proxyAgentNotifications } from "@/lib/assistant/agents-proxy";

type Context = { params: Promise<{ agentId: string }> };

export async function GET(request: Request, context: Context) {
  return proxyAgentNotifications(request, (await context.params).agentId);
}

export async function POST(request: Request, context: Context) {
  return proxyAgentNotifications(request, (await context.params).agentId);
}
