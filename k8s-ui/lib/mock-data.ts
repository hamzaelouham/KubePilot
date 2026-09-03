export type StatCardItem = {
  label: string;
  value: string;
  detail: string;
  tone: "emerald" | "blue" | "amber" | "violet" | "rose";
};

export const stats: StatCardItem[] = [
  { label: "Ready nodes", value: "16/18", detail: "+2 this week", tone: "emerald" },
  { label: "Healthy workloads", value: "84%", detail: "7 failing", tone: "blue" },
  { label: "CPU usage", value: "62%", detail: "Up 8%", tone: "amber" },
  { label: "Memory pressure", value: "41%", detail: "Within budget", tone: "violet" },
];

export const namespaces = [
  { name: "platform", pods: 112, cpu: "42%", memory: "58%", status: "Healthy" },
  { name: "payments", pods: 74, cpu: "28%", memory: "31%", status: "Healthy" },
  { name: "observability", pods: 38, cpu: "68%", memory: "64%", status: "Warning" },
  { name: "data-lake", pods: 21, cpu: "71%", memory: "72%", status: "Warning" },
];

export const workloadRows = [
  { name: "web-frontend", type: "Deployment", namespace: "platform", replicas: "6/6", age: "3d", status: "Ready" },
  { name: "billing-api", type: "Deployment", namespace: "payments", replicas: "4/4", age: "8h", status: "Ready" },
  { name: "prometheus", type: "StatefulSet", namespace: "observability", replicas: "1/1", age: "12d", status: "Ready" },
  { name: "worker-jobs", type: "CronJob", namespace: "platform", replicas: "-", age: "2h", status: "Running" },
  { name: "data-sync", type: "Job", namespace: "data-lake", replicas: "-", age: "1h", status: "Succeeded" },
];

export const recentEvents = [
  { message: "Deployment web-frontend scaled to 6 replicas", time: "2m ago", source: "kube-controller-manager" },
  { message: "billing-api restarted after image pull retry", time: "12m ago", source: "kubelet" },
  { message: "Node ip-10-0-0-22 became Ready", time: "28m ago", source: "node-controller" },
  { message: "Ingress certificate renewed for prod.example.com", time: "1h ago", source: "cert-manager" },
];

export const alerts = [
  { title: "CPU pressure on observability namespace", severity: "warning", detail: "Prometheus is nearing its CPU limit." },
  { title: "Ingress misconfiguration detected", severity: "error", detail: "Two endpoints are failing readiness checks." },
  { title: "Backup policy not enforced", severity: "info", detail: "A cluster snapshot is due within 24 hours." },
];
