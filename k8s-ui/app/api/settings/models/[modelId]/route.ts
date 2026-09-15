import { NextRequest } from "next/server";
import { backendUnavailable, backendUrl, forwardedCookie, proxyResponse } from "@/lib/backend";

type ModelRouteContext = { params: Promise<{ modelId: string }> };

async function proxy(request: NextRequest, context: ModelRouteContext) {
  try {
    const { modelId } = await context.params;
    const response = await fetch(`${backendUrl()}/api/v1/settings/models/${encodeURIComponent(modelId)}`, {
      method: request.method,
      headers: { cookie: forwardedCookie(request), "content-type": "application/json" },
      body: request.method === "PUT" ? await request.text() : undefined,
      cache: "no-store",
    });
    return proxyResponse(response);
  } catch {
    return backendUnavailable("The AI model service is unavailable");
  }
}

export async function PUT(request: NextRequest, context: ModelRouteContext) {
  return proxy(request, context);
}

export async function DELETE(request: NextRequest, context: ModelRouteContext) {
  return proxy(request, context);
}
