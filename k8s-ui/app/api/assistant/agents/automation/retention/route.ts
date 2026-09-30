import { proxyAgentRetention } from "@/lib/assistant/agents-proxy";

export async function GET(request: Request) {
  return proxyAgentRetention(request);
}

export async function PUT(request: Request) {
  return proxyAgentRetention(request);
}
