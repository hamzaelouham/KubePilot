import { proxyAgentCatalog } from "@/lib/assistant/agent-catalog-proxy";

type Context = { params: Promise<{ skillId: string }> };
export async function GET(request: Request, context: Context) { return proxyAgentCatalog(request, "skills", (await context.params).skillId); }
export async function PUT(request: Request, context: Context) { return proxyAgentCatalog(request, "skills", (await context.params).skillId); }
export async function DELETE(request: Request, context: Context) { return proxyAgentCatalog(request, "skills", (await context.params).skillId); }
