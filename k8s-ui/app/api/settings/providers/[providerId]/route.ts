import { NextRequest } from "next/server";
import { backendUnavailable, backendUrl, forwardedCookie, proxyResponse } from "@/lib/backend";

type ProviderRouteContext = { params: Promise<{ providerId: string }> };

async function proxy(request: NextRequest, context: ProviderRouteContext) {
  try {
    const { providerId } = await context.params;
    const headers: HeadersInit = { cookie: forwardedCookie(request) };
    const body = await request.text();
    headers["content-type"] = "application/json";
    const response = await fetch(
      `${backendUrl()}/api/v1/settings/providers/${encodeURIComponent(providerId)}${request.method === "POST" ? "/test" : ""}`,
      { method: request.method, headers, body: body || undefined, cache: "no-store" },
    );
    return proxyResponse(response);
  } catch {
    return backendUnavailable("The AI provider service is unavailable");
  }
}

export async function PUT(request: NextRequest, context: ProviderRouteContext) {
  return proxy(request, context);
}

export async function POST(request: NextRequest, context: ProviderRouteContext) {
  return proxy(request, context);
}
