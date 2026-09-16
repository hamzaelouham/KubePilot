import { NextRequest } from "next/server";
import { SESSION_COOKIE_NAME } from "@/lib/auth-constants";
import { backendUnavailable, backendUrl, proxyResponse } from "@/lib/backend";

function sessionCookie(request: NextRequest) {
  const value = request.cookies.get(SESSION_COOKIE_NAME)?.value;
  return value ? `${SESSION_COOKIE_NAME}=${value}` : "";
}

export async function GET(request: NextRequest) {
  try {
    const sourceUrl = new URL(request.url);
    const response = await fetch(`${backendUrl()}/api/v1/settings/audit-logs?${sourceUrl.searchParams.toString()}`, {
      headers: { cookie: sessionCookie(request) },
      cache: "no-store",
    });
    return proxyResponse(response);
  } catch {
    return backendUnavailable("The audit log service is unavailable");
  }
}
