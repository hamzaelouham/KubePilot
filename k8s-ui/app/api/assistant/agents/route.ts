import { proxyAgents } from "@/lib/assistant/agents-proxy";
export async function GET(request: Request) { return proxyAgents(request); }
export async function POST(request: Request) { return proxyAgents(request); }
