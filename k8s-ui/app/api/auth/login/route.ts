import { NextRequest, NextResponse } from "next/server";
import { backendUnavailable, backendUrl } from "@/lib/backend";

export async function POST(request: NextRequest) {
  try {
    const response = await fetch(`${backendUrl()}/api/v1/auth/login`, {
      method: "POST",
      headers: { "content-type": request.headers.get("content-type") ?? "application/json" },
      body: await request.text(),
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