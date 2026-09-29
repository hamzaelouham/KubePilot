import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.v1.agent_schemas import AgentDeleted, AgentItem, AgentList, AgentWrite
from app.core.dependencies import AuthenticatedActor, get_database_session
from app.core.rbac import Permission, require_permission
from app.services.agents import delete_agent, list_agents, read_agent, save_agent

router = APIRouter(prefix="/assistant/agents", tags=["agents"])
Reader = Annotated[AuthenticatedActor, Depends(require_permission(Permission.RESOURCES_READ))]
Writer = Annotated[AuthenticatedActor, Depends(require_permission(Permission.SETTINGS_WRITE))]
Database = Annotated[Session, Depends(get_database_session)]


async def agent_body(request: Request) -> AgentWrite:
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > 256_000:
            raise HTTPException(413, detail={"code": "request_too_large", "message": "Agent configuration is too large."})
    try:
        return AgentWrite.model_validate(json.loads(content))
    except (ValidationError, ValueError, UnicodeDecodeError):
        raise HTTPException(422, detail={"code": "validation_error", "message": "Check the agent fields and selected model."}) from None


@router.get("", response_model=AgentList)
def listing(actor: Reader, database: Database):
    return {"agents": list_agents(database)}


@router.get("/{agent_id}", response_model=AgentItem)
def detail(agent_id: UUID, actor: Reader, database: Database):
    return read_agent(database, agent_id)


@router.post("", response_model=AgentItem, status_code=201)
def create(actor: Writer, database: Database, body: Annotated[AgentWrite, Depends(agent_body)]):
    return save_agent(database, actor.user_id, body)


@router.put("/{agent_id}", response_model=AgentItem)
def update(agent_id: UUID, actor: Writer, database: Database, body: Annotated[AgentWrite, Depends(agent_body)]):
    return save_agent(database, actor.user_id, body, agent_id)


@router.delete("/{agent_id}", response_model=AgentDeleted)
def delete(agent_id: UUID, actor: Writer, database: Database):
    return delete_agent(database, actor.user_id, agent_id)
