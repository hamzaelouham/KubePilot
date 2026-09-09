const cache = new Map<string, { data: unknown; expiresAt: number }>();

const DEFAULT_TTL_MS = 30_000;

export async function cachedFetch(
  url: string,
  options: RequestInit & { ttlMs?: number } = {},
): Promise<unknown> {
  const { ttlMs = DEFAULT_TTL_MS, ...fetchOptions } = options;
  const now = Date.now();
  const entry = cache.get(url);
  if (entry && entry.expiresAt > now) return entry.data;

  const response = await fetch(url, { ...fetchOptions, cache: "no-store" });
  const body = await response.json();
  if (response.ok) {
    cache.set(url, { data: body, expiresAt: now + ttlMs });
  }
  return body;
}

export function invalidateCache(pattern?: string) {
  if (!pattern) {
    cache.clear();
    return;
  }
  for (const key of cache.keys()) {
    if (key.startsWith(pattern)) cache.delete(key);
  }
}
