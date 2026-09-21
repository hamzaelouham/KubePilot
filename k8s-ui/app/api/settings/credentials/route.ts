import { NextRequest } from "next/server";
import { backendUnavailable, backendUrl, forwardedSessionCookie, proxyResponse } from "@/lib/backend";

export async function GET(request: NextRequest) {
  try {
    const response = await fetch(`${backendUrl()}/api/v1/settings/credentials`, {
      headers: { cookie: forwardedSessionCookie(request) },
      cache: "no-store",
    });
    return proxyResponse(response);
  } catch {
    return backendUnavailable("The credential service is unavailable");
  }
}
