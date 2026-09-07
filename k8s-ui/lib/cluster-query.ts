export function withCluster(path: string, cluster: string): string {
  if (!cluster) return path;
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}cluster=${encodeURIComponent(cluster)}`;
}