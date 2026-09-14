import { NextRequest } from "next/server";
import { backendUnavailable, backendUrl, forwardedCookie, proxyResponse } from "@/lib/backend";

async function proxy(request: NextRequest) {
  try {
    const headers: HeadersInit = {
      cookie: forwardedCookie(request),
    };
    let body: string | undefined;
    if (request.method === "PATCH") {
      body = await request.text();
      headers["content-type"] = "application/json";
    }
    const response = await fetch(`${backendUrl()}/api/v1/settings/preferences`, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
    });
    return proxyResponse(response);
  } catch {
    return backendUnavailable("The preferences service is unavailable");
  }
}

export async function GET(request: NextRequest) {
  return proxy(request);
}

export async function PATCH(request: NextRequest) {
  return proxy(request);
}
