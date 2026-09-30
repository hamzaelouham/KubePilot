import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.agent_schemas import (
    AgentDeleted,
    AgentItem,
    AgentList,
    AgentNotificationDestinationItem,
    AgentNotificationDestinationList,
    AgentNotificationDestinationWrite,
    AgentSkillDeleted,
    AgentSkillItem,
    AgentSkillList,
    AgentSkillWrite,
    AgentTemplateList,
    AgentToolList,
    AgentWrite,
)
from app.core.config import Settings
from app.core.dependencies import AuthenticatedActor, get_database_session, get_settings
from app.core.rbac import Permission, require_permission
from app.api.v1.integration_schemas import IntegrationDeliveryItem
from app.assistant.catalog import tool_catalog
from app.assistant.templates import template_catalog
from app.models.entities import AIAgentSkillAssignment
from app.services.agent_notifications import (
    delete_destination,
    list_destinations,
    queue_test_delivery,
    save_destination,
)
from app.services.integration_delivery import DeliveryServiceError
from app.services.agents import (
    delete_agent,
    delete_skill,
    get_skill,
    list_agents,
    list_skills,
    read_agent,
    save_agent,
    save_skill,
    skill_summary,
)

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


async def skill_body(request: Request) -> AgentSkillWrite:
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > 256_000:
            raise HTTPException(413, detail={"code": "request_too_large", "message": "Skill configuration is too large."})
    try:
        return AgentSkillWrite.model_validate(json.loads(content))
    except (ValidationError, ValueError, UnicodeDecodeError):
        raise HTTPException(422, detail={"code": "validation_error", "message": "Check the skill fields."}) from None


async def notification_body(request: Request) -> AgentNotificationDestinationWrite:
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > 32_000:
            raise HTTPException(413, detail={"code": "request_too_large", "message": "Notification configuration is too large."})
    try:
        return AgentNotificationDestinationWrite.model_validate(json.loads(content))
    except (ValidationError, ValueError, UnicodeDecodeError):
        raise HTTPException(422, detail={"code": "validation_error", "message": "Check the notification destination fields."}) from None


@router.get("/skills", response_model=AgentSkillList)
def skills(actor: Reader, database: Database):
    return {"skills": list_skills(database)}


@router.post("/skills", response_model=AgentSkillItem, status_code=201)
def create_skill(actor: Writer, database: Database, body: Annotated[AgentSkillWrite, Depends(skill_body)]):
    return save_skill(database, actor.user_id, body)


@router.get("/skills/{skill_id}", response_model=AgentSkillItem)
def skill_detail(skill_id: UUID, actor: Reader, database: Database):
    row = get_skill(database, skill_id)
    assigned = database.scalar(
        select(func.count())
        .select_from(AIAgentSkillAssignment)
        .where(AIAgentSkillAssignment.skill_id == skill_id)
    )
    return skill_summary(row, assigned or 0)


@router.put("/skills/{skill_id}", response_model=AgentSkillItem)
def update_skill(skill_id: UUID, actor: Writer, database: Database, body: Annotated[AgentSkillWrite, Depends(skill_body)]):
    return save_skill(database, actor.user_id, body, skill_id)


@router.delete("/skills/{skill_id}", response_model=AgentSkillDeleted)
def remove_skill(skill_id: UUID, actor: Writer, database: Database):
    return delete_skill(database, actor.user_id, skill_id)


@router.get("/tools", response_model=AgentToolList)
def tools(actor: Reader):
    return {"tools": tool_catalog()}


@router.get("/templates", response_model=AgentTemplateList)
def templates(actor: Reader):
    return {"templates": template_catalog()}


@router.get("/{agent_id}/notifications", response_model=AgentNotificationDestinationList)
def notification_destinations(agent_id: UUID, actor: Reader, database: Database):
    return {"destinations": [AgentNotificationDestinationItem(**item) for item in list_destinations(database, agent_id)]}


@router.post("/{agent_id}/notifications", response_model=AgentNotificationDestinationItem, status_code=201)
def create_notification_destination(
    agent_id: UUID,
    actor: Writer,
    database: Database,
    settings: Annotated[Settings, Depends(get_settings)],
    body: Annotated[AgentNotificationDestinationWrite, Depends(notification_body)],
):
    return AgentNotificationDestinationItem(
        **save_destination(database, settings, actor.user_id, agent_id, body)
    )


@router.put("/{agent_id}/notifications/{destination_id}", response_model=AgentNotificationDestinationItem)
def update_notification_destination(
    agent_id: UUID,
    destination_id: UUID,
    actor: Writer,
    database: Database,
    settings: Annotated[Settings, Depends(get_settings)],
    body: Annotated[AgentNotificationDestinationWrite, Depends(notification_body)],
):
    return AgentNotificationDestinationItem(
        **save_destination(database, settings, actor.user_id, agent_id, body, destination_id)
    )


@router.delete("/{agent_id}/notifications/{destination_id}", response_model=AgentDeleted)
def remove_notification_destination(agent_id: UUID, destination_id: UUID, actor: Writer, database: Database):
    return delete_destination(database, actor.user_id, agent_id, destination_id)


@router.post("/{agent_id}/notifications/{destination_id}/test", response_model=IntegrationDeliveryItem)
def test_notification_destination(
    agent_id: UUID,
    destination_id: UUID,
    actor: Writer,
    database: Database,
    settings: Annotated[Settings, Depends(get_settings)],
):
    try:
        return IntegrationDeliveryItem(
            **queue_test_delivery(database, settings, actor.user_id, agent_id, destination_id)
        )
    except DeliveryServiceError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail={"code": error.code, "message": str(error)},
        ) from error


@router.get("", response_model=AgentList)
def listing(actor: Reader, database: Database):
    return {"agents": list_agents(database, actor.role)}


@router.get("/{agent_id}", response_model=AgentItem)
def detail(agent_id: UUID, actor: Reader, database: Database):
    return read_agent(database, agent_id, actor.role)


@router.post("", response_model=AgentItem, status_code=201)
def create(actor: Writer, database: Database, body: Annotated[AgentWrite, Depends(agent_body)]):
    return save_agent(database, actor.user_id, body, role=actor.role)


@router.put("/{agent_id}", response_model=AgentItem)
def update(agent_id: UUID, actor: Writer, database: Database, body: Annotated[AgentWrite, Depends(agent_body)]):
    return save_agent(database, actor.user_id, body, agent_id, actor.role)


@router.delete("/{agent_id}", response_model=AgentDeleted)
def delete(agent_id: UUID, actor: Writer, database: Database):
    return delete_agent(database, actor.user_id, agent_id)
