import "server-only";
import { z } from "zod";
import { backendUrl } from "@/lib/backend";
import { AssistantError, boundedBody, sameOrigin, sessionCookie } from "./backend";
import { agentSkillWriteSchema } from "./agents";

const resources = z.enum(["skills", "templates", "tools"]);

export async function proxyAgentCatalog(request: Request, resource: "skills" | "templates" | "tools", identity?: string) {
  try {
    resources.parse(resource);
    if (identity !== undefined) z.string().uuid().parse(identity);
    if (request.method !== "GET") sameOrigin(request);
    const cookie = sessionCookie(request);
    if (!cookie) throw new AssistantError(401, "authentication_required", "Sign in to access AI Agent configuration.");
    const body = ["POST", "PUT"].includes(request.method) ? agentSkillWriteSchema.parse(await boundedBody(request)) : undefined;
    const response = await fetch(`${backendUrl()}/api/v1/assistant/agents/${resource}${identity ? `/${identity}` : ""}`, {
      method: request.method,
      headers: { cookie, "content-type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
      cache: "no-store",
      signal: AbortSignal.timeout(45000),
    });
    if (response.status >= 500) return Response.json({ code: "service_unavailable", message: "Agent configuration service unavailable. Refresh stored state before retrying a change." }, { status: 503 });
    const data: unknown = await response.json();
    return Response.json(data, { status: response.status, headers: { "cache-control": "no-store" } });
  } catch (error) {
    if (error instanceof AssistantError) return Response.json({ code: error.code, message: error.status === 413 ? "Agent configuration is too large." : error.message }, { status: error.status });
    if (error instanceof z.ZodError) return Response.json({ code: "validation_error", message: "Check the skill fields and identifier." }, { status: 422 });
    return Response.json({ code: "service_unavailable", message: "Agent configuration service unavailable. Refresh stored state before retrying a change." }, { status: 503 });
  }
}
