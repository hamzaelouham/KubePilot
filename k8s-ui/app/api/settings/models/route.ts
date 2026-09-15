import { NextRequest } from "next/server";
import { backendUnavailable, backendUrl, forwardedCookie, proxyResponse } from "@/lib/backend";

async function proxy(request: NextRequest) {
  try {
    const response = await fetch(`${backendUrl()}/api/v1/settings/models`, {
      method: request.method,
      headers: { cookie: forwardedCookie(request), "content-type": "application/json" },
      body: request.method === "POST" ? await request.text() : undefined,
      cache: "no-store",
    });
    return proxyResponse(response);
  } catch {
    return backendUnavailable("The AI model service is unavailable");
  }
}

export async function GET(request: NextRequest) {
  return proxy(request);
}

export async function POST(request: NextRequest) {
  return proxy(request);
}
