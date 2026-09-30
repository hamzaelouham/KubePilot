import { proxyAgentAutomation } from "@/lib/assistant/agents-proxy";

export async function GET(request: Request, context: { params: Promise<{ agentId: string }> }) {
  return proxyAgentAutomation(request, (await context.params).agentId);
}

export async function POST(request: Request, context: { params: Promise<{ agentId: string }> }) {
  return proxyAgentAutomation(request, (await context.params).agentId);
}
