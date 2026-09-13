import "server-only";

import { NextResponse, type NextRequest } from "next/server";
import { backendUnavailable, backendUrl, forwardedCookie, proxyResponse } from "@/lib/backend";

export async function proxyHelmRepository(request: NextRequest, path = "") {
  const target = new URL(`/api/v1/helm/repositories${path}`, backendUrl());
  let body: string | undefined;
  if (request.method !== "GET") body = await request.text();
  try {
    const response = await fetch(target, {
      method: request.method,
      headers: { cookie: forwardedCookie(request), ...(body === undefined ? {} : { "content-type": "application/json" }) },
      body,
      cache: "no-store",
    });
    return proxyResponse(response);
  } catch (error) {
    if (!(error instanceof TypeError)) throw error;
    return backendUnavailable("The Helm repository service is unavailable.");
  }
}
