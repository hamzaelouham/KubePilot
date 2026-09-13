import type { NextRequest } from "next/server";
import { proxyHelmRepository } from "@/lib/helm-repository-proxy";

type Context = { params: Promise<{ repositoryId: string }> };

export async function PATCH(request: NextRequest, { params }: Context) {
  return proxyHelmRepository(request, `/${encodeURIComponent((await params).repositoryId)}`);
}

export async function DELETE(request: NextRequest, { params }: Context) {
  return proxyHelmRepository(request, `/${encodeURIComponent((await params).repositoryId)}`);
}
