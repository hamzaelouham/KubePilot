import "server-only";

import { NextResponse, type NextRequest } from "next/server";
import { backendUnavailable, backendUrl, forwardedCookie, proxyResponse } from "@/lib/backend";
import { RESOURCE_TYPES } from "@/lib/resource-management";

export async function proxyManagement(request: NextRequest, resourceType: string, name?: string) {
  const invalid = (code: string, message: string) => NextResponse.json({ code, message }, { status: 422 });
  if (!RESOURCE_TYPES.some((type) => type.value === resourceType)) return invalid("invalid_resource_type", "Unsupported resource type.");
  const query = request.nextUrl.searchParams;
  const cluster = query.get("cluster");
  const namespace = query.get("namespace");
  if (query.getAll("cluster").length !== 1 || !cluster?.trim() || cluster !== cluster.trim()) {
    return invalid("invalid_resource_identity", "Select one registered cluster.");
  }
  if (query.getAll("namespace").length > 1 || namespace !== null && !/^[a-z0-9](?:[-a-z0-9]{0,61}[a-z0-9])?$/.test(namespace)) {
    return invalid("invalid_namespace_scope", "Select one valid namespace.");
  }
  if (resourceType === "namespaces" && namespace !== null || resourceType !== "namespaces" && request.method !== "GET" && !namespace) {
    return invalid("invalid_namespace_scope", "Use cluster scope for Namespaces and an explicit namespace for other mutations.");
  }
  if (name !== undefined && (name.length > 253 || !/^[a-z0-9](?:[-a-z0-9.]*[a-z0-9])?$/.test(name))) {
    return invalid("invalid_resource_identity", "Invalid resource name.");
  }
  let body: string | undefined;
  if (request.method !== "GET") {
    try {
      body = JSON.stringify(await request.json());
    } catch (error) {
      if (!(error instanceof SyntaxError)) throw error;
      return invalid("validation_error", "Request validation failed");
    }
  }
  const url = new URL(`/api/v1/cluster/manage-resources/${resourceType}${name === undefined ? "" : `/${encodeURIComponent(name)}`}`, backendUrl());
  url.searchParams.set("cluster", cluster);
  if (namespace !== null) url.searchParams.set("namespace", namespace);
  try {
    const response = await fetch(url, {
      method: request.method,
      headers: { cookie: forwardedCookie(request), ...(body === undefined ? {} : { "content-type": "application/json" }) },
      body,
      cache: "no-store",
    });
    return await proxyResponse(response);
  } catch (error) {
    if (!(error instanceof TypeError)) throw error;
    return backendUnavailable("Resource management backend is unavailable.");
  }
}
