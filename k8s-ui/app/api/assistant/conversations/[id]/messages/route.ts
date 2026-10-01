import { proxyConversations } from "@/lib/assistant/conversation-proxy";

type Context = { params: Promise<{ id: string }> };

export async function PUT(request: Request, context: Context) { return proxyConversations(request, `/${(await context.params).id}/messages`); }
