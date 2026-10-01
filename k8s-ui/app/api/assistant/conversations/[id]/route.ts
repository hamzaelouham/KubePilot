import { proxyConversations } from "@/lib/assistant/conversation-proxy";

type Context = { params: Promise<{ id: string }> };

export async function GET(request: Request, context: Context) { return proxyConversations(request, `/${(await context.params).id}`); }
export async function PATCH(request: Request, context: Context) { return proxyConversations(request, `/${(await context.params).id}`); }
export async function DELETE(request: Request, context: Context) { return proxyConversations(request, `/${(await context.params).id}`); }
