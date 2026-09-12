import { cookies } from "next/headers";
import { SESSION_COOKIE_NAME } from "@/lib/auth-constants";
import { apiErrorMessage } from "@/lib/api-error";
import { backendUrl } from "@/lib/backend";
import type { MarketplacePackage } from "@/components/package-card";

export type InitialMarketplaceData = {
  packages: MarketplacePackage[];
  total: number;
  errorMessage: string | null;
};

export async function fetchInitialMarketplaceData(): Promise<InitialMarketplaceData> {
  const cookieStore = await cookies();
  const sessionCookie = cookieStore.get(SESSION_COOKIE_NAME)?.value;
  if (!sessionCookie) {
    return { packages: [], total: 0, errorMessage: "Your session could not be verified." };
  }

  const target = new URL("/api/v1/marketplace/packages", backendUrl());
  target.searchParams.set("limit", "12");
  target.searchParams.set("offset", "0");

  try {
    const response = await fetch(target, {
      headers: { cookie: `${SESSION_COOKIE_NAME}=${sessionCookie}` },
      cache: "no-store",
    });
    const body = (await response.json()) as { packages?: MarketplacePackage[]; total?: number; message?: string; code?: string };
    if (!response.ok || !Array.isArray(body.packages) || typeof body.total !== "number") {
      return {
        packages: [],
        total: 0,
        errorMessage: apiErrorMessage(body, "Marketplace data is temporarily unavailable."),
      };
    }
    return { packages: body.packages, total: body.total, errorMessage: null };
  } catch {
    return {
      packages: [],
      total: 0,
      errorMessage: "Marketplace data is temporarily unavailable.",
    };
  }
}
