from time import monotonic
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.assistant.actions import decide, propose, summary
from app.assistant.api_adapter import read_tool
from app.assistant.observations import observe
from app.assistant.schemas import Decision, Observation, Proposal, ReadTool
from app.core.audit import record_audit
from app.core.config import Settings
from app.core.dependencies import AuthenticatedActor, get_current_actor, get_database_session, get_settings
from app.core.rbac import Permission, require_permission
from app.kubernetes.resource_management import ResourceManagementError
from app.models.entities import AssistantProposal
from app.services.ai_models import list_eligible_models
from app.api.v1.settings_schemas import EligibleModelsResponse

router = APIRouter(prefix="/assistant", tags=["assistant"])
Actor = Annotated[AuthenticatedActor, Depends(require_permission(Permission.RESOURCES_READ))]
Database = Annotated[Session, Depends(get_database_session)]
Configuration = Annotated[Settings, Depends(get_settings)]
Authenticated = Annotated[AuthenticatedActor, Depends(get_current_actor)]


async def audited(database, actor, tool, cluster, operation):
    start = monotonic()
    outcome = "failed"
    try:
        result = await operation()
        outcome = "success"
        return result
    finally:
        record_audit(database, "assistant.tool", actor.user_id, "assistant_tool", tool, result=outcome, context={"cluster": cluster, "duration_ms": round((monotonic() - start) * 1000)})
        database.commit()


@router.post("/observe/{operation}")
async def observation(operation: Literal["list", "inspect", "events", "logs"], body: Observation, actor: Actor, database: Database):
    return await audited(database, actor, operation, body.cluster, lambda: run_in_threadpool(observe, database, operation, body))


@router.post("/read")
async def read(body: ReadTool, request: Request, actor: Actor, database: Database):
    return await audited(database, actor, body.tool, body.cluster, lambda: read_tool(request, database, body))


@router.post("/proposals", status_code=201)
async def proposal(body: Proposal, request: Request, actor: Actor, database: Database, settings: Configuration):
    return await propose(request, database, settings, actor, body)


@router.post("/proposals/{proposal_id}/decision")
async def decision(proposal_id: UUID, body: Decision, request: Request, actor: Actor, database: Database, settings: Configuration):
    return await decide(request, database, settings, actor, proposal_id, body)


@router.get("/proposals/{proposal_id}")
def get_proposal(proposal_id: UUID, actor: Actor, database: Database):
    proposal = database.get(AssistantProposal, proposal_id)
    if proposal is None or proposal.actor_id != actor.user_id or proposal.session_id != actor.session_id:
        raise ResourceManagementError(404, "proposal_not_found", "Proposal not found for this session")
    return summary(proposal)


@router.get("/models", response_model=EligibleModelsResponse)
def eligible_models(_actor: Authenticated, database: Database) -> EligibleModelsResponse:
    return EligibleModelsResponse(models=list_eligible_models(database))
