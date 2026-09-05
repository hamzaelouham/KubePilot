import { NextRequest, NextResponse } from "next/server";

const backendUrl = process.env.KUBEPILOT_BACKEND_URL ?? "http://127.0.0.1:8000";

type RouteContext = { params: Promise<{ id: string }> };

async function proxy(request: NextRequest, { params }: RouteContext, method: string, action: string) {
  const { id } = await params;

  try {
    const response = await fetch(`${backendUrl}/api/v1/users/${encodeURIComponent(id)}/${action}`, {
      method,
      headers: {
        cookie: request.headers.get("cookie") ?? "",
        "content-type": "application/json",
      },
      body: method === "GET" ? undefined : await request.text(),
      cache: "no-store",
    });

    const body = await response.text();
    return new NextResponse(body, {
      status: response.status,
      headers: { "content-type": "application/json" },
    });
  } catch {
    return NextResponse.json(
      { code: "backend_unavailable", message: "The backend service is unavailable" },
      { status: 503 },
    );
  }
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  return proxy(request, context, "PATCH", "role");
}

export async function POST(request: NextRequest, context: RouteContext) {
  return proxy(request, context, "POST", "deactivate");
}