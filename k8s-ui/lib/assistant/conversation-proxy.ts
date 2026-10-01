import "server-only";
import { z } from "zod";
import { backendUrl } from "@/lib/backend";
import { AssistantError, boundedBody, sameOrigin, sessionCookie } from "./backend";
import { conversationCreateSchema, conversationRenameSchema, conversationSaveSchema, retentionSchema } from "./conversations";

function responseFromBackend(response: Response) {
  if (response.status === 204) return new Response(null, { status: 204, headers: { "cache-control": "no-store" } });
  return response.json().then(data => Response.json(data, { status: response.status, headers: { "cache-control": "no-store" } }));
}

export async function proxyConversations(request: Request, suffix = "") {
  try {
    if (request.method !== "GET") sameOrigin(request);
    const cookie = sessionCookie(request);
    if (!cookie) throw new AssistantError(401, "authentication_required", "Sign in to access Assistant conversations.");
    if (suffix && suffix !== "/retention" && suffix !== "/purge") z.string().uuid().parse(suffix.replace(/^\//, "").split("/")[0]);
    let body: unknown;
    if ((request.method === "POST" && suffix === "") || ["PUT", "PATCH"].includes(request.method)) {
      const raw = await boundedBody(request);
      body = suffix === ""
        ? conversationCreateSchema.parse(raw)
        : suffix === "/retention"
          ? retentionSchema.parse(raw)
          : suffix.endsWith("/messages")
            ? conversationSaveSchema.parse(raw)
            : conversationRenameSchema.parse(raw);
    }
    const url = `${backendUrl()}/api/v1/assistant/conversations${suffix}${request.method === "GET" ? new URL(request.url).search : ""}`;
    const response = await fetch(url, {
      method: request.method,
      headers: { cookie, "content-type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
      signal: AbortSignal.timeout(45000),
    });
    if (response.status >= 500) return Response.json({ code: "service_unavailable", message: "Conversation service unavailable. Refresh before trying again." }, { status: 503 });
    return responseFromBackend(response);
  } catch (error) {
    if (error instanceof AssistantError) return Response.json({ code: error.code, message: error.message }, { status: error.status });
    if (error instanceof z.ZodError) return Response.json({ code: "validation_error", message: "The conversation request is invalid." }, { status: 422 });
    return Response.json({ code: "service_unavailable", message: "Conversation service unavailable. Refresh before trying again." }, { status: 503 });
  }
}
