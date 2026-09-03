import { DashboardShell } from "@/components/dashboard-shell";
import { CoreResourceView } from "@/components/core-resource-view";

const workloads = [
  { name: "test", namespace: "default", labels: "k8s-app: test", pods: "2 / 1", age: "4 hours", image: "luksa/kubia", status: "error" },
  { name: "kubia", namespace: "default", labels: "app: kubia", pods: "3 / 3", age: "11 days", image: "luksa/kubia", status: "ok" },
];

const pods = [
  { name: "kubia-abc123", status: "Running", ready: "1/1", restarts: "0", age: "11 days" },
  { name: "kubia-def456", status: "Running", ready: "1/1", restarts: "1", age: "4 hours" },
  { name: "test-xyz789", status: "CrashLoopBackOff", ready: "0/1", restarts: "7", age: "4 hours" },
];

const namespaces = [
  { name: "default", status: "Active", pods: 18, age: "11 days" },
  { name: "kube-system", status: "Active", pods: 29, age: "11 days" },
  { name: "monitoring", status: "Active", pods: 12, age: "7 days" },
];

const pieData = [
  { label: "Deployments", values: [50, 50], color: ["#e74c3c", "#22c55e"] },
  { label: "Pods", values: [80, 20], color: ["#22c55e", "#e74c3c"] },
  { label: "Replica Sets", values: [33.3, 66.7], color: ["#e74c3c", "#22c55e"] },
];

function DonutChart({ values, colors }: { values: number[]; colors: string[] }) {
  const [a, b] = values;
  const degrees = (a / (a + b)) * 360;

  return (
    <div className="relative mx-auto h-28 w-28">
      <div
        className="absolute inset-0 rounded-full"
        style={{
          background: `conic-gradient(${colors[0]} 0deg ${degrees}deg, ${colors[1]} ${degrees}deg 360deg)`,
        }}
      />
      <div className="absolute inset-[18px] rounded-full bg-[#f5f7f9]" />
      <div className="absolute inset-0 flex items-center justify-center text-sm font-medium text-slate-700">
        <span>{a.toFixed(0)}%</span>
      </div>
    </div>
  );
}

function renderResource(resource: string, namespace: string) {
  switch (resource) {
    case "overview":
      return (
        <div className="space-y-8">
          <div className="mb-3">
            <h2 className="text-3xl font-semibold text-slate-700">Workloads</h2>
          </div>

          <div className="rounded-xl border border-slate-200 bg-[#f2f5f7] p-5">
            <h3 className="mb-6 text-2xl font-semibold text-slate-700">Workload Status</h3>
            <div className="grid gap-8 md:grid-cols-3">
              {pieData.map((pie) => (
                <div key={pie.label} className="text-center">
                  <div className="flex justify-center">
                    <DonutChart values={pie.values} colors={pie.color} />
                  </div>
                  <p className="mt-3 text-lg text-slate-700">{pie.label}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white">
            <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
              <h3 className="text-2xl font-semibold text-slate-700">Deployments</h3>
              <button className="border border-slate-200 bg-slate-100 px-2 py-1 text-sm text-slate-600">☰</button>
            </div>

            <div className="overflow-hidden">
              <table className="min-w-full text-left text-base">
                <thead className="bg-slate-100 text-slate-600">
                  <tr>
                    <th className="px-4 py-3 font-medium">Name</th>
                    <th className="px-4 py-3 font-medium">Namespace Labels</th>
                    <th className="px-4 py-3 font-medium">Pods</th>
                    <th className="px-4 py-3 font-medium">Age</th>
                    <th className="px-4 py-3 font-medium">Images</th>
                  </tr>
                </thead>
                <tbody>
                  {workloads.map((item) => (
                    <tr key={item.name} className="border-t border-slate-200 text-slate-700">
                      <td className="px-4 py-4">
                        <div className="flex items-center gap-3">
                          <span className={`inline-flex h-5 w-5 items-center justify-center rounded-full text-xs ${item.status === "error" ? "bg-red-500 text-white" : "bg-green-500 text-white"}`}>
                            {item.status === "error" ? "!" : "✓"}
                          </span>
                          <span className="font-medium">{item.name}</span>
                        </div>
                      </td>
                      <td className="px-4 py-4">
                        <span className="inline-flex rounded-full bg-slate-200 px-2 py-1 text-sm text-slate-600">{item.namespace}</span>
                        <span className="ml-2 inline-flex rounded-full bg-slate-200 px-2 py-1 text-sm text-slate-600">{item.labels}</span>
                      </td>
                      <td className="px-4 py-4">{item.pods}</td>
                      <td className="px-4 py-4">{item.age}</td>
                      <td className="px-4 py-4">{item.image}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      );

    case "workloads":
      return (
        <div className="space-y-6">
          <h2 className="text-3xl font-semibold text-slate-700">Workloads</h2>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <table className="min-w-full text-left text-base">
              <thead className="bg-slate-100 text-slate-600">
                <tr>
                  <th className="px-4 py-3 font-medium">Name</th>
                  <th className="px-4 py-3 font-medium">Namespace</th>
                  <th className="px-4 py-3 font-medium">Pods</th>
                  <th className="px-4 py-3 font-medium">Age</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {workloads.map((item) => (
                  <tr key={item.name} className="border-t border-slate-200 text-slate-700">
                    <td className="px-4 py-3 font-medium">{item.name}</td>
                    <td className="px-4 py-3">{item.namespace}</td>
                    <td className="px-4 py-3">{item.pods}</td>
                    <td className="px-4 py-3">{item.age}</td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2 py-1 text-sm ${item.status === "error" ? "bg-red-100 text-red-700" : "bg-green-100 text-green-700"}`}>
                        {item.status === "error" ? "Error" : "Healthy"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      );

    case "deployments":
    case "pods":
    case "services":
    case "nodes":
      return (
        <CoreResourceView resource={resource} namespace={namespace} />
      );

    case "namespaces":
      return (
        <div className="space-y-6">
          <h2 className="text-3xl font-semibold text-slate-700">Namespaces</h2>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <table className="min-w-full text-left text-base">
              <thead className="bg-slate-100 text-slate-600">
                <tr>
                  <th className="px-4 py-3 font-medium">Name</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Pods</th>
                  <th className="px-4 py-3 font-medium">Age</th>
                </tr>
              </thead>
              <tbody>
                {namespaces.map((item) => (
                  <tr key={item.name} className="border-t border-slate-200 text-slate-700">
                    <td className="px-4 py-3 font-medium">{item.name}</td>
                    <td className="px-4 py-3">{item.status}</td>
                    <td className="px-4 py-3">{item.pods}</td>
                    <td className="px-4 py-3">{item.age}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      );

    default:
      return renderResource("overview", namespace);
  }
}

export default async function DashboardPage({
  searchParams,
}: {
  searchParams?: Promise<{ resource?: string; namespace?: string }> | { resource?: string; namespace?: string };
}) {
  const resolvedParams = await Promise.resolve(searchParams ?? {});
  const resource = resolvedParams.resource ?? "overview";
  const namespace = resolvedParams.namespace ?? "default";

  return <DashboardShell>{renderResource(resource, namespace)}</DashboardShell>;
}
