import { proxyConversations } from "@/lib/assistant/conversation-proxy";

export async function POST(request: Request) { return proxyConversations(request, "/purge"); }
