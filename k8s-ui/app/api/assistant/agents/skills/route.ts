import { proxyAgentCatalog } from "@/lib/assistant/agent-catalog-proxy";

export async function GET(request: Request) { return proxyAgentCatalog(request, "skills"); }
export async function POST(request: Request) { return proxyAgentCatalog(request, "skills"); }
