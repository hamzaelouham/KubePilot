import asyncio
from collections.abc import AsyncIterator
from time import monotonic
from typing import Annotated, Literal
from uuid import UUID

import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import ValidationError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.background import BackgroundTask
from starlette.responses import StreamingResponse

from app.assistant.actions import decide, propose, summary
from app.assistant.api_adapter import read_tool
from app.assistant.observations import observe
from app.assistant.schemas import ChatCompletionsRequest, Decision, Observation, Proposal, ReadTool
from app.core.audit import AuditEvent, record_audit
from app.core.config import Settings
from app.core.dependencies import AuthenticatedActor, get_database_session, get_settings
from app.core.rbac import Permission, has_permission, require_permission
from app.kubernetes.resource_management import ResourceManagementError
from app.models.entities import AssistantProposal
from app.services.ai_models import list_eligible_models
from app.services.ai_runtime import (
    AIRuntimeError,
    MAX_INFERENCE_REQUEST_BYTES,
    ProviderStream,
    RuntimeModel,
    open_chat_stream,
    resolve_runtime_model,
)
from app.api.v1.settings_schemas import EligibleModelsResponse
from app.api.v1.conversation_schemas import (
    ConversationCreateRequest,
    ConversationDetail,
    ConversationListResponse,
    ConversationPurgeResponse,
    ConversationRenameRequest,
    ConversationRetentionResponse,
    ConversationSaveRequest,
    ConversationSummary,
)
from app.services.assistant_conversations import (
    ConversationError,
    conversation_retention_days,
    create_conversation,
    delete_conversation,
    get_conversation,
    list_conversations,
    purge_expired_conversations,
    rename_conversation,
    save_conversation,
    set_conversation_retention,
)

router = APIRouter(prefix="/assistant", tags=["assistant"])
Actor = Annotated[AuthenticatedActor, Depends(require_permission(Permission.RESOURCES_READ))]
Database = Annotated[Session, Depends(get_database_session)]
Configuration = Annotated[Settings, Depends(get_settings)]
AdminReadActor = Annotated[AuthenticatedActor, Depends(require_permission(Permission.SETTINGS_READ))]
AdminWriteActor = Annotated[AuthenticatedActor, Depends(require_permission(Permission.SETTINGS_WRITE))]


def _conversation_http_error(error: ConversationError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail={"code": error.code, "message": str(error)})


async def audited(database, actor, tool, cluster, operation):
    start = monotonic()
    outcome = "failed"
    try:
        result = await operation()
        outcome = "success"
        return result
    except asyncio.CancelledError:
        outcome = "cancelled"
        raise
    finally:
        record_audit(database, AuditEvent.ASSISTANT_TOOL, actor.user_id, "assistant_tool", tool, result=outcome, context={"cluster": cluster, "duration_ms": round((monotonic() - start) * 1000)})
        database.commit()


def _record_inference_audit(
    database: Session,
    actor: AuthenticatedActor,
    requested_model: Literal["default"] | UUID,
    started_at: float,
    result: Literal["success", "failed", "cancelled"],
    runtime: RuntimeModel | None = None,
    error_code: str | None = None,
) -> None:
    context: dict[str, str | int] = {
        "tool_mode": "enabled" if runtime and runtime.supports_tools else "disabled" if runtime else "unknown",
        "duration_ms": round((monotonic() - started_at) * 1000),
    }
    if runtime is not None:
        context["provider_id"] = runtime.provider.provider_id
    if error_code is not None:
        context["error_code"] = error_code
    record_audit(
        database,
        AuditEvent.ASSISTANT_INFERENCE,
        actor.user_id,
        "ai_model",
        str(runtime.model_id if runtime is not None else requested_model),
        result=result,
        context=context,
    )
    database.commit()


class AuditedInferenceStream(AsyncIterator[bytes]):
    def __init__(
        self,
        stream: ProviderStream,
        database: Session,
        actor: AuthenticatedActor,
        requested_model: Literal["default"] | UUID,
        runtime: RuntimeModel,
        started_at: float,
    ) -> None:
        self._stream = stream
        self._database = database
        self._actor = actor
        self._requested_model = requested_model
        self._runtime = runtime
        self._started_at = started_at
        self._finalized = False

    def __aiter__(self) -> "AuditedInferenceStream":
        return self

    async def __anext__(self) -> bytes:
        try:
            return await self._stream.__anext__()
        except StopAsyncIteration:
            self._finalize("success")
            raise
        except asyncio.CancelledError:
            self._finalize("cancelled", "request_cancelled")
            raise
        except AIRuntimeError as error:
            self._finalize("failed", error.code)
            raise
        except Exception:
            self._finalize("failed", "ai_provider_stream_failed")
            raise

    async def aclose(self) -> None:
        if not self._finalized:
            self._finalize("cancelled", "request_cancelled")
        await self._stream.aclose()

    def _finalize(
        self,
        result: Literal["success", "failed", "cancelled"],
        error_code: str | None = None,
    ) -> None:
        if self._finalized:
            return
        self._finalized = True
        _record_inference_audit(
            self._database,
            self._actor,
            self._requested_model,
            self._started_at,
            result,
            self._runtime,
            error_code,
        )


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


@router.get("/conversations", response_model=ConversationListResponse)
def conversations(
    actor: Actor,
    database: Database,
    search: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ConversationListResponse:
    try:
        return list_conversations(
            database,
            actor.user_id,
            admin=has_permission(actor.role, Permission.SETTINGS_READ),
            search=search,
            limit=limit,
            offset=offset,
        )
    except ConversationError as error:
        raise _conversation_http_error(error) from error


@router.post("/conversations", response_model=ConversationDetail, status_code=201)
def create_conversation_route(body: ConversationCreateRequest, actor: Actor, database: Database) -> ConversationDetail:
    try:
        return create_conversation(database, actor.user_id, body)
    except ConversationError as error:
        raise _conversation_http_error(error) from error


@router.get("/conversations/retention", response_model=ConversationRetentionResponse)
def get_conversation_retention(actor: AdminReadActor, database: Database) -> ConversationRetentionResponse:
    value = conversation_retention_days(database)
    record_audit(database, AuditEvent.ASSISTANT_CONVERSATION_RETENTION_VIEWED, actor.user_id, "application_setting", "assistant.conversation_retention_days", result="succeeded")
    database.commit()
    return ConversationRetentionResponse(retention_days=value)


@router.put("/conversations/retention", response_model=ConversationRetentionResponse)
def update_conversation_retention(body: ConversationRetentionResponse, actor: AdminWriteActor, database: Database) -> ConversationRetentionResponse:
    try:
        return set_conversation_retention(database, actor.user_id, body.retention_days)
    except ConversationError as error:
        raise _conversation_http_error(error) from error


@router.post("/conversations/purge", response_model=ConversationPurgeResponse)
def purge_conversations(actor: AdminWriteActor, database: Database) -> ConversationPurgeResponse:
    return purge_expired_conversations(database, actor.user_id)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def conversation_detail(conversation_id: UUID, actor: Actor, database: Database) -> ConversationDetail:
    try:
        return get_conversation(
            database,
            actor.user_id,
            conversation_id,
            admin=has_permission(actor.role, Permission.SETTINGS_READ),
        )
    except ConversationError as error:
        raise _conversation_http_error(error) from error


@router.put("/conversations/{conversation_id}/messages", response_model=ConversationDetail)
def save_conversation_route(conversation_id: UUID, body: ConversationSaveRequest, actor: Actor, database: Database) -> ConversationDetail:
    try:
        return save_conversation(database, actor.user_id, conversation_id, body)
    except ConversationError as error:
        raise _conversation_http_error(error) from error


@router.patch("/conversations/{conversation_id}", response_model=ConversationSummary)
def rename_conversation_route(conversation_id: UUID, body: ConversationRenameRequest, actor: Actor, database: Database) -> ConversationSummary:
    try:
        return rename_conversation(
            database,
            actor.user_id,
            conversation_id,
            body,
            admin=has_permission(actor.role, Permission.SETTINGS_READ),
        )
    except ConversationError as error:
        raise _conversation_http_error(error) from error


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation_route(conversation_id: UUID, actor: Actor, database: Database) -> Response:
    try:
        delete_conversation(
            database,
            actor.user_id,
            conversation_id,
            admin=has_permission(actor.role, Permission.SETTINGS_READ),
        )
    except ConversationError as error:
        raise _conversation_http_error(error) from error
    return Response(status_code=204)


@router.get("/models", response_model=EligibleModelsResponse)
def eligible_models(_actor: Actor, database: Database) -> EligibleModelsResponse:
    return EligibleModelsResponse(models=list_eligible_models(database))


@router.post("/inference/chat/completions")
async def chat_completions(
    request: Request,
    actor: Actor,
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
    started_at = monotonic()
    runtime: RuntimeModel | None = None
    try:
        runtime = resolve_runtime_model(database, settings, body.model)
        stream, content_type = await open_chat_stream(
            database,
            settings,
            body.model_dump(exclude_none=True),
            runtime_model=runtime,
        )
    except AIRuntimeError as error:
        _record_inference_audit(database, actor, body.model, started_at, "failed", runtime, error.code)
        raise ResourceManagementError(error.status_code, error.code, str(error)) from error
    except asyncio.CancelledError:
        _record_inference_audit(database, actor, body.model, started_at, "cancelled", runtime, "request_cancelled")
        raise
    except Exception:
        _record_inference_audit(database, actor, body.model, started_at, "failed", runtime, "ai_provider_unavailable")
        raise
    audited_stream = AuditedInferenceStream(stream, database, actor, body.model, runtime, started_at)
    return StreamingResponse(
        audited_stream,
        status_code=200,
        media_type=content_type,
        headers={"cache-control": "no-store", "x-content-type-options": "nosniff"},
        background=BackgroundTask(audited_stream.aclose),
    )
