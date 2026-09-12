import "server-only";

import { NextResponse, type NextRequest } from "next/server";
import { backendUnavailable, backendUrl, forwardedCookie, proxyResponse } from "@/lib/backend";

const NAME_PATTERN = /^[a-z0-9](?:[-a-z0-9]{0,61}[a-z0-9])?$/;

export async function proxyHelmRelease(
  request: NextRequest,
  path: string,
  needsNamespace: boolean,
) {
  const query = request.nextUrl.searchParams;
  const cluster = query.get("cluster");
  const namespace = query.get("namespace");
  if (query.getAll("cluster").length !== 1 || !cluster || cluster.trim() !== cluster) {
    return NextResponse.json({ code: "invalid_cluster_scope", message: "Select one explicit registered cluster." }, { status: 422 });
  }
  if (needsNamespace && (query.getAll("namespace").length !== 1 || !namespace || !NAME_PATTERN.test(namespace))) {
    return NextResponse.json({ code: "invalid_namespace_scope", message: "Select one valid release namespace." }, { status: 422 });
  }
  const target = new URL(`/api/v1/cluster/helm/releases${path}`, backendUrl());
  target.searchParams.set("cluster", cluster);
  if (needsNamespace && namespace) target.searchParams.set("namespace", namespace);
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
    return backendUnavailable("The Helm release service is unavailable.");
  }
}
