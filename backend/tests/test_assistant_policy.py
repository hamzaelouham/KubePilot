import asyncio
from dataclasses import replace
from types import SimpleNamespace

import pytest

from app.assistant.actions import authorize, execute
from app.assistant.catalog import TOOL_DEFINITIONS
from app.assistant.policy import PROPOSAL_TOOL_ACTIONS, proposal_permission, validate_tool_catalog
from app.kubernetes.resource_management import ResourceManagementError


def test_assistant_catalog_requires_policy_backed_proposal_tools():
    proposal_ids = {definition.id for definition in TOOL_DEFINITIONS if definition.kind == "proposal"}
    assert proposal_ids == set(PROPOSAL_TOOL_ACTIONS)
    assert all(proposal_permission(action) for action in PROPOSAL_TOOL_ACTIONS.values())
    validate_tool_catalog(TOOL_DEFINITIONS)

    with pytest.raises(ValueError, match="Unsupported assistant proposal action"):
        proposal_permission("execute")

    invalid_kind = list(TOOL_DEFINITIONS) + [
        type(TOOL_DEFINITIONS[0])("unsafe", "Unsafe", "Unsafe", "write", "resources:update"),
    ]
    with pytest.raises(ValueError, match="Unsupported Assistant tool kind"):
        validate_tool_catalog(invalid_kind)

    invalid_permission = [
        replace(definition, required_permission="resources:delete")
        if definition.id == "proposeScale" else definition
        for definition in TOOL_DEFINITIONS
    ]
    with pytest.raises(ValueError, match="permission does not match"):
        validate_tool_catalog(invalid_permission)


def test_authorize_rejects_an_unregistered_side_effect():
    actor = SimpleNamespace(restricted=False, role="operator")
    body = SimpleNamespace(action="execute")

    with pytest.raises(ResourceManagementError, match="not available for approval"):
        authorize(actor, body)


def test_execute_rejects_an_unregistered_side_effect_before_external_access():
    body = SimpleNamespace(action="execute")

    with pytest.raises(ResourceManagementError, match="not available for approval"):
        asyncio.run(execute(None, None, body, {}))
