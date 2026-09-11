import type { NextRequest } from "next/server";
import { proxyManagement } from "@/lib/resource-management-proxy";

type Context = { params: Promise<{ resourceType: string }> };

export async function GET(request: NextRequest, { params }: Context) {
  return proxyManagement(request, (await params).resourceType);
}

export async function POST(request: NextRequest, { params }: Context) {
  return proxyManagement(request, (await params).resourceType);
}
