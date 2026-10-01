from collections.abc import Iterable

from app.core.rbac import Permission


PROPOSAL_ACTION_PERMISSIONS: dict[str, str] = {
    "scale": Permission.RESOURCES_UPDATE,
    "restart": Permission.RESOURCES_UPDATE,
    "delete": Permission.RESOURCES_DELETE,
    "install": Permission.MARKETPLACE_INSTALL,
    "upgrade": Permission.MARKETPLACE_RELEASE,
    "rollback": Permission.MARKETPLACE_RELEASE,
    "uninstall": Permission.MARKETPLACE_RELEASE,
}

PROPOSAL_TOOL_ACTIONS: dict[str, str] = {
    "proposeScale": "scale",
    "proposeRestart": "restart",
    "proposeDelete": "delete",
    "proposeInstall": "install",
    "proposeUpgrade": "upgrade",
    "proposeRollback": "rollback",
    "proposeUninstall": "uninstall",
}

TOOL_KINDS = frozenset({"read", "proposal"})


def proposal_permission(action: str) -> str:
    try:
        return PROPOSAL_ACTION_PERMISSIONS[action]
    except KeyError as error:
        raise ValueError("Unsupported assistant proposal action") from error


def validate_tool_catalog(definitions: Iterable[object]) -> None:
    seen: set[str] = set()
    proposal_ids: set[str] = set()
    for definition in definitions:
        tool_id = getattr(definition, "id", "")
        kind = getattr(definition, "kind", "")
        if not tool_id or tool_id in seen:
            raise ValueError("Assistant tool IDs must be unique and nonblank")
        if kind not in TOOL_KINDS:
            raise ValueError(f"Unsupported Assistant tool kind: {kind}")
        seen.add(tool_id)
        if kind == "proposal":
            if tool_id not in PROPOSAL_TOOL_ACTIONS:
                raise ValueError(f"Proposal tool has no approved action policy: {tool_id}")
            action = PROPOSAL_TOOL_ACTIONS[tool_id]
            if getattr(definition, "required_permission", "") != PROPOSAL_ACTION_PERMISSIONS[action]:
                raise ValueError(f"Proposal tool permission does not match action policy: {tool_id}")
            proposal_ids.add(tool_id)
        elif tool_id in PROPOSAL_TOOL_ACTIONS:
            raise ValueError(f"Proposal action tool must use proposal kind: {tool_id}")

    expected = set(PROPOSAL_TOOL_ACTIONS)
    if proposal_ids != expected:
        missing = ", ".join(sorted(expected - proposal_ids))
        extra = ", ".join(sorted(proposal_ids - expected))
        details = f"missing={missing}" if missing else f"unexpected={extra}"
        raise ValueError(f"Assistant proposal catalog is incomplete: {details}")
