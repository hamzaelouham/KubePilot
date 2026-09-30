from dataclasses import dataclass


@dataclass(frozen=True)
class AgentTemplateDefinition:
    id: str
    name: str
    description: str
    instructions: str
    tool_ids: tuple[str, ...]


AGENT_TEMPLATES: tuple[AgentTemplateDefinition, ...] = (
    AgentTemplateDefinition(
        "workload-investigator",
        "Workload investigator",
        "Trace workload health from status through events and bounded logs.",
        "Inspect the selected workload using live evidence. Separate observations from hypotheses, cite the resource scope, and identify the next safe check. Never claim a change was made.",
        ("listResources", "inspectResource", "getEvents", "getPodLogs", "getResourceUsage"),
    ),
    AgentTemplateDefinition(
        "cluster-observer",
        "Cluster observer",
        "Summarize selected-cluster health, namespaces, resources, and usage.",
        "Build a concise operational snapshot from live read-only evidence. Call out unavailable metrics or permissions instead of guessing, and keep all findings scoped to the selected cluster.",
        ("listClusters", "listNamespaces", "listResources", "getResourceUsage", "getEvents"),
    ),
    AgentTemplateDefinition(
        "helm-reviewer",
        "Helm release reviewer",
        "Inspect Helm releases, revisions, repositories, packages, and job state.",
        "Review Helm state using explicit release, repository, chart, and version identity. Treat queued or running jobs as incomplete and never imply that a release mutation occurred.",
        ("listHelmReleases", "getHelmHistory", "listRepositories", "searchPackages", "getPackage", "getJobStatus"),
    ),
)


def template_catalog() -> list[dict[str, object]]:
    return [
        {
            "id": template.id,
            "name": template.name,
            "description": template.description,
            "instructions": template.instructions,
            "tool_ids": list(template.tool_ids),
        }
        for template in AGENT_TEMPLATES
    ]


TEMPLATE_BY_ID = {template.id: template for template in AGENT_TEMPLATES}
