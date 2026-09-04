import { NextRequest, NextResponse } from "next/server";

const clusterScoped = new Set(["nodes", "persistent-volumes", "cluster-roles", "storage-classes"]);

const resourceTypes = new Set([
  "pods",
  "deployments",
  "services",
  "nodes",
  "endpoints",
  "replica-sets",
  "daemon-sets",
  "stateful-sets",
  "jobs",
  "cron-jobs",
  "replication-controllers",
  "persistent-volumes",
  "persistent-volume-claims",
  "cluster-roles",
  "storage-classes",
]);

export async function GET(request: NextRequest) {
  const resource = request.nextUrl.searchParams.get("resource") ?? "pods";
  const namespace = request.nextUrl.searchParams.get("namespace");

  if (!resourceTypes.has(resource)) {
    return NextResponse.json(
      { code: "invalid_resource", message: "Unsupported resource type" },
      { status: 400 },
    );
  }

  const backendUrl = process.env.KUBEPILOT_BACKEND_URL ?? "http://127.0.0.1:8000";
  const target = new URL(`/api/v1/cluster/resources/${resource}`, backendUrl);
  if (namespace && !clusterScoped.has(resource)) {
    target.searchParams.set("namespace", namespace);
  }

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
