"use client";

import { useState } from "react";
import { Star } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { packageLogo, publisherOf, type MarketplacePackage } from "@/components/package-card";

function PackageLogo({ pkg }: { pkg: MarketplacePackage }) {
  const [logoFailed, setLogoFailed] = useState(false);
  const logo = logoFailed ? null : packageLogo(pkg);
  if (!logo) {
    return (
      <div className="flex size-10 shrink-0 items-center justify-center rounded-md bg-muted text-sm font-medium text-muted-foreground">
        {pkg.name.slice(0, 2).toUpperCase()}
      </div>
    );
  }
  return (
    <img
      src={logo}
      alt=""
      className="size-10 shrink-0 rounded-md object-cover"
      onError={() => setLogoFailed(true)}
    />
  );
}

function HelmInstallBlock({ pkg }: { pkg: MarketplacePackage }) {
  const repo = pkg.repository;
  if (!repo?.name) return null;
  const commands: string[] = [];
  if (repo.url) commands.push(`helm repo add ${repo.name} ${repo.url}`);
  commands.push(`helm install my-release ${repo.name}/${pkg.name}`);
  return (
    <div>
      <h4 className="text-sm font-medium text-foreground">Helm install</h4>
      <pre className="mt-2 overflow-x-auto rounded-lg bg-muted p-3 font-mono text-xs text-foreground">
        {commands.join("\n")}
      </pre>
    </div>
  );
}

function PackageDetailsBody({
  pkg,
  onInstall,
}: {
  pkg: MarketplacePackage;
  onInstall?: () => void;
}) {
  const showBadges = pkg.official || pkg.signed || pkg.deprecated;

  return (
    <>
      <DialogHeader className="border-b border-border pb-4">
        <div className="flex items-start gap-3">
          <PackageLogo pkg={pkg} />
          <div className="min-w-0">
            <DialogTitle className="truncate">{pkg.name}</DialogTitle>
            <p className="text-sm text-muted-foreground">{publisherOf(pkg)}</p>
          </div>
        </div>
        {showBadges && (
          <div className="flex flex-wrap gap-1.5">
            {pkg.official && <Badge variant="secondary">Official</Badge>}
            {pkg.signed && <Badge variant="outline">Signed</Badge>}
            {pkg.deprecated && <Badge variant="destructive">Deprecated</Badge>}
          </div>
        )}
      </DialogHeader>
      <div className="flex max-h-[calc(100dvh-12rem)] flex-col gap-4 overflow-y-auto pr-1 sm:max-h-[60vh]">
        <DialogDescription>
          {pkg.description ?? "No description provided."}
        </DialogDescription>
        <dl className="grid grid-cols-1 gap-x-4 gap-y-3 rounded-xl border border-border bg-muted/30 p-4 text-sm sm:grid-cols-2">
          <dt className="text-muted-foreground">Repository</dt>
          <dd className="truncate text-foreground">{pkg.repository?.name ?? "—"}</dd>
          <dt className="text-muted-foreground">Latest version</dt>
          <dd className="truncate text-foreground">{pkg.version ?? "—"}</dd>
          {pkg.app_version != null && (
            <>
              <dt className="text-muted-foreground">App version</dt>
              <dd className="truncate text-foreground">{pkg.app_version}</dd>
            </>
          )}
          {pkg.license != null && (
            <>
              <dt className="text-muted-foreground">License</dt>
              <dd className="truncate text-foreground">{pkg.license}</dd>
            </>
          )}
          {pkg.stars != null && (
            <>
              <dt className="text-muted-foreground">Stars</dt>
              <dd className="flex items-center gap-1 text-foreground">
                <Star className="size-3.5 text-muted-foreground" aria-hidden="true" />
                {pkg.stars}
              </dd>
            </>
          )}
        </dl>
        <HelmInstallBlock pkg={pkg} />
      </div>
      <DialogFooter>
        <Button type="button" className="w-full sm:w-auto" onClick={onInstall}>
          Install
        </Button>
      </DialogFooter>
    </>
  );
}

export function PackageDetailsDialog({
  pkg,
  onOpenChange,
  onInstall,
}: {
  pkg: MarketplacePackage | null;
  onOpenChange: (open: boolean) => void;
  onInstall?: () => void;
}) {
  return (
    <Dialog open={pkg !== null} onOpenChange={onOpenChange}>
      {pkg && (
        <DialogContent className="max-h-[calc(100dvh-1rem)] w-[calc(100%-1rem)] overflow-hidden sm:max-h-[90dvh] sm:w-full sm:max-w-lg">
          <PackageDetailsBody key={pkg.package_id} pkg={pkg} onInstall={onInstall} />
        </DialogContent>
      )}
    </Dialog>
  );
}
