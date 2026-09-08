import { NextRequest } from "next/server";
import { backendUnavailable, backendUrl, forwardedCookie, proxyResponse } from "@/lib/backend";

export async function GET(request: NextRequest) {
  const target = new URL("/api/v1/marketplace/packages", backendUrl());
  for (const key of ["limit", "offset", "ts_query_web", "sort"]) {
    const value = request.nextUrl.searchParams.get(key);
    if (value !== null) target.searchParams.set(key, value);
  }

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