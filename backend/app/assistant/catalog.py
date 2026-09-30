from dataclasses import dataclass

from app.core.rbac import Permission


@dataclass(frozen=True)
class AssistantToolDefinition:
    id: str
    label: str
    description: str
    kind: str
    required_permission: str


TOOL_DEFINITIONS: tuple[AssistantToolDefinition, ...] = (
    AssistantToolDefinition("listClusters", "List clusters", "Read registered cluster names and status.", "read", Permission.CLUSTERS_READ),
    AssistantToolDefinition("listNamespaces", "List namespaces", "Discover namespaces in the selected cluster.", "read", Permission.RESOURCES_READ),
    AssistantToolDefinition("listResources", "List resources", "Read bounded resource inventory and safe status.", "read", Permission.RESOURCES_READ),
    AssistantToolDefinition("inspectResource", "Inspect resources", "Read resource conditions, ownership, and status details.", "read", Permission.RESOURCES_READ),
    AssistantToolDefinition("getPodLogs", "Read Pod logs", "Read a bounded, credential-scrubbed Pod log excerpt.", "read", Permission.RESOURCES_READ),
    AssistantToolDefinition("getEvents", "Read events", "Read namespace events and warning evidence.", "read", Permission.RESOURCES_READ),
    AssistantToolDefinition("getResourceUsage", "Read resource usage", "Read node and namespace metrics when available.", "read", Permission.RESOURCES_READ),
    AssistantToolDefinition("listHelmReleases", "List Helm releases", "Read live Helm releases in the selected cluster.", "read", Permission.RESOURCES_READ),
    AssistantToolDefinition("getHelmHistory", "Read Helm history", "Read revisions for a Helm release.", "read", Permission.RESOURCES_READ),
    AssistantToolDefinition("listRepositories", "List repositories", "Read configured public Helm repositories.", "read", Permission.RESOURCES_READ),
    AssistantToolDefinition("searchPackages", "Search packages", "Search verified Helm packages on Artifact Hub.", "read", Permission.RESOURCES_READ),
    AssistantToolDefinition("getPackage", "Read package details", "Read verified package identity and chart versions.", "read", Permission.RESOURCES_READ),
    AssistantToolDefinition("getJobStatus", "Read job status", "Read an installation or release-action job status.", "read", Permission.RESOURCES_READ),
    AssistantToolDefinition("proposeScale", "Propose a scale", "Create a scale proposal for authenticated review.", "proposal", Permission.RESOURCES_UPDATE),
    AssistantToolDefinition("proposeRestart", "Propose a restart", "Create a restart proposal for authenticated review.", "proposal", Permission.RESOURCES_UPDATE),
    AssistantToolDefinition("proposeDelete", "Propose a deletion", "Create a deletion proposal for authenticated review.", "proposal", Permission.RESOURCES_DELETE),
    AssistantToolDefinition("proposeInstall", "Propose an install", "Create a Helm installation proposal for authenticated review.", "proposal", Permission.MARKETPLACE_INSTALL),
    AssistantToolDefinition("proposeUpgrade", "Propose an upgrade", "Create a Helm upgrade proposal for authenticated review.", "proposal", Permission.MARKETPLACE_RELEASE),
    AssistantToolDefinition("proposeRollback", "Propose a rollback", "Create a Helm rollback proposal for authenticated review.", "proposal", Permission.MARKETPLACE_RELEASE),
    AssistantToolDefinition("proposeUninstall", "Propose an uninstall", "Create a Helm uninstall proposal for authenticated review.", "proposal", Permission.MARKETPLACE_RELEASE),
)

TOOL_BY_ID = {definition.id: definition for definition in TOOL_DEFINITIONS}


def tool_catalog() -> list[dict[str, str]]:
    return [definition.__dict__.copy() for definition in TOOL_DEFINITIONS]
