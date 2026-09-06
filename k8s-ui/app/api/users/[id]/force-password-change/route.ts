import { NextRequest, NextResponse } from "next/server";
import { backendUnavailable, backendUrl, forwardedCookie } from "@/lib/backend";

export async function POST(request: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  try {
    const response = await fetch(`${backendUrl()}/api/v1/users/${id}/force-password-change`, {
      method: "POST",
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