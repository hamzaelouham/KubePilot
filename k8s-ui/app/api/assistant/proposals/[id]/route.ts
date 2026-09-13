import { z } from "zod";
import { authenticate, backendRequest, boundedBody, errorResponse, sameOrigin, sessionCookie } from "@/lib/assistant/backend";

export async function GET(request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const cookie = sessionCookie(request);
    await authenticate(cookie);
    const id = z.string().uuid().parse((await params).id);
    return Response.json(await backendRequest(cookie, `/assistant/proposals/${id}`));
  } catch (error) { return errorResponse(error); }
}

export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    sameOrigin(request);
    const cookie = sessionCookie(request);
    await authenticate(cookie);
    const id = z.string().uuid().parse((await params).id);
    const body = z.object({ approved: z.boolean(), confirm_name: z.string().max(253), cluster: z.string().min(1).max(253) }).strict().parse(await boundedBody(request));
    return Response.json(await backendRequest(cookie, `/assistant/proposals/${id}/decision`, body));
  } catch (error) { return errorResponse(error); }
}
