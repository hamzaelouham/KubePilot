import { NextRequest, NextResponse } from "next/server";
import { backendUrl } from "@/lib/backend";

type RouteContext = { params: Promise<{ providerId: string }> };

export async function GET(request: NextRequest, context: RouteContext) {
  const { providerId } = await context.params;
  const allowed = new URLSearchParams();
  for (const key of ["state", "code", "error"]) {
    const value = request.nextUrl.searchParams.get(key);
    if (value) allowed.set(key, value);
  }

  try {
    const response = await fetch(
      `${backendUrl()}/api/v1/settings/integrations/${encodeURIComponent(providerId)}/callback?${allowed.toString()}`,
      { cache: "no-store" },
    );
    const payload = await response.json().catch(() => null);
    const target = new URL("/settings/integrations", request.url);
    target.searchParams.set("provider", providerId);
    if (response.ok) {
      target.searchParams.set("connection", "connected");
    } else {
      target.searchParams.set("connection", "error");
      const errorCode = payload?.detail?.code;
      if (typeof errorCode === "string") target.searchParams.set("error", errorCode);
    }
    return NextResponse.redirect(target);
  } catch {
    const target = new URL("/settings/integrations", request.url);
    target.searchParams.set("provider", providerId);
    target.searchParams.set("connection", "backend_unavailable");
    return NextResponse.redirect(target);
  }
}
