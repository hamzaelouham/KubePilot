from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.agent_schemas import AgentWrite
from app.assistant.catalog import TOOL_BY_ID, AssistantToolDefinition
from app.core.audit import record_audit
from app.core.rbac import has_permission
from app.models.entities import AIAgent, AIAgentSkill, AIAgentSkillAssignment, AIAgentToolAssignment, AIModelConfig
from app.services.ai_models import list_models


def fail(status: int, code: str, message: str):
    raise HTTPException(status, detail={"code": code, "message": message})


def skill_summary(row: AIAgentSkill, assigned_agent_count: int = 0):
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description,
        "instructions": row.instructions,
        "created_by_id": row.created_by_id,
        "updated_by_id": row.updated_by_id,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "assigned_agent_count": assigned_agent_count,
    }


def list_skills(database: Session):
    counts = dict(
        database.execute(
            select(AIAgentSkillAssignment.skill_id, func.count(AIAgentSkillAssignment.agent_id))
            .group_by(AIAgentSkillAssignment.skill_id)
        ).all()
    )
    return [
        skill_summary(row, counts.get(row.id, 0))
        for row in database.scalars(select(AIAgentSkill).order_by(AIAgentSkill.name, AIAgentSkill.id))
    ]


def get_skill(database: Session, identity: UUID) -> AIAgentSkill:
    row = database.get(AIAgentSkill, identity)
    if row is None:
        fail(404, "skill_not_found", "This skill no longer exists. Refresh the skill list.")
    return row


def save_skill(database: Session, actor_id: UUID, body, identity: UUID | None = None):
    row = get_skill(database, identity) if identity else None
    try:
        if row is None:
            row = AIAgentSkill(created_by_id=actor_id)
            database.add(row)
        for key, value in body.model_dump().items():
            setattr(row, key, value)
        row.updated_by_id = actor_id
        row.updated_at = datetime.now(timezone.utc)
        database.flush()
        record_audit(
            database,
            "assistant.agent_skill.update" if identity else "assistant.agent_skill.create",
            actor_id,
            "ai_agent_skill",
            str(row.id),
            result="succeeded",
        )
        database.commit()
        database.refresh(row)
    except IntegrityError:
        database.rollback()
        fail(409, "skill_conflict", "The skill name is already in use. Refresh and try again.")
    except Exception:
        database.rollback()
        raise
    return skill_summary(row)


def delete_skill(database: Session, actor_id: UUID, identity: UUID):
    row = get_skill(database, identity)
    if database.scalar(
        select(func.count())
        .select_from(AIAgentSkillAssignment)
        .where(AIAgentSkillAssignment.skill_id == identity)
    ):
        fail(409, "skill_in_use", "Remove this skill from its agents before deleting it.")
    try:
        database.delete(row)
        record_audit(database, "assistant.agent_skill.delete", actor_id, "ai_agent_skill", str(identity), result="succeeded")
        database.commit()
    except Exception:
        database.rollback()
        raise
    return {"id": identity}


def get_agent(database: Session, identity: UUID) -> AIAgent:
    row = database.get(AIAgent, identity)
    if row is None:
        fail(404, "agent_not_found", "This agent no longer exists. Refresh the agent list.")
    return row


def _skill_references(database: Session, identity: UUID):
    return [
        {
            "id": skill.id,
            "name": skill.name,
            "description": skill.description,
            "instructions": skill.instructions,
        }
        for _, skill in database.execute(
            select(AIAgentSkillAssignment, AIAgentSkill)
            .join(AIAgentSkill, AIAgentSkill.id == AIAgentSkillAssignment.skill_id)
            .where(AIAgentSkillAssignment.agent_id == identity)
            .order_by(AIAgentSkillAssignment.position, AIAgentSkill.name, AIAgentSkill.id)
        ).all()
    ]


def _tool_ids(database: Session, identity: UUID):
    return [
        row.tool_id
        for row in database.scalars(
            select(AIAgentToolAssignment)
            .where(AIAgentToolAssignment.agent_id == identity)
            .order_by(AIAgentToolAssignment.tool_id)
        )
    ]


def _capabilities(tool_ids: list[str], model: dict | None, role: str):
    model_supported = bool(model and model.get("enabled") and model.get("availability") == "available" and model.get("capabilities", {}).get("tools"))
    result = []
    for definition in TOOL_BY_ID.values():
        configured = definition.id in tool_ids
        actor_permitted = has_permission(role, definition.required_permission)
        if not configured:
            status = "not_configured"
        elif model is None:
            status = "model_missing"
        elif not model.get("enabled") or model.get("availability") != "available":
            status = "model_unavailable"
        elif not model.get("capabilities", {}).get("tools"):
            status = "model_no_tools"
        elif not actor_permitted:
            status = "permission_denied"
        else:
            status = "available"
        result.append({
            "id": definition.id,
            "label": definition.label,
            "description": definition.description,
            "kind": definition.kind,
            "required_permission": definition.required_permission,
            "configured": configured,
            "model_supported": model_supported,
            "actor_permitted": actor_permitted,
            "status": status,
        })
    return result


def summary(row: AIAgent, models: dict, database: Session, role: str):
    model = models.get(row.model_id)
    skills = _skill_references(database, row.id)
    configured_tools = _tool_ids(database, row.id)
    return {field: getattr(row, field) for field in (
        "id", "name", "description", "instructions", "model_id", "enabled",
        "created_by_id", "updated_by_id", "created_at", "updated_at",
    )} | {
        "model": model,
        "skills": skills,
        "skill_ids": [item["id"] for item in skills],
        "tool_ids": configured_tools,
        "capabilities": _capabilities(configured_tools, model, role),
    }


def model_map(database: Session):
    return {item["id"]: item for item in list_models(database)}


def list_agents(database: Session, role: str):
    models = model_map(database)
    return [summary(row, models, database, role) for row in database.scalars(select(AIAgent).order_by(AIAgent.name, AIAgent.id))]


def read_agent(database: Session, identity: UUID, role: str):
    return summary(get_agent(database, identity), model_map(database), database, role)


def _validate_assignments(database: Session, body: AgentWrite):
    if len(body.skill_ids) != len(set(body.skill_ids)) or len(body.tool_ids) != len(set(body.tool_ids)):
        fail(422, "validation_error", "Assignments must not contain duplicates.")
    skills = list(database.scalars(select(AIAgentSkill).where(AIAgentSkill.id.in_(body.skill_ids)))) if body.skill_ids else []
    if len(skills) != len(body.skill_ids):
        fail(422, "validation_error", "Select existing skills.")
    if any(tool_id not in TOOL_BY_ID for tool_id in body.tool_ids):
        fail(422, "validation_error", "Select supported Assistant tools.")
    return skills


def _replace_assignments(database: Session, agent_id: UUID, body: AgentWrite, skills: list[AIAgentSkill]):
    database.execute(delete(AIAgentSkillAssignment).where(AIAgentSkillAssignment.agent_id == agent_id))
    database.execute(delete(AIAgentToolAssignment).where(AIAgentToolAssignment.agent_id == agent_id))
    skill_positions = {skill_id: position for position, skill_id in enumerate(body.skill_ids)}
    database.add_all([
        AIAgentSkillAssignment(agent_id=agent_id, skill_id=skill.id, position=skill_positions[skill.id])
        for skill in skills
    ])
    database.add_all([AIAgentToolAssignment(agent_id=agent_id, tool_id=tool_id) for tool_id in body.tool_ids])


def save_agent(database: Session, actor_id: UUID, body: AgentWrite, identity: UUID | None = None, role: str = "admin"):
    row = get_agent(database, identity) if identity else None
    skills = _validate_assignments(database, body)
    model = database.get(AIModelConfig, body.model_id) if body.model_id else None
    if body.model_id and model is None:
        fail(422, "validation_error", "Select an existing model from Settings.")
    if body.model_id is None and (row is None or row.model_id is not None or body.enabled):
        fail(422, "validation_error", "Select a model before enabling or creating this agent.")
    # An outage must not block editing an unchanged definition or disabling it.
    activating = body.enabled and (row is None or not row.enabled or row.model_id != body.model_id)
    if activating and (not model or not model.enabled or model.availability != "available"):
        fail(422, "validation_error", "Choose an enabled, available model before enabling the agent.")
    try:
        if row is None:
            row = AIAgent(created_by_id=actor_id)
            database.add(row)
        for key, value in body.model_dump().items():
            if key in {"skill_ids", "tool_ids"}:
                continue
            setattr(row, key, value)
        row.updated_by_id = actor_id
        row.updated_at = datetime.now(timezone.utc)
        database.flush()
        _replace_assignments(database, row.id, body, skills)
        record_audit(database, "assistant.agent.update" if identity else "assistant.agent.create",
                     actor_id, "ai_agent", str(row.id), result="succeeded",
                     context={"skill_count": len(body.skill_ids), "tool_count": len(body.tool_ids)})
        database.commit()
        database.refresh(row)
    except IntegrityError:
        database.rollback()
        fail(409, "agent_conflict", "The name is already in use or the selected model changed. Refresh and try again.")
    except Exception:
        database.rollback()
        raise
    return summary(row, model_map(database), database, role)


def delete_agent(database: Session, actor_id: UUID, identity: UUID):
    row = get_agent(database, identity)
    try:
        database.delete(row)
        record_audit(database, "assistant.agent.delete", actor_id, "ai_agent", str(identity), result="succeeded")
        database.commit()
    except Exception:
        database.rollback()
        raise
    return {"id": identity}
