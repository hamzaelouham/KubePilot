import { NextRequest } from "next/server";
import { backendUnavailable, backendUrl, forwardedSessionCookie, proxyResponse } from "@/lib/backend";

type RouteContext = { params: Promise<{ providerId: string }> };

export async function POST(request: NextRequest, context: RouteContext) {
  try {
    const { providerId } = await context.params;
    const response = await fetch(
      `${backendUrl()}/api/v1/settings/integrations/${encodeURIComponent(providerId)}/test`,
      {
        method: "POST",
        headers: { cookie: forwardedSessionCookie(request) },
        cache: "no-store",
      },
    );
    return proxyResponse(response);
  } catch {
    return backendUnavailable("The integration test service is unavailable");
  }
}
