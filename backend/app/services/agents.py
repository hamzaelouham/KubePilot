from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.agent_schemas import AgentWrite
from app.core.audit import record_audit
from app.models.entities import AIAgent, AIModelConfig
from app.services.ai_models import list_models


def fail(status: int, code: str, message: str):
    raise HTTPException(status, detail={"code": code, "message": message})


def get_agent(database: Session, identity: UUID) -> AIAgent:
    row = database.get(AIAgent, identity)
    if row is None:
        fail(404, "agent_not_found", "This agent no longer exists. Refresh the agent list.")
    return row


def summary(row: AIAgent, models: dict):
    return {field: getattr(row, field) for field in (
        "id", "name", "description", "instructions", "model_id", "enabled",
        "created_by_id", "updated_by_id", "created_at", "updated_at",
    )} | {"model": models.get(row.model_id)}


def model_map(database: Session):
    return {item["id"]: item for item in list_models(database)}


def list_agents(database: Session):
    models = model_map(database)
    return [summary(row, models) for row in database.scalars(select(AIAgent).order_by(AIAgent.name, AIAgent.id))]


def read_agent(database: Session, identity: UUID):
    return summary(get_agent(database, identity), model_map(database))


def save_agent(database: Session, actor_id: UUID, body: AgentWrite, identity: UUID | None = None):
    row = get_agent(database, identity) if identity else None
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
            setattr(row, key, value)
        row.updated_by_id = actor_id
        row.updated_at = datetime.now(timezone.utc)
        database.flush()
        record_audit(database, "assistant.agent.update" if identity else "assistant.agent.create",
                     actor_id, "ai_agent", str(row.id), result="succeeded")
        database.commit()
        database.refresh(row)
    except IntegrityError:
        database.rollback()
        fail(409, "agent_conflict", "The name is already in use or the selected model changed. Refresh and try again.")
    except Exception:
        database.rollback()
        raise
    return summary(row, model_map(database))


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
