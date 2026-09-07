import { NextRequest, NextResponse } from "next/server";

const metricTypes = new Set(["nodes", "namespaces", "summary", "storage"]);

export async function GET(request: NextRequest) {
  const metricType = request.nextUrl.searchParams.get("type") ?? "nodes";
  const namespace = request.nextUrl.searchParams.get("namespace");

  if (!metricTypes.has(metricType)) {
    return NextResponse.json(
      { code: "invalid_metric_type", message: "Unsupported metric type" },
      { status: 400 },
    );
  }

  if (metricType === "namespaces" && !namespace) {
    return NextResponse.json(
      { code: "invalid_namespace", message: "Namespace is required for namespace metrics" },
      { status: 400 },
    );
  }

  const backendUrl = process.env.KUBEPILOT_BACKEND_URL ?? "http://127.0.0.1:8000";
  let target: URL;

  if (metricType === "namespaces" && namespace) {
    target = new URL(`/api/v1/cluster/metrics/namespaces/${encodeURIComponent(namespace)}`, backendUrl);
  } else {
    target = new URL(`/api/v1/cluster/metrics/${metricType}`, backendUrl);
  }
  const clusterParam = request.nextUrl.searchParams.get("cluster");
  if (clusterParam) target.searchParams.set("cluster", clusterParam);

  try {
    const response = await fetch(target, {
      headers: { cookie: request.headers.get("cookie") ?? "" },
      cache: "no-store",
    });
    return new NextResponse(response.body, {
      status: response.status,
      headers: { "content-type": response.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    return NextResponse.json(
      { code: "backend_unavailable", message: "The backend service is unavailable" },
      { status: 503 },
    );
  }
}
