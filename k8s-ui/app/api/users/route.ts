import { NextRequest, NextResponse } from "next/server";

const backendUrl = process.env.KUBEPILOT_BACKEND_URL ?? "http://127.0.0.1:8000";

async function proxy(request: NextRequest, method: string) {
  try {
    const response = await fetch(`${backendUrl}/api/v1/users`, {
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

export async function GET(request: NextRequest) {
  return proxy(request, "GET");
}

export async function POST(request: NextRequest) {
  return proxy(request, "POST");
}