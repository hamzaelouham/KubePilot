import { NextRequest } from "next/server";
import { backendUnavailable, backendUrl, forwardedCookie, proxyResponse } from "@/lib/backend";

export async function GET(request: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  try {
    const response = await fetch(`${backendUrl()}/api/v1/clusters/${id}/health`, {
      headers: { cookie: forwardedCookie(request) },
      cache: "no-store",
    });
    return proxyResponse(response);
  } catch {
    return backendUnavailable("The cluster management service is unavailable");
  }
}