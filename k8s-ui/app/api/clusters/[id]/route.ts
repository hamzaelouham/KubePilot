import { NextRequest, NextResponse } from "next/server";
import { backendUnavailable, backendUrl, forwardedCookie } from "@/lib/backend";

export async function PATCH(request: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  try {
    const response = await fetch(`${backendUrl()}/api/v1/clusters/${id}`, {
      method: "PATCH",
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

export async function DELETE(request: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  try {
    const response = await fetch(`${backendUrl()}/api/v1/clusters/${id}`, {
      method: "DELETE",
      headers: { cookie: forwardedCookie(request) },
      cache: "no-store",
    });
    const body = await response.text();
    return new NextResponse(body ? body : null, {
      status: response.status,
      headers: body ? { "content-type": "application/json" } : {},
    });
  } catch {
    return backendUnavailable("The cluster management service is unavailable");
  }
}