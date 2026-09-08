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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PackageCard, type MarketplacePackage } from "@/components/package-card";

const PAGE_SIZE = 24;
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
  const response = await fetch(`/api/marketplace/packages?${search.toString()}`, {
    signal,
    cache: "no-store",
  });
  const body = (await response.json()) as MarketplaceResponse & { message?: string };
  if (!response.ok) throw new Error(body.message ?? "Unable to load packages");
  return body;
}

function SkeletonGrid() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {Array.from({ length: 6 }).map((_, index) => (
        <div
          key={index}
          className="flex flex-col gap-3 rounded-xl border border-border bg-surface-elevated p-4 shadow-sm"
        >
          <div className="flex items-start gap-3">
            <div className="size-9 shrink-0 animate-pulse rounded-md bg-muted" />
            <div className="flex-1 space-y-2">
              <div className="h-3.5 w-1/2 animate-pulse rounded bg-muted" />
              <div className="h-3 w-1/3 animate-pulse rounded bg-muted" />
            </div>
          </div>
          <div className="h-3 w-full animate-pulse rounded bg-muted" />
          <div className="h-3 w-3/4 animate-pulse rounded bg-muted" />
          <div className="mt-auto flex items-center justify-between pt-2">
            <div className="space-y-2">
              <div className="h-3 w-16 animate-pulse rounded bg-muted" />
              <div className="h-3.5 w-12 animate-pulse rounded bg-muted" />
            </div>
            <div className="h-7 w-16 animate-pulse rounded-lg bg-muted" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function MarketplaceBrowser() {
  const [packages, setPackages] = useState<MarketplacePackage[]>([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [loadingMore, setLoadingMore] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [sort, setSort] = useState<Sort>("relevance");
  const offsetRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed === debouncedQuery) return;
    const timer = setTimeout(() => setDebouncedQuery(trimmed), DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [query, debouncedQuery]);

  const fetchAt = useCallback(
    async (offset: number, replace: boolean) => {
      const controller = new AbortController();
      abortRef.current?.abort();
      abortRef.current = controller;
      if (replace) setStatus("loading");
      else setLoadingMore(true);
      try {
        const body = await fetchPage({ offset, query: debouncedQuery, sort }, controller.signal);
        setPackages((previous) =>
          replace || previous.length === 0 ? body.packages : [...previous, ...body.packages],
        );
        setTotal(body.total);
        offsetRef.current = offset + body.packages.length;
        setStatus("ready");
        setErrorMessage("");
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setErrorMessage(error instanceof Error ? error.message : "Unable to load packages");
        setStatus("error");
      } finally {
        setLoadingMore(false);
      }
    },
    [debouncedQuery, sort],
  );

  useEffect(() => {
    void Promise.resolve().then(() => fetchAt(0, true));
    return () => abortRef.current?.abort();
  }, [fetchAt]);

  const handleSort = useCallback((value: Sort | null) => {
    const next = value === "stars" ? "stars" : "relevance";
    if (next === sort) return;
    setStatus("loading");
    setSort(next);
  }, [sort]);

  const retry = useCallback(() => {
    const replace = offsetRef.current === 0;
    if (replace) setStatus("loading");
    setLoadingMore(!replace);
    void fetchAt(offsetRef.current, replace);
  }, [fetchAt]);

  const loadMore = useCallback(() => {
    setLoadingMore(true);
    void fetchAt(offsetRef.current, false);
  }, [fetchAt]);

  const hasPackages = packages.length > 0;
  const showLoadMore = hasPackages && packages.length < total;

  let content;
  if (status === "loading") {
    content = <SkeletonGrid />;
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
      <div>
        {status === "error" && (
          <div
            role="alert"
            className="mb-4 flex flex-wrap items-center gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700"
          >
            <span>{errorMessage || "Unable to load more packages."}</span>
            <Button variant="outline" size="xs" onClick={retry}>
              Retry
            </Button>
          </div>
        )}
        <div className="grid items-stretch gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {packages.map((pkg) => (
            <PackageCard key={pkg.package_id} pkg={pkg} />
          ))}
        </div>
        {showLoadMore && (
          <div className="mt-6 flex justify-center">
            <Button variant="secondary" onClick={loadMore} disabled={loadingMore}>
              {loadingMore ? "Loading…" : "Load more"}
            </Button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-end gap-3">
        <div className="min-w-60 flex-1">
          <label htmlFor="marketplace-packages-search" className="sr-only">
            Search packages
          </label>
          <Input
            id="marketplace-packages-search"
            type="search"
            placeholder="Search packages…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
        <div>
          <Select value={sort} onValueChange={handleSort}>
            <SelectTrigger aria-label="Sort packages" className="w-44">
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
    </div>
  );
}