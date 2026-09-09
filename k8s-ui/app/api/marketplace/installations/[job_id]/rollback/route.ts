import { NextRequest } from "next/server";
import { backendUnavailable, backendUrl, forwardedCookie, proxyResponse } from "@/lib/backend";

export async function POST(
  request: NextRequest,
  ctx: { params: Promise<{ job_id: string }> },
) {
  const { job_id: jobId } = await ctx.params;
  const target = new URL(
    `/api/v1/marketplace/installations/${jobId}/rollback`,
    backendUrl(),
  );

  try {
    const response = await fetch(target, {
      method: "POST",
      headers: {
        "content-type": request.headers.get("content-type") ?? "application/json",
        cookie: forwardedCookie(request),
      },
      body: await request.text(),
      cache: "no-store",
    });
    return proxyResponse(response);
  } catch {
    return backendUnavailable("The marketplace service is unavailable");
  }
}