import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function backendUrl() {
  return process.env.KUBEPILOT_BACKEND_URL ?? "http://127.0.0.1:8000";
}

export function forwardedCookie(request: NextRequest) {
  return request.headers.get("cookie") ?? "";
}

export async function proxyResponse(response: Response) {
  const body = await response.text();
  return new NextResponse(body, {
    status: response.status,
    headers: { "content-type": "application/json" },
  });
}

export function backendUnavailable(message: string) {
  return NextResponse.json({ code: "backend_unavailable", message }, { status: 503 });
}