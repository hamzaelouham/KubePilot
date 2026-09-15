import { NextRequest } from "next/server";
import { backendUnavailable, backendUrl, forwardedCookie, proxyResponse } from "@/lib/backend";

type ModelRouteContext = { params: Promise<{ modelId: string }> };

export async function POST(request: NextRequest, context: ModelRouteContext) {
  try {
    const { modelId } = await context.params;
    const response = await fetch(`${backendUrl()}/api/v1/settings/models/${encodeURIComponent(modelId)}/default`, {
      method: "POST",
      headers: { cookie: forwardedCookie(request), "content-type": "application/json" },
      body: await request.text() || "{}",
      cache: "no-store",
    });
    return proxyResponse(response);
  } catch {
    return backendUnavailable("The AI model service is unavailable");
  }
}
