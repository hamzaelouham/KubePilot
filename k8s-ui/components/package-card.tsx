"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";

export type MarketplacePackageRepository = {
  name: string;
  display_name?: string | null;
  organization_name?: string | null;
  organization_display_name?: string | null;
  url?: string | null;
  kind?: number | null;
};

export type MarketplacePackage = {
  package_id: string;
  name: string;
  normalized_name?: string | null;
  description?: string | null;
  version?: string | null;
  app_version?: string | null;
  logo_image_id?: string | null;
  stars?: number | null;
  deprecated: boolean;
  official: boolean;
  signed: boolean;
  license?: string | null;
  repository?: MarketplacePackageRepository | null;
};

function packageLogo(pkg: MarketplacePackage) {
  return pkg.logo_image_id ? `https://artifacthub.io/image/${encodeURIComponent(pkg.logo_image_id)}` : null;
}

export function PackageCard({ pkg }: { pkg: MarketplacePackage }) {
  const [logoFailed, setLogoFailed] = useState(false);
  const logo = logoFailed ? null : packageLogo(pkg);
  const publisher =
    pkg.repository?.organization_display_name ??
    pkg.repository?.display_name ??
    pkg.repository?.name ??
    "Unknown publisher";

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-surface-elevated p-4 shadow-sm">
      <div className="flex items-start gap-3">
        {logo ? (
          <img
            src={logo}
            alt=""
            className="size-9 shrink-0 rounded-md object-cover"
            onError={() => setLogoFailed(true)}
          />
        ) : (
          <div className="flex size-9 shrink-0 items-center justify-center rounded-md bg-muted text-xs font-medium text-muted-foreground">
            {pkg.name.slice(0, 2).toUpperCase()}
          </div>
        )}
        <div className="min-w-0">
          <h3 className="truncate text-sm font-medium text-foreground">{pkg.name}</h3>
          <p className="truncate text-xs text-muted-foreground">{publisher}</p>
        </div>
      </div>
      <p className="line-clamp-2 text-sm text-muted-foreground">{pkg.description ?? "No description provided."}</p>
      <div className="mt-auto flex items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground">Latest version</p>
          <p className="truncate text-sm font-medium text-foreground">{pkg.version ?? "—"}</p>
        </div>
        <Button size="sm" variant="default">
          Install
        </Button>
      </div>
    </div>
  );
}