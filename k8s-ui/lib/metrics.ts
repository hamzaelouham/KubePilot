export type UtilizationTone = "good" | "warning" | "critical" | "unavailable";

export function utilizationTone(percent: number | null): UtilizationTone {
  if (percent === null || percent < 0) return "unavailable";
  if (percent >= 90) return "critical";
  if (percent >= 70) return "warning";
  return "good";
}

export function utilizationToneClasses(tone: UtilizationTone): string {
  switch (tone) {
    case "good":
      return "bg-green-100 text-green-700";
    case "warning":
      return "bg-amber-100 text-amber-700";
    case "critical":
      return "bg-red-100 text-red-700";
    case "unavailable":
    default:
      return "bg-slate-200 text-slate-600";
  }
}

export function formatMillicores(millicores: number | null): string {
  if (millicores === null) return "—";
  if (millicores >= 1000) return `${(millicores / 1000).toFixed(1)}c`;
  return `${Math.round(millicores)}m`;
}

export function formatBytes(bytes: number | null): string {
  if (bytes === null) return "—";
  if (bytes >= 2 ** 40) return `${(bytes / 2 ** 40).toFixed(1)} TiB`;
  if (bytes >= 2 ** 30) return `${(bytes / 2 ** 30).toFixed(1)} GiB`;
  if (bytes >= 2 ** 20) return `${(bytes / 2 ** 20).toFixed(1)} MiB`;
  if (bytes >= 2 ** 10) return `${(bytes / 2 ** 10).toFixed(1)} KiB`;
  return `${Math.round(bytes)} B`;
}

export function utilizationPercent(used: number | null, total: number | null): number | null {
  if (used === null || total === null || total === 0) return null;
  return Math.round((used / total) * 100);
}

export type NodeMetricItem = {
  name: string;
  cpu_usage_millicores: number;
  cpu_allocatable_millicores: number | null;
  memory_usage_bytes: number;
  memory_allocatable_bytes: number | null;
  storage_capacity_bytes: number | null;
  storage_allocatable_bytes: number | null;
};

export type NodesMetricsResponse = {
  available: boolean;
  reason: string | null;
  items: NodeMetricItem[];
};

export type WorkloadMetricItem = {
  namespace: string;
  name: string;
  kind: string;
  cpu_usage_millicores: number;
  memory_usage_bytes: number;
};

export type NamespaceMetricSummary = {
  namespace: string;
  cpu_usage_millicores: number;
  memory_usage_bytes: number;
  pod_count: number;
};

export type NamespaceMetricsResponse = {
  available: boolean;
  reason: string | null;
  workloads: WorkloadMetricItem[];
  summary: NamespaceMetricSummary | null;
};

export type MetricsSummaryResponse = {
  available: boolean;
  reason: string | null;
  namespaces: NamespaceMetricSummary[];
};

export type StorageMetricsItem = {
  name: string;
  kind: string;
  capacity_bytes: number | null;
  utilization: string | null;
};

export type StorageMetricsResponse = {
  available: boolean;
  reason: string | null;
  items: StorageMetricsItem[];
};
