import { NextRequest, NextResponse } from "next/server";

const backendUrl = process.env.KUBEPILOT_BACKEND_URL ?? "http://127.0.0.1:8000";

export async function GET(request: NextRequest) {
  try {
    const target = new URL(`${backendUrl}/api/v1/cluster/namespaces`);
    const cluster = request.nextUrl.searchParams.get("cluster");
    if (cluster) target.searchParams.set("cluster", cluster);
    const response = await fetch(target, {
      headers: { cookie: request.headers.get("cookie") ?? "" },
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
