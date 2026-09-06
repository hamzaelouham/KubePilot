import { NextRequest, NextResponse } from "next/server";
import { backendUnavailable, backendUrl, forwardedCookie } from "@/lib/backend";

export async function GET(request: NextRequest) {
  try {
    const response = await fetch(`${backendUrl()}/api/v1/auth/me`, {
      headers: { cookie: forwardedCookie(request) },
      cache: "no-store",
    });
    const body = await response.text();
    return new NextResponse(body, {
      status: response.status,
      headers: { "content-type": "application/json" },
    });
  } catch {
    return backendUnavailable("The authentication service is unavailable");
  }
}