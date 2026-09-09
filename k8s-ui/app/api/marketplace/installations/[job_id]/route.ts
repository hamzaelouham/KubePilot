import { NextRequest } from "next/server";
import { backendUnavailable, backendUrl, forwardedCookie, proxyResponse } from "@/lib/backend";

export async function GET(
  request: NextRequest,
  ctx: { params: Promise<{ job_id: string }> },
) {
  const { job_id: jobId } = await ctx.params;
  const target = new URL(`/api/v1/marketplace/installations/${jobId}`, backendUrl());

  try {
    const response = await fetch(target, {
      headers: { cookie: forwardedCookie(request) },
      cache: "no-store",
    });
    return proxyResponse(response);
  } catch {
    return backendUnavailable("The marketplace service is unavailable");
  }
}
