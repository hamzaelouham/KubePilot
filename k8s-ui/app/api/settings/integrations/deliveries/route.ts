import { NextRequest } from "next/server";
import { backendUnavailable, backendUrl, forwardedSessionCookie, proxyResponse } from "@/lib/backend";

export async function GET(request: NextRequest) {
  try {
    const sourceUrl = new URL(request.url);
    const response = await fetch(`${backendUrl()}/api/v1/settings/integrations/deliveries?${sourceUrl.searchParams.toString()}`, {
      headers: { cookie: forwardedSessionCookie(request) },
      cache: "no-store",
    });
    return proxyResponse(response);
  } catch {
    return backendUnavailable("The integration delivery service is unavailable");
  }
}
