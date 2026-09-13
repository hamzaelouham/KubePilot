import "server-only";
import { backendUrl } from "@/lib/backend";
import { SESSION_COOKIE_NAME } from "@/lib/auth-constants";
import { z } from "zod";
import { scrubText } from "./schemas";

export class AssistantError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message); }
}

export function sessionCookie(request: Request) {
  return (request.headers.get("cookie") ?? "").split(";").map(value => value.trim()).find(value => value.startsWith(`${SESSION_COOKIE_NAME}=`)) ?? "";
}

export async function backendRequest(cookie: string, path: string, body?: unknown, signal?: AbortSignal): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(`${backendUrl()}/api/v1${path}`, {
      method: body === undefined ? "GET" : "POST", headers: { cookie, "content-type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body), cache: "no-store",
      signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(45000)]) : AbortSignal.timeout(45000),
    });
  } catch {
    throw new AssistantError(503, "backend_unavailable", "KubePilot backend is unavailable or the request timed out.");
  }
  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const error = z.object({ code: z.string(), message: z.string() }).safeParse(data);
    throw new AssistantError(response.status, error.success ? error.data.code : "api_error", error.success ? scrubText(error.data.message) : `KubePilot API returned HTTP ${response.status}.`);
  }
  return data;
}

export async function authenticate(cookie: string) {
  const user = z.object({ id: z.string(), role: z.enum(["admin", "operator", "viewer"]), must_change_password: z.boolean(), password_expired: z.boolean() }).parse(await backendRequest(cookie, "/auth/me"));
  if (user.must_change_password || user.password_expired) throw new AssistantError(403, "password_change_required", "Change your password before using the assistant.");
  return user;
}

export function sameOrigin(request: Request) {
  const origin = request.headers.get("origin");
  if (!origin || origin !== new URL(request.url).origin) throw new AssistantError(403, "invalid_origin", "This request must originate from KubePilot.");
}

export async function boundedBody(request: Request) {
  const reader = request.body?.getReader();
  if (!reader) throw new AssistantError(400, "invalid_request", "A request body is required.");
  let size = 0;
  const chunks: Uint8Array[] = [];
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > 256000) { await reader.cancel(); throw new AssistantError(413, "conversation_too_large", "Start a new conversation; this conversation is too large."); }
    chunks.push(value);
  }
  try { return JSON.parse(Buffer.concat(chunks).toString("utf8")) as unknown; }
  catch { throw new AssistantError(400, "invalid_request", "Invalid request JSON."); }
}

export function errorResponse(error: unknown) {
  if (error instanceof AssistantError) return Response.json({ code: error.code, message: error.message }, { status: error.status });
  if (error instanceof z.ZodError) return Response.json({ code: "invalid_request", message: "Invalid assistant request or scope." }, { status: 422 });
  return Response.json({ code: "assistant_unavailable", message: "The AI service could not complete this request. Check its model configuration and try again." }, { status: 503 });
}
