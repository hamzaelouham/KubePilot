import { proxyConversations } from "@/lib/assistant/conversation-proxy";

export async function GET(request: Request) { return proxyConversations(request); }
export async function POST(request: Request) { return proxyConversations(request); }
