import { proxyConversations } from "@/lib/assistant/conversation-proxy";

export async function GET(request: Request) { return proxyConversations(request, "/retention"); }
export async function PUT(request: Request) { return proxyConversations(request, "/retention"); }
