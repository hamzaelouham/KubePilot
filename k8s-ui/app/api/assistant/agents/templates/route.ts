import { proxyAgentCatalog } from "@/lib/assistant/agent-catalog-proxy";

export async function GET(request: Request) { return proxyAgentCatalog(request, "templates"); }
