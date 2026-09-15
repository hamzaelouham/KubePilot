from time import monotonic
from typing import Annotated, Literal
from uuid import UUID

import json

from fastapi import APIRouter, Depends, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.background import BackgroundTask
from starlette.responses import StreamingResponse

from app.assistant.actions import decide, propose, summary
from app.assistant.api_adapter import read_tool
from app.assistant.observations import observe
from app.assistant.schemas import ChatCompletionsRequest, Decision, Observation, Proposal, ReadTool
from app.core.audit import record_audit
from app.core.config import Settings
from app.core.dependencies import AuthenticatedActor, get_current_actor, get_database_session, get_settings
from app.core.rbac import Permission, require_permission
from app.kubernetes.resource_management import ResourceManagementError
from app.models.entities import AssistantProposal
from app.services.ai_models import list_eligible_models
from app.services.ai_runtime import AIRuntimeError, MAX_INFERENCE_REQUEST_BYTES, open_chat_stream
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


@router.post("/inference/chat/completions")
async def chat_completions(
    request: Request,
    _actor: Actor,
    database: Database,
    settings: Configuration,
) -> StreamingResponse:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_INFERENCE_REQUEST_BYTES:
                raise ResourceManagementError(413, "ai_request_too_large", "The AI request is too large.")
        except ValueError as error:
            raise ResourceManagementError(422, "invalid_ai_request", "The AI request is invalid.") from error
    raw_body = await request.body()
    if len(raw_body) > MAX_INFERENCE_REQUEST_BYTES:
        raise ResourceManagementError(413, "ai_request_too_large", "The AI request is too large.")
    try:
        parsed = json.loads(raw_body)
        body = ChatCompletionsRequest.model_validate(parsed)
    except (json.JSONDecodeError, UnicodeDecodeError, ValidationError, TypeError) as error:
        raise ResourceManagementError(422, "invalid_ai_request", "The AI request is invalid.") from error
    try:
        stream, content_type = await open_chat_stream(
            database,
            settings,
            body.model_dump(exclude_none=True),
        )
    except AIRuntimeError as error:
        raise ResourceManagementError(error.status_code, error.code, str(error)) from error
    return StreamingResponse(
        stream,
        status_code=200,
        media_type=content_type,
        headers={"cache-control": "no-store", "x-content-type-options": "nosniff"},
        background=BackgroundTask(stream.aclose),
    )
