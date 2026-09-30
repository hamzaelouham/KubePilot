import "server-only";
import { z } from "zod";
import { backendUrl } from "@/lib/backend";
import { AssistantError, boundedBody, sameOrigin, sessionCookie } from "./backend";
import { agentWriteSchema, notificationDestinationWriteSchema } from "./agents";

export async function proxyAgents(request: Request, identity?: string) {
  try {
    if (identity !== undefined) z.string().uuid().parse(identity);
    if (request.method !== "GET") sameOrigin(request);
    const cookie = sessionCookie(request);
    if (!cookie) throw new AssistantError(401, "authentication_required", "Sign in to access AI Agents.");
    const body = ["POST", "PUT"].includes(request.method) ? agentWriteSchema.parse(await boundedBody(request)) : undefined;
    const response = await fetch(`${backendUrl()}/api/v1/assistant/agents${identity ? `/${identity}` : ""}`, {
      method: request.method, headers: { cookie, "content-type": "application/json" },
      body: body ? JSON.stringify(body) : undefined, cache: "no-store", signal: AbortSignal.timeout(45000),
    });
    if (response.status >= 500) return Response.json({ code: "service_unavailable", message: "Agent service unavailable. Refresh stored state before retrying a change." }, { status: 503 });
    const data: unknown = await response.json();
    return Response.json(data, { status: response.status, headers: { "cache-control": "no-store" } });
  } catch (error) {
    if (error instanceof AssistantError) return Response.json({ code: error.code, message: error.status === 413 ? "Agent configuration is too large." : error.message }, { status: error.status });
    if (error instanceof z.ZodError) return Response.json({ code: "validation_error", message: "Check the agent fields and selected model." }, { status: 422 });
    return Response.json({ code: "service_unavailable", message: "Agent service unavailable. Refresh stored state before retrying a change." }, { status: 503 });
  }
}

export async function proxyAgentNotifications(
  request: Request,
  agentId: string,
  destinationId?: string,
  action?: "test",
) {
  try {
    z.string().uuid().parse(agentId);
    if (destinationId !== undefined) z.string().uuid().parse(destinationId);
    if (request.method !== "GET") sameOrigin(request);
    const cookie = sessionCookie(request);
    if (!cookie) throw new AssistantError(401, "authentication_required", "Sign in to access agent notifications.");
    const body = ["POST", "PUT"].includes(request.method) && action !== "test"
      ? notificationDestinationWriteSchema.parse(await boundedBody(request))
      : undefined;
    const suffix = destinationId
      ? `/${destinationId}${action ? `/${action}` : ""}`
      : "";
    const response = await fetch(`${backendUrl()}/api/v1/assistant/agents/${agentId}/notifications${suffix}`, {
      method: request.method,
      headers: { cookie, "content-type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
      cache: "no-store",
      signal: AbortSignal.timeout(45000),
    });
    if (response.status >= 500) {
      return Response.json(
        { code: "service_unavailable", message: "Agent notification service unavailable. Refresh before retrying." },
        { status: 503 },
      );
    }
    const data: unknown = await response.json();
    return Response.json(data, { status: response.status, headers: { "cache-control": "no-store" } });
  } catch (error) {
    if (error instanceof AssistantError) {
      return Response.json(
        { code: error.code, message: error.status === 413 ? "Notification configuration is too large." : error.message },
        { status: error.status },
      );
    }
    if (error instanceof z.ZodError) {
      return Response.json({ code: "validation_error", message: "Check the notification destination fields." }, { status: 422 });
    }
    return Response.json(
      { code: "service_unavailable", message: "Agent notification service unavailable. Refresh before retrying." },
      { status: 503 },
    );
  }
}
