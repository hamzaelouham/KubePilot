import { NextRequest } from "next/server";
import { backendUnavailable, backendUrl, forwardedSessionCookie, proxyResponse } from "@/lib/backend";

type RouteContext = { params: Promise<{ deliveryId: string }> };

export async function POST(request: NextRequest, context: RouteContext) {
  try {
    const { deliveryId } = await context.params;
    const response = await fetch(`${backendUrl()}/api/v1/settings/integrations/deliveries/${encodeURIComponent(deliveryId)}/retry`, {
      method: "POST",
      headers: { cookie: forwardedSessionCookie(request) },
      cache: "no-store",
    });
    return proxyResponse(response);
  } catch {
    return backendUnavailable("The integration delivery service is unavailable");
  }
}
