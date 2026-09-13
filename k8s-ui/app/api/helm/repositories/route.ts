import type { NextRequest } from "next/server";
import { proxyHelmRepository } from "@/lib/helm-repository-proxy";

export async function GET(request: NextRequest) {
  return proxyHelmRepository(request);
}

export async function POST(request: NextRequest) {
  return proxyHelmRepository(request);
}
