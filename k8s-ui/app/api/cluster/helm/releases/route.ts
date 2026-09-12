import type { NextRequest } from "next/server";
import { proxyHelmRelease } from "@/lib/helm-release-proxy";

export async function GET(request: NextRequest) {
  return proxyHelmRelease(request, "", false);
}
