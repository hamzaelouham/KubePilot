"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
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

export function packageLogo(pkg: MarketplacePackage) {
  return pkg.logo_image_id ? `https://artifacthub.io/image/${encodeURIComponent(pkg.logo_image_id)}` : null;
}

export function publisherOf(pkg: MarketplacePackage) {
  return (
    pkg.repository?.organization_display_name ??
    pkg.repository?.display_name ??
    pkg.repository?.name ??
    "Unknown publisher"
  );
}

export function PackageCard({
  pkg,
  onSelect,
  onInstall,
}: {
  pkg: MarketplacePackage;
  onSelect: () => void;
  onInstall?: () => void;
}) {
  const [logoFailed, setLogoFailed] = useState(false);
  const logo = logoFailed ? null : packageLogo(pkg);
  const publisher = publisherOf(pkg);

  return (
    <article className="group relative flex min-h-64 flex-col gap-4 rounded-2xl border border-border bg-card p-5 shadow-sm transition duration-150 hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md">
      <button
        type="button"
        onClick={onSelect}
        aria-label={`View details for ${pkg.name}`}
        className="absolute inset-0 rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
      />
      <div className="flex items-start gap-3.5">
        {logo ? (
          <img
            src={logo}
            alt=""
            className="size-12 shrink-0 rounded-xl border border-border bg-background object-cover p-1"
            onError={() => setLogoFailed(true)}
          />
        ) : (
          <div className="flex size-12 shrink-0 items-center justify-center rounded-xl border border-border bg-primary/10 text-sm font-semibold text-primary">
            {pkg.name.slice(0, 2).toUpperCase()}
          </div>
        )}
        <div className="min-w-0">
          <h3 className="truncate text-base font-semibold text-foreground">{pkg.name}</h3>
          <p className="mt-0.5 truncate text-sm text-muted-foreground">{publisher}</p>
          {(pkg.official || pkg.signed || pkg.deprecated) && (
            <div className="mt-2 flex flex-wrap gap-1">
              {pkg.official && <Badge variant="secondary">Official</Badge>}
              {pkg.signed && <Badge variant="outline">Signed</Badge>}
              {pkg.deprecated && <Badge variant="destructive">Deprecated</Badge>}
            </div>
          )}
        </div>
      </div>
      <p className="line-clamp-3 text-sm leading-6 text-muted-foreground">{pkg.description ?? "No description provided."}</p>
      <div className="mt-auto flex items-end justify-between gap-3 border-t border-border pt-4">
        <div className="min-w-0">
          <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">Latest version</p>
          <p className="truncate text-sm font-medium text-foreground">{pkg.version ?? "—"}</p>
        </div>
        <Button size="sm" variant="default" className="relative z-10" onClick={(event) => { event.stopPropagation(); onInstall?.(); }}>
          Install
        </Button>
      </div>
    </article>
  );
}
