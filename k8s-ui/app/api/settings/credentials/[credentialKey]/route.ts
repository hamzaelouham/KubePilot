import { NextRequest } from "next/server";
import { backendUnavailable, backendUrl, forwardedSessionCookie, proxyResponse } from "@/lib/backend";

type CredentialRouteContext = { params: Promise<{ credentialKey: string }> };

async function proxy(request: NextRequest, context: CredentialRouteContext) {
  try {
    const { credentialKey } = await context.params;
    const body = request.method === "PUT" ? await request.text() : undefined;
    const response = await fetch(
      `${backendUrl()}/api/v1/settings/credentials/${encodeURIComponent(credentialKey)}`,
      {
        method: request.method,
        headers: {
          cookie: forwardedSessionCookie(request),
          ...(body === undefined ? {} : { "content-type": "application/json" }),
        },
        body,
        cache: "no-store",
      },
    );
    return proxyResponse(response);
  } catch {
    return backendUnavailable("The credential service is unavailable");
  }
}

export async function PUT(request: NextRequest, context: CredentialRouteContext) {
  return proxy(request, context);
}

export async function DELETE(request: NextRequest, context: CredentialRouteContext) {
  return proxy(request, context);
}
