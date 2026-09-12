import type { NextRequest } from "next/server";
import { proxyHelmRelease } from "@/lib/helm-release-proxy";

export async function GET(request: NextRequest, { params }: { params: Promise<{ release: string }> }) {
  const { release } = await params;
  return proxyHelmRelease(request, `/${encodeURIComponent(release)}/history`, true);
}
