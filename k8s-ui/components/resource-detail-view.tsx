"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { DashboardShell } from "@/components/dashboard-shell";

type DetailData = {
  cluster: string;
  resource_type: string;
  name: string;
  namespace: string | null;
  kind: string;
  status: string;
  metadata: Record<string, string>;
  source: string;
};

type YamlData = {
  content: string;
  truncated: boolean;
};

type LogData = {
  lines: string[];
  container: string | null;
  truncated: boolean;
};

type EventItem = {
  type: string;
  reason: string;
  message: string;
  source: string;
  created_at: string | null;
};

type EventData = {
  items: EventItem[];
  truncated: boolean;
};

type Tab = "status" | "yaml" | "logs" | "events";

type DetailState =
  | { status: "loading" }
  | { status: "ready"; data: DetailData }
  | { status: "error"; message: string };

type YamlState =
  | { status: "loading" }
  | { status: "ready"; data: YamlData }
  | { status: "error"; message: string };

type LogState =
  | { status: "loading" }
  | { status: "ready"; data: LogData }
  | { status: "error"; message: string };

type EventState =
  | { status: "loading" }
  | { status: "ready"; data: EventData }
  | { status: "error"; message: string };

function StatusPanel({ data }: { data: DetailData }) {
  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-slate-200 bg-white p-6">
        <h3 className="mb-4 text-lg font-semibold text-slate-700">Resource Information</h3>
        <dl className="grid grid-cols-2 gap-4">
          <div>
            <dt className="text-sm text-slate-500">Name</dt>
            <dd className="font-medium text-slate-700">{data.name}</dd>
          </div>
          <div>
            <dt className="text-sm text-slate-500">Kind</dt>
            <dd className="font-medium text-slate-700">{data.kind}</dd>
          </div>
          <div>
            <dt className="text-sm text-slate-500">Namespace</dt>
            <dd className="font-medium text-slate-700">{data.namespace ?? "Cluster-scoped"}</dd>
          </div>
          <div>
            <dt className="text-sm text-slate-500">Status</dt>
            <dd className="font-medium text-slate-700">{data.status}</dd>
          </div>
          <div>
            <dt className="text-sm text-slate-500">Cluster</dt>
            <dd className="font-medium text-slate-700">{data.cluster}</dd>
          </div>
          <div>
            <dt className="text-sm text-slate-500">Source</dt>
            <dd className="font-medium text-slate-700">{data.source}</dd>
          </div>
        </dl>
      </div>

      {Object.keys(data.metadata).length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-6">
          <h3 className="mb-4 text-lg font-semibold text-slate-700">Labels & Annotations</h3>
          <dl className="space-y-2">
            {Object.entries(data.metadata).map(([key, value]) => (
              <div key={key} className="flex justify-between border-b border-slate-100 py-2">
                <dt className="text-sm text-slate-500">{key}</dt>
                <dd className="font-mono text-sm text-slate-700">{value}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </div>
  );
}

function YamlPanel({ state }: { state: YamlState }) {
  if (state.status === "loading") {
    return <p className="rounded-lg bg-slate-100 p-5 text-slate-500">Loading YAML...</p>;
  }
  if (state.status === "error") {
    return <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-5 text-red-700">{state.message}</p>;
  }
  return (
    <div className="space-y-4">
      {state.data.truncated && (
        <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-700">
          YAML output was truncated due to size limits.
        </p>
      )}
      <div className="rounded-xl border border-slate-200 bg-white">
        <pre className="overflow-x-auto p-6 font-mono text-sm text-slate-700">{state.data.content}</pre>
      </div>
    </div>
  );
}

function LogsPanel({ state }: { state: LogState }) {
  if (state.status === "loading") {
    return <p className="rounded-lg bg-slate-100 p-5 text-slate-500">Loading logs...</p>;
  }
  if (state.status === "error") {
    return <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-5 text-red-700">{state.message}</p>;
  }
  if (state.data.lines.length === 0) {
    return <p className="rounded-lg bg-slate-100 p-5 text-slate-500">No logs available for this resource.</p>;
  }
  return (
    <div className="space-y-4">
      {state.data.container && (
        <p className="text-sm text-slate-500">Container: {state.data.container}</p>
      )}
      {state.data.truncated && (
        <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-700">
          Logs were truncated due to size limits.
        </p>
      )}
      <div className="rounded-xl border border-slate-200 bg-white">
        <pre className="overflow-x-auto p-6 font-mono text-sm text-slate-700 whitespace-pre-wrap">
          {state.data.lines.join("\n")}
        </pre>
      </div>
    </div>
  );
}

function EventsPanel({ state }: { state: EventState }) {
  if (state.status === "loading") {
    return <p className="rounded-lg bg-slate-100 p-5 text-slate-500">Loading events...</p>;
  }
  if (state.status === "error") {
    return <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-5 text-red-700">{state.message}</p>;
  }
  if (state.data.items.length === 0) {
    return <p className="rounded-lg bg-slate-100 p-5 text-slate-500">No events found for this resource.</p>;
  }
  return (
    <div className="space-y-4">
      {state.data.truncated && (
        <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-700">
          Events were truncated. Showing most recent entries.
        </p>
      )}
      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="min-w-full text-left text-base">
          <thead className="bg-slate-100 text-slate-600">
            <tr>
              <th className="px-4 py-3 font-medium">Type</th>
              <th className="px-4 py-3 font-medium">Reason</th>
              <th className="px-4 py-3 font-medium">Message</th>
              <th className="px-4 py-3 font-medium">Source</th>
              <th className="px-4 py-3 font-medium">Time</th>
            </tr>
          </thead>
          <tbody>
            {state.data.items.map((item, index) => (
              <tr key={index} className="border-t border-slate-200 text-slate-700">
                <td className="px-4 py-3">
                  <span className={`rounded-full px-2 py-1 text-xs font-medium ${
                    item.type === "Warning" ? "bg-amber-100 text-amber-700" : "bg-green-100 text-green-700"
                  }`}>
                    {item.type}
                  </span>
                </td>
                <td className="px-4 py-3 font-medium">{item.reason}</td>
                <td className="px-4 py-3 max-w-md truncate">{item.message}</td>
                <td className="px-4 py-3">{item.source}</td>
                <td className="px-4 py-3 text-sm text-slate-500">{item.created_at ?? "Unknown"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function ResourceDetailView({
  resourceType,
  name,
  namespace,
}: {
  resourceType: string;
  name: string;
  namespace: string | null;
}) {

  const [activeTab, setActiveTab] = useState<Tab>("status");
  const [detailState, setDetailState] = useState<DetailState>({ status: "loading" });
  const [yamlState, setYamlState] = useState<YamlState>({ status: "loading" });
  const [logState, setLogState] = useState<LogState>({ status: "loading" });
  const [eventState, setEventState] = useState<EventState>({ status: "loading" });
  const router = useRouter();

  const handleNav = (resource: string, ns: string) => {
    const params = new URLSearchParams({ resource, namespace: ns });
    router.push(`/dashboard?${params.toString()}`);
  };

  useEffect(() => {
    if (!name) return;

    const controller = new AbortController();
    setDetailState({ status: "loading" });

    const params = new URLSearchParams({ tab: "detail" });
    if (namespace) params.set("namespace", namespace);

    fetch(`/api/cluster/details/${resourceType}/${encodeURIComponent(name)}?${params}`, {
      signal: controller.signal,
      cache: "no-store",
    })
      .then(async (response) => {
        const body = (await response.json()) as DetailData & { message?: string };
        if (!response.ok) throw new Error(body.message ?? "Unable to load resource details");
        setDetailState({ status: "ready", data: body });
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setDetailState({ status: "error", message: error instanceof Error ? error.message : "Unable to load resource details" });
      });

    return () => controller.abort();
  }, [resourceType, name, namespace]);

  useEffect(() => {
    if (!name || activeTab !== "yaml") return;

    const controller = new AbortController();
    setYamlState({ status: "loading" });

    const params = new URLSearchParams({ tab: "yaml" });
    if (namespace) params.set("namespace", namespace);

    fetch(`/api/cluster/details/${resourceType}/${encodeURIComponent(name)}?${params}`, {
      signal: controller.signal,
      cache: "no-store",
    })
      .then(async (response) => {
        const body = (await response.json()) as YamlData & { message?: string };
        if (!response.ok) throw new Error(body.message ?? "Unable to load YAML");
        setYamlState({ status: "ready", data: body });
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setYamlState({ status: "error", message: error instanceof Error ? error.message : "Unable to load YAML" });
      });

    return () => controller.abort();
  }, [activeTab, resourceType, name, namespace]);

  useEffect(() => {
    if (!name || activeTab !== "logs") return;

    const controller = new AbortController();
    setLogState({ status: "loading" });

    const params = new URLSearchParams({ tab: "logs" });
    if (namespace) params.set("namespace", namespace);

    fetch(`/api/cluster/details/${resourceType}/${encodeURIComponent(name)}?${params}`, {
      signal: controller.signal,
      cache: "no-store",
    })
      .then(async (response) => {
        const body = (await response.json()) as LogData & { message?: string };
        if (!response.ok) throw new Error(body.message ?? "Unable to load logs");
        setLogState({ status: "ready", data: body });
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setLogState({ status: "error", message: error instanceof Error ? error.message : "Unable to load logs" });
      });

    return () => controller.abort();
  }, [activeTab, resourceType, name, namespace]);

  useEffect(() => {
    if (!name || activeTab !== "events") return;

    const controller = new AbortController();
    setEventState({ status: "loading" });

    const params = new URLSearchParams({ tab: "events" });
    if (namespace) params.set("namespace", namespace);

    fetch(`/api/cluster/details/${resourceType}/${encodeURIComponent(name)}?${params}`, {
      signal: controller.signal,
      cache: "no-store",
    })
      .then(async (response) => {
        const body = (await response.json()) as EventData & { message?: string };
        if (!response.ok) throw new Error(body.message ?? "Unable to load events");
        setEventState({ status: "ready", data: body });
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setEventState({ status: "error", message: error instanceof Error ? error.message : "Unable to load events" });
      });

    return () => controller.abort();
  }, [activeTab, resourceType, name, namespace]);

  const tabs: { id: Tab; label: string }[] = [
    { id: "status", label: "Status" },
    { id: "yaml", label: "YAML" },
    { id: "logs", label: "Logs" },
    { id: "events", label: "Events" },
  ];

  if (!name) {
    return (
      <DashboardShell
        activeResource={resourceType}
        activeNamespace={namespace ?? ""}
        onNavigate={handleNav}
      >
        <div className="space-y-6">
          <Link href="/dashboard?resource=pods" className="text-sm text-cyan-600 hover:underline">
            ← Back to resources
          </Link>
          <p className="rounded-lg border border-red-200 bg-red-50 p-5 text-red-700">
            No resource name provided. Please select a resource from the list.
          </p>
        </div>
      </DashboardShell>
    );
  }

  return (
    <DashboardShell
      activeResource={resourceType}
      activeNamespace={namespace ?? ""}
      onNavigate={handleNav}
    >
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link
          href={`/dashboard?resource=${resourceType}${namespace ? `&namespace=${namespace}` : ""}`}
          className="text-sm text-cyan-600 hover:underline"
        >
          ← Back to {resourceType}
        </Link>
        {detailState.status === "ready" && (
          <span className="rounded-full bg-cyan-100 px-3 py-1 text-sm font-medium text-cyan-800">
            {detailState.data.kind}
          </span>
        )}
      </div>

      <div>
        <p className="text-sm font-medium uppercase tracking-[0.2em] text-slate-400">Resource details</p>
        <h2 className="text-3xl font-semibold text-slate-700">
          {name}
          {namespace && <span className="ml-2 text-lg text-slate-500">({namespace})</span>}
        </h2>
      </div>

      <div className="flex gap-1 rounded-lg border border-slate-200 bg-slate-100 p-1">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 rounded-md px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === tab.id
                ? "bg-white text-slate-700 shadow-sm"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="mt-6">
        {activeTab === "status" && (
          detailState.status === "loading" ? (
            <p className="rounded-lg bg-slate-100 p-5 text-slate-500">Loading status...</p>
          ) : detailState.status === "error" ? (
            <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-5 text-red-700">{detailState.message}</p>
          ) : (
            <StatusPanel data={detailState.data} />
          )
        )}
        {activeTab === "yaml" && <YamlPanel state={yamlState} />}
        {activeTab === "logs" && <LogsPanel state={logState} />}
        {activeTab === "events" && <EventsPanel state={eventState} />}
      </div>
    </div>
    </DashboardShell>
  );
}
