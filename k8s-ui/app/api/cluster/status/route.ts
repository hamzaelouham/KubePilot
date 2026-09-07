import { NextRequest, NextResponse } from "next/server";
import { backendUrl, backendUnavailable, forwardedCookie } from "@/lib/backend";

export async function GET(request: NextRequest) {
  try {
    const target = new URL(`${backendUrl()}/api/v1/cluster/status`);
    const cluster = request.nextUrl.searchParams.get("cluster");
    if (cluster) target.searchParams.set("cluster", cluster);
    const response = await fetch(target, {
      headers: { cookie: forwardedCookie(request) },
      cache: "no-store",
    });
    const body = await response.text();
    return new NextResponse(body, {
      status: response.status,
      headers: { "content-type": "application/json" },
    });
  } catch {
    return backendUnavailable("The backend service is unavailable");
  }
}