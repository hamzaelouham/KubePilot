import { NextRequest, NextResponse } from "next/server";
import { backendUnavailable, backendUrl, forwardedCookie, proxyResponse } from "@/lib/backend";

export async function GET(request: NextRequest) {
  try {
    const response = await fetch(`${backendUrl()}/api/v1/clusters`, {
      headers: { cookie: forwardedCookie(request) },
      cache: "no-store",
    });
    return proxyResponse(response);
  } catch {
    return backendUnavailable("The cluster management service is unavailable");
  }
}

export async function POST(request: NextRequest) {
  try {
    const response = await fetch(`${backendUrl()}/api/v1/clusters`, {
      method: "POST",
      headers: {
        "content-type": request.headers.get("content-type") ?? "application/json",
        cookie: forwardedCookie(request),
      },
      body: await request.text(),
      cache: "no-store",
    });
    const body = await response.text();
    return new NextResponse(body, {
      status: response.status,
      headers: { "content-type": "application/json" },
    });
  } catch {
    return backendUnavailable("The cluster management service is unavailable");
  }
}