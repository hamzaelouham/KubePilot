import type { NextRequest } from "next/server";
import { proxyManagement } from "@/lib/resource-management-proxy";

export async function DELETE(request: NextRequest, { params }: { params: Promise<{ resourceType: string; name: string }> }) {
  const { resourceType, name } = await params;
  return proxyManagement(request, resourceType, name);
}
