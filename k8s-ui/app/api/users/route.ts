import { NextRequest, NextResponse } from "next/server";
import { backendUnavailable, backendUrl, forwardedCookie } from "@/lib/backend";

export async function GET(request: NextRequest) {
  try {
    const response = await fetch(`${backendUrl()}/api/v1/users`, {
      headers: { cookie: forwardedCookie(request) },
      cache: "no-store",
    });
    const body = await response.text();
    return new NextResponse(body, {
      status: response.status,
      headers: { "content-type": "application/json" },
    });
  } catch {
    return backendUnavailable("The user management service is unavailable");
  }
}

export async function POST(request: NextRequest) {
  try {
    const response = await fetch(`${backendUrl()}/api/v1/users`, {
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
    return backendUnavailable("The user management service is unavailable");
  }
}