"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PackageCard, type MarketplacePackage } from "@/components/package-card";
import { PackageDetailsDialog } from "@/components/package-details-dialog";
import { InstallDialog } from "@/components/install-dialog";
import { cachedFetch } from "@/lib/marketplace-cache";
import { apiErrorMessage } from "@/lib/api-error";

const PAGE_SIZE = 12;
const DEBOUNCE_MS = 350;

type Sort = "relevance" | "stars";

type MarketplaceResponse = { packages: MarketplacePackage[]; total: number };

async function fetchPage(
  params: { offset: number; query: string; sort: Sort },
  signal: AbortSignal,
) {
  const search = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(params.offset) });
  if (params.query) search.set("ts_query_web", params.query);
  if (params.sort === "stars") search.set("sort", params.sort);
  const body = await cachedFetch(`/api/marketplace/packages?${search.toString()}`, {
    signal,
  });
  if (!body || typeof body !== "object") throw new Error("Unable to load packages");
  const typed = body as MarketplaceResponse;
  if (!Array.isArray(typed.packages)) throw new Error(apiErrorMessage(typed, "Unable to load packages"));
  return typed;
}

function getPageItems(currentPage: number, totalPages: number): (number | "...")[] {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }
  const pages = new Set([1, totalPages, currentPage - 1, currentPage, currentPage + 1]);
  const sorted = [...pages]
    .filter((n) => n >= 1 && n <= totalPages)
    .sort((a, b) => a - b);
  const items: (number | "...")[] = [];
  sorted.forEach((item, index) => {
    if (index > 0 && item - sorted[index - 1] > 1) items.push("...");
    items.push(item);
  });
  return items;
}

function PackageCardSkeleton() {
  return (
    <div
      aria-hidden="true"
      className="flex min-h-64 flex-col gap-4 rounded-2xl border border-border bg-card p-4 shadow-sm sm:p-5"
    >
      <div className="flex items-start gap-3.5">
        <Skeleton className="size-11 shrink-0 rounded-xl sm:size-12" />
        <div className="flex min-w-0 flex-1 flex-col gap-2">
          <Skeleton className="h-5 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-5 w-20" />
        </div>
      </div>
      <div className="flex flex-col gap-2">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-11/12" />
        <Skeleton className="h-4 w-2/3" />
      </div>
      <div className="mt-auto flex items-end justify-between gap-3 border-t border-border pt-4">
        <div className="flex min-w-0 flex-1 flex-col gap-2">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-4 w-16" />
        </div>
        <Skeleton className="h-9 w-full rounded-md sm:w-20" />
      </div>
    </div>
  );
}

function PackageGridSkeleton() {
  return (
    <div
      role="status"
      aria-label="Loading packages"
      className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
    >
      {Array.from({ length: 8 }, (_, index) => (
        <PackageCardSkeleton key={index} />
      ))}
    </div>
  );
}

export function MarketplaceBrowser({
  cluster,
  clusters,
  onSelectCluster,
  initialData,
}: {
  cluster: string;
  clusters: string[];
  onSelectCluster: (cluster: string) => void;
  initialData: MarketplaceResponse & { errorMessage: string | null };
}) {
  const [packages, setPackages] = useState<MarketplacePackage[]>(initialData.packages);
  const [total, setTotal] = useState(initialData.total);
  const [status, setStatus] = useState<"loading" | "ready" | "error">(
    initialData.errorMessage ? "error" : "ready",
  );
  const [errorMessage, setErrorMessage] = useState(initialData.errorMessage ?? "");
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [sort, setSort] = useState<Sort>("relevance");
  const [page, setPage] = useState(0);
  const [selectedPackage, setSelectedPackage] = useState<MarketplacePackage | null>(null);
  const [installTarget, setInstallTarget] = useState<MarketplacePackage | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const initialLoadRef = useRef(true);

  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed === debouncedQuery) return;
    const timer = setTimeout(() => {
      if (trimmed === debouncedQuery) return;
      setDebouncedQuery(trimmed);
      setPage(0);
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [query, debouncedQuery]);

  const fetchAt = useCallback(
    async (offset: number) => {
      const controller = new AbortController();
      abortRef.current?.abort();
      abortRef.current = controller;
      setStatus("loading");
      setErrorMessage("");
      try {
        const body = await fetchPage({ offset, query: debouncedQuery, sort }, controller.signal);
        setPackages(body.packages);
        setTotal(body.total);
        setStatus("ready");
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setErrorMessage(error instanceof Error ? error.message : "Unable to load packages");
        setStatus("error");
      }
    },
    [debouncedQuery, sort],
  );

  useEffect(() => {
    if (initialLoadRef.current) {
      initialLoadRef.current = false;
      return () => abortRef.current?.abort();
    }
    void Promise.resolve().then(() => fetchAt(0));
    return () => abortRef.current?.abort();
  }, [fetchAt]);

  const handleSort = useCallback((value: Sort | null) => {
    const next = value === "stars" ? "stars" : "relevance";
    if (next === sort) return;
    setPage(0);
    setSort(next);
  }, [sort]);

  const retry = useCallback(() => {
    void fetchAt(page * PAGE_SIZE);
  }, [fetchAt, page]);

  const goToPage = useCallback(
    (nextPage: number) => {
      setPage(nextPage);
      void fetchAt(nextPage * PAGE_SIZE);
    },
    [fetchAt],
  );

  const hasPackages = packages.length > 0;
  const totalPages = total > 0 ? Math.ceil(total / PAGE_SIZE) : 0;

  let content;
  if (status === "loading" && !hasPackages) {
    content = (
      <PackageGridSkeleton />
    );
  } else if (status === "error" && !hasPackages) {
    content = (
      <Empty>
        <EmptyContent>
          <EmptyHeader>
            <EmptyTitle>Couldn&apos;t load packages</EmptyTitle>
          </EmptyHeader>
          <EmptyDescription>
            {errorMessage || "Marketplace data is temporarily unavailable."}
          </EmptyDescription>
        </EmptyContent>
        <Button variant="outline" size="sm" onClick={retry}>
          Retry
        </Button>
      </Empty>
    );
  } else if (!hasPackages) {
    content = (
      <Empty>
        <EmptyContent>
          <EmptyHeader>
            <EmptyTitle>No packages found</EmptyTitle>
          </EmptyHeader>
          <EmptyDescription>No packages match your criteria.</EmptyDescription>
        </EmptyContent>
      </Empty>
    );
  } else {
    content = (
      <div aria-busy={status === "loading"}>
        {status === "loading" && (
          <p role="status" className="mb-3 text-sm text-muted-foreground">
            Updating packages…
          </p>
        )}
        {status === "error" && (
          <div
            role="alert"
            className="mb-4 flex flex-wrap items-center gap-3 rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive"
          >
            <span>{errorMessage || "Unable to load packages."}</span>
            <Button variant="outline" size="xs" onClick={retry}>
              Retry
            </Button>
          </div>
        )}
        <div className="grid grid-cols-1 items-stretch gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {packages.map((pkg) => (
            <PackageCard
              key={pkg.package_id}
              pkg={pkg}
              onSelect={() => setSelectedPackage(pkg)}
              onInstall={() => setInstallTarget(pkg)}
            />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6 grid gap-3 sm:flex sm:flex-wrap sm:items-end">
        <div className="min-w-0 flex-1">
          <label htmlFor="marketplace-packages-search" className="sr-only">
            Search packages
          </label>
          <Input
            id="marketplace-packages-search"
            type="search"
            placeholder="Search packages…"
            value={query}
            disabled={status === "loading"}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
        <div className="w-full sm:w-auto">
          <Select value={sort} onValueChange={handleSort} disabled={status === "loading"}>
            <SelectTrigger aria-label="Sort packages" className="w-full sm:w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent align="end">
              <SelectItem value="relevance">Relevance</SelectItem>
              <SelectItem value="stars">Most stars</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
      {content}
      {hasPackages && totalPages > 1 && (
        <nav
          aria-label="Package pages"
          className="mt-6 flex flex-wrap items-center justify-center gap-1"
        >
          <Button
            variant="outline"
            size="sm"
            onClick={() => goToPage(page - 1)}
            disabled={status === "loading" || page === 0}
          >
            Previous
          </Button>
          {getPageItems(page, totalPages).map((item, index) =>
            item === "..." ? (
              <span
                key={`ellipsis-${index}`}
                className="px-1 text-sm text-muted-foreground"
              >
                …
              </span>
            ) : (
              <Button
                key={item}
                variant={item === page + 1 ? "default" : "outline"}
                size="sm"
                aria-current={item === page + 1 ? "page" : undefined}
                disabled={status === "loading"}
                onClick={() => goToPage(item - 1)}
              >
                {item}
              </Button>
            ),
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => goToPage(page + 1)}
            disabled={status === "loading" || page >= totalPages - 1}
          >
            Next
          </Button>
        </nav>
      )}
      <PackageDetailsDialog
        pkg={selectedPackage}
        onOpenChange={(open) => {
          if (!open) setSelectedPackage(null);
        }}
        onInstall={() => {
          if (selectedPackage) setInstallTarget(selectedPackage);
          setSelectedPackage(null);
        }}
      />
      <InstallDialog
        pkg={installTarget}
        cluster={cluster}
        clusters={clusters}
        onSelectCluster={onSelectCluster}
        onOpenChange={(open) => {
          if (!open) setInstallTarget(null);
        }}
      />
    </div>
  );
}
