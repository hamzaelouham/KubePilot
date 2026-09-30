import type { AgentDefinition, AgentModel, AgentTool } from "./agents";

export type AgentModelStateKey =
  | "missing"
  | "disabled"
  | "unavailable"
  | "conversational"
  | "ready";

export type AgentModelState = {
  key: AgentModelStateKey;
  label: string;
  description: string;
  canEnable: boolean;
  supportsTools: boolean;
};

export function getAgentModelState(model: AgentModel | null | undefined): AgentModelState {
  if (!model) {
    return {
      key: "missing",
      label: "Model not configured",
      description: "Choose an enabled model in Settings before enabling this agent.",
      canEnable: false,
      supportsTools: false,
    };
  }
  if (!model.enabled) {
    return {
      key: "disabled",
      label: "Model disabled",
      description: "This model is disabled in Settings. Choose an enabled model before enabling this agent.",
      canEnable: false,
      supportsTools: false,
    };
  }
  if (model.availability !== "available") {
    return {
      key: "unavailable",
      label: `Model ${model.availability}`,
      description: "The provider has not marked this model available. The agent can be edited but cannot be enabled with this model.",
      canEnable: false,
      supportsTools: false,
    };
  }
  if (!model.capabilities.tools) {
    return {
      key: "conversational",
      label: "Conversational model",
      description: "This model can answer in the Assistant but does not support Kubernetes tool calls.",
      canEnable: true,
      supportsTools: false,
    };
  }
  return {
    key: "ready",
    label: "Ready for tool-assisted runs",
    description: "This model is enabled, available, and supports the configured Kubernetes tools.",
    canEnable: true,
    supportsTools: true,
  };
}

type ToolGroupDefinition = {
  id: string;
  label: string;
  description: string;
  toolIds: string[];
};

const toolGroupDefinitions: ToolGroupDefinition[] = [
  {
    id: "workloads",
    label: "Workload inspection",
    description: "Clusters, namespaces, and workload status.",
    toolIds: ["listClusters", "listNamespaces", "listResources", "inspectResource"],
  },
  {
    id: "signals",
    label: "Logs, events, and metrics",
    description: "Evidence used to explain workload health.",
    toolIds: ["getPodLogs", "getEvents", "getResourceUsage"],
  },
  {
    id: "helm",
    label: "Helm and packages",
    description: "Release, repository, and package information.",
    toolIds: ["listHelmReleases", "getHelmHistory", "listRepositories", "searchPackages", "getPackage", "getJobStatus"],
  },
];

export type AgentToolGroup = ToolGroupDefinition & { tools: AgentTool[] };

export type AgentCapability = AgentDefinition["capabilities"][number];

export function getAgentToolStatus(capability: AgentCapability | undefined, model: AgentModel | null | undefined): string {
  if (!model) return "model_missing";
  if (!model.enabled || model.availability !== "available") return "model_unavailable";
  if (!model.capabilities.tools) return "model_no_tools";
  if (capability && !capability.actor_permitted) return "permission_denied";
  return capability ? "available" : "pending_check";
}

export function groupAgentTools(tools: AgentTool[]): AgentToolGroup[] {
  const knownIds = new Set(toolGroupDefinitions.flatMap(group => group.toolIds));
  const groups = toolGroupDefinitions
    .map(group => ({ ...group, tools: tools.filter(tool => group.toolIds.includes(tool.id)) }))
    .filter(group => group.tools.length > 0);
  const otherTools = tools.filter(tool => !knownIds.has(tool.id));
  if (otherTools.length > 0) {
    groups.push({
      id: "other",
      label: "Other capabilities",
      description: "Additional tools supplied by the current catalog.",
      toolIds: otherTools.map(tool => tool.id),
      tools: otherTools,
    });
  }
  return groups;
}

export function selectedToolCount(tools: AgentTool[], selectedIds: string[]): number {
  const selected = new Set(selectedIds);
  return tools.reduce((count, tool) => count + (selected.has(tool.id) ? 1 : 0), 0);
}

export function toolStatusLabel(status: string, selected: boolean): string {
  if (!selected) return "Not configured";
  return status.replaceAll("_", " ");
}
