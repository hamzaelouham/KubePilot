import { NextRequest, NextResponse } from "next/server";

const resourceTypes = new Set(["pods", "deployments", "services", "nodes"]);

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ resourceType: string; name: string }> }
) {
  const { resourceType, name } = await params;
  const namespace = request.nextUrl.searchParams.get("namespace");
  const tab = request.nextUrl.searchParams.get("tab") ?? "detail";

  if (!resourceTypes.has(resourceType)) {
    return NextResponse.json(
      { code: "invalid_resource", message: "Unsupported resource type" },
      { status: 400 }
    );
  }

  const validTabs = new Set(["detail", "yaml", "logs", "events"]);
  if (!validTabs.has(tab)) {
    return NextResponse.json(
      { code: "invalid_tab", message: "Unsupported tab" },
      { status: 400 }
    );
  }

  if (resourceType !== "nodes" && !namespace) {
    return NextResponse.json(
      { code: "invalid_namespace", message: "Namespace is required for namespaced resources" },
      { status: 400 }
    );
  }

  const backendUrl = process.env.KUBEPILOT_BACKEND_URL ?? "http://127.0.0.1:8000";
  const pathSuffix = tab === "detail" ? "" : `/${tab}`;
  const target = new URL(
    `/api/v1/cluster/resources/${resourceType}/${encodeURIComponent(name)}${pathSuffix}`,
    backendUrl
  );

  if (namespace && resourceType !== "nodes") {
    target.searchParams.set("namespace", namespace);
  }
  target.searchParams.set("cluster", process.env.KUBEPILOT_CLUSTER_NAME ?? "primary");

  try {
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
      { status: 503 }
    );
  }
}
