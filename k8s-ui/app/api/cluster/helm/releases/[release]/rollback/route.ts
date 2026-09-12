import type { NextRequest } from "next/server";
import { proxyHelmRelease } from "@/lib/helm-release-proxy";

export async function POST(request: NextRequest, { params }: { params: Promise<{ release: string }> }) {
  const { release } = await params;
  return proxyHelmRelease(request, `/${encodeURIComponent(release)}/rollback`, true);
}
