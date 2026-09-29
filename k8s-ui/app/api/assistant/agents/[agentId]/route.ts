import { proxyAgents } from "@/lib/assistant/agents-proxy";
type Context = { params: Promise<{ agentId: string }> };
export async function GET(request: Request, context: Context) { return proxyAgents(request, (await context.params).agentId); }
export async function PUT(request: Request, context: Context) { return proxyAgents(request, (await context.params).agentId); }
export async function DELETE(request: Request, context: Context) { return proxyAgents(request, (await context.params).agentId); }
