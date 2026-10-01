"""Account-backed Assistant conversation persistence and retention."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.api.v1.conversation_schemas import (
    ConversationContext,
    ConversationCreateRequest,
    ConversationDetail,
    ConversationListResponse,
    ConversationMessage,
    ConversationPurgeResponse,
    ConversationRenameRequest,
    ConversationRetentionResponse,
    ConversationSaveRequest,
    ConversationSummary,
)
from app.assistant.sanitize import sanitize, safe_text
from app.core.audit import AuditEvent, record_audit
from app.models.entities import (
    AIAgent,
    AIModelConfig,
    ApplicationSetting,
    AssistantConversation,
    AssistantConversationPart,
    AssistantProposal,
    ClusterConnection,
    UserAccount,
)

CONVERSATION_RETENTION_SETTING_KEY = "assistant.conversation_retention_days"
DEFAULT_CONVERSATION_RETENTION_DAYS = 30
MIN_CONVERSATION_RETENTION_DAYS = 1
MAX_CONVERSATION_RETENTION_DAYS = 365
MAX_PART_BYTES = 32 * 1024


class ConversationError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 422, code: str = "conversation_error"):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _owner_or_not_found(database: Session, conversation_id: UUID, owner_id: UUID, admin: bool) -> AssistantConversation:
    conversation = database.get(AssistantConversation, conversation_id)
    if conversation is None or (not admin and conversation.owner_id != owner_id):
        raise ConversationError("Conversation was not found", status_code=404, code="conversation_not_found")
    return conversation


def _validate_reference(database: Session, body: ConversationCreateRequest | ConversationSaveRequest) -> None:
    if body.model_id is not None and database.get(AIModelConfig, body.model_id) is None:
        raise ConversationError("The selected model was not found", status_code=422, code="model_not_found")
    if body.agent_id is not None and database.get(AIAgent, body.agent_id) is None:
        raise ConversationError("The selected agent was not found", status_code=422, code="agent_not_found")


def _cluster_id(database: Session, cluster_name: str) -> UUID:
    cluster = database.scalar(select(ClusterConnection).where(ClusterConnection.name == cluster_name))
    if cluster is None or cluster.status != "active":
        raise ConversationError("The selected cluster was not found", status_code=404, code="cluster_not_found")
    return cluster.id


def _safe_title(title: str | None) -> str:
    value = (title or "New conversation").strip()
    if not value or "\x00" in value:
        return "New conversation"
    return value[:160]


def _summary(conversation: AssistantConversation, owner: UserAccount | None = None) -> ConversationSummary:
    return ConversationSummary(
        id=conversation.id,
        title=conversation.title,
        mode=conversation.mode,
        model_id=conversation.model_id,
        agent_id=conversation.agent_id,
        cluster=conversation.cluster_name,
        namespace=conversation.namespace,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        owner={"id": owner.id, "email": owner.email} if owner is not None else None,
    )


def _detail(database: Session, conversation: AssistantConversation, owner: UserAccount | None = None) -> ConversationDetail:
    parts = database.scalars(
        select(AssistantConversationPart)
        .where(AssistantConversationPart.conversation_id == conversation.id)
        .order_by(AssistantConversationPart.sequence, AssistantConversationPart.id)
    ).all()
    summary = _summary(conversation, owner)
    return ConversationDetail(
        **summary.model_dump(),
        resource=conversation.resource,
        name=conversation.resource_name,
        release=conversation.release,
        parts=[
            {
                "id": part.id,
                "sequence": part.sequence,
                "role": part.role,
                "part_type": part.part_type,
                "payload": part.payload,
                "proposal_id": part.proposal_id,
                "created_at": part.created_at,
            }
            for part in parts
        ],
    )


def create_conversation(database: Session, owner_id: UUID, body: ConversationCreateRequest) -> ConversationDetail:
    _validate_reference(database, body)
    conversation = AssistantConversation(
        owner_id=owner_id,
        title=_safe_title(body.title),
        mode=body.mode,
        model_id=body.model_id,
        agent_id=body.agent_id,
        cluster_id=_cluster_id(database, body.context.cluster),
        cluster_name=body.context.cluster,
        namespace=body.context.namespace,
        resource=body.context.resource,
        resource_name=body.context.name,
        release=body.context.release,
    )
    database.add(conversation)
    database.commit()
    database.refresh(conversation)
    return _detail(database, conversation)


def list_conversations(
    database: Session,
    owner_id: UUID,
    *,
    admin: bool,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> ConversationListResponse:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    filters = [] if admin else [AssistantConversation.owner_id == owner_id]
    clean_search = (search or "").strip()
    if clean_search:
        pattern = f"%{clean_search}%"
        filters.append(
            or_(
                AssistantConversation.title.ilike(pattern),
                AssistantConversation.cluster_name.ilike(pattern),
                AssistantConversation.namespace.ilike(pattern),
                AssistantConversation.owner_id.in_(select(UserAccount.id).where(UserAccount.email.ilike(pattern))),
            )
        )
    query = select(AssistantConversation).where(*filters).order_by(AssistantConversation.updated_at.desc(), AssistantConversation.id.desc()).offset(offset).limit(limit)
    conversations = list(database.scalars(query).all())
    owners: dict[UUID, UserAccount] = {}
    if admin and conversations:
        owners = {user.id: user for user in database.scalars(select(UserAccount).where(UserAccount.id.in_({row.owner_id for row in conversations}))).all()}
    total = database.scalar(select(func.count()).select_from(AssistantConversation).where(*filters)) or 0
    if admin:
        record_audit(
            database,
            AuditEvent.ASSISTANT_CONVERSATION_LISTED,
            owner_id,
            "assistant_conversation",
            "list",
            result="succeeded",
            context={"search": bool(clean_search), "count": len(conversations)},
        )
        database.commit()
    return ConversationListResponse(
        conversations=[_summary(row, owners.get(row.owner_id)) for row in conversations],
        total=total,
    )


def get_conversation(database: Session, owner_id: UUID, conversation_id: UUID, *, admin: bool) -> ConversationDetail:
    conversation = _owner_or_not_found(database, conversation_id, owner_id, admin)
    owner = database.get(UserAccount, conversation.owner_id) if admin else None
    if admin:
        record_audit(
            database,
            AuditEvent.ASSISTANT_CONVERSATION_VIEWED,
            owner_id,
            "assistant_conversation",
            str(conversation.id),
            target_user_id=conversation.owner_id,
            result="succeeded",
        )
        database.commit()
    return _detail(database, conversation, owner)


def rename_conversation(database: Session, owner_id: UUID, conversation_id: UUID, body: ConversationRenameRequest, *, admin: bool) -> ConversationSummary:
    conversation = _owner_or_not_found(database, conversation_id, owner_id, admin)
    conversation.title = _safe_title(body.title)
    conversation.updated_at = _utc_now()
    if admin:
        record_audit(
            database,
            AuditEvent.ASSISTANT_CONVERSATION_RENAMED,
            owner_id,
            "assistant_conversation",
            str(conversation.id),
            target_user_id=conversation.owner_id,
            result="succeeded",
        )
    database.commit()
    return _summary(conversation, database.get(UserAccount, conversation.owner_id) if admin else None)


def delete_conversation(database: Session, owner_id: UUID, conversation_id: UUID, *, admin: bool) -> None:
    conversation = _owner_or_not_found(database, conversation_id, owner_id, admin)
    if admin:
        record_audit(
            database,
            AuditEvent.ASSISTANT_CONVERSATION_DELETED,
            owner_id,
            "assistant_conversation",
            str(conversation.id),
            target_user_id=conversation.owner_id,
            result="succeeded",
        )
    database.execute(delete(AssistantConversationPart).where(AssistantConversationPart.conversation_id == conversation.id))
    database.delete(conversation)
    database.commit()


def _proposal_id(value: Any) -> UUID | None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "proposal_id" and isinstance(item, str):
                try:
                    return UUID(item)
                except ValueError:
                    return None
            found = _proposal_id(item)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _proposal_id(item)
            if found is not None:
                return found
    return None


def _parts(database: Session, owner_id: UUID, messages: list[ConversationMessage]) -> tuple[list[dict[str, Any]], str | None]:
    result: list[dict[str, Any]] = []
    first_user_text: str | None = None
    total_bytes = 0
    for message in messages:
        for part in message.parts:
            part_type = part.get("type")
            if not isinstance(part_type, str) or not (part_type == "text" or part_type == "step-start" or part_type.startswith("tool-")):
                raise ConversationError("Only text and KubePilot tool results can be saved", code="invalid_message")
            if part.get("providerExecuted") is True:
                raise ConversationError("Provider-executed parts cannot be saved", code="invalid_message")
            safe_part = sanitize(part)
            if not isinstance(safe_part, dict):
                raise ConversationError("Conversation part is invalid", code="invalid_message")
            encoded_size = len(json.dumps(safe_part, separators=(",", ":"), default=str).encode())
            total_bytes += encoded_size
            if encoded_size > MAX_PART_BYTES or total_bytes > 256 * 1024:
                raise ConversationError("Conversation part is too large", status_code=413, code="conversation_too_large")
            if message.role == "user" and first_user_text is None and part_type == "text" and isinstance(safe_part.get("text"), str):
                first_user_text = safe_text(safe_part["text"], 80).strip()
            proposal_id = _proposal_id(safe_part)
            if proposal_id is not None:
                proposal = database.get(AssistantProposal, proposal_id)
                if proposal is None or proposal.actor_id != owner_id:
                    raise ConversationError("Conversation contains an unauthorized proposal reference", code="invalid_message")
            result.append({"role": message.role, "part_type": part_type, "payload": safe_part, "proposal_id": proposal_id})
    return result, first_user_text


def save_conversation(database: Session, owner_id: UUID, conversation_id: UUID, body: ConversationSaveRequest) -> ConversationDetail:
    conversation = _owner_or_not_found(database, conversation_id, owner_id, False)
    _validate_reference(database, body)
    parts, first_user_text = _parts(database, owner_id, body.messages)
    cluster = database.scalar(select(ClusterConnection).where(ClusterConnection.name == body.context.cluster))
    conversation.mode = body.mode
    conversation.model_id = body.model_id
    conversation.agent_id = body.agent_id
    conversation.cluster_id = cluster.id if cluster is not None else None
    conversation.cluster_name = body.context.cluster
    conversation.namespace = body.context.namespace
    conversation.resource = body.context.resource
    conversation.resource_name = body.context.name
    conversation.release = body.context.release
    if conversation.title == "New conversation" and first_user_text:
        conversation.title = first_user_text or "New conversation"
    conversation.updated_at = _utc_now()
    database.execute(delete(AssistantConversationPart).where(AssistantConversationPart.conversation_id == conversation.id))
    for sequence, part in enumerate(parts):
        database.add(
            AssistantConversationPart(
                conversation_id=conversation.id,
                sequence=sequence,
                role=part["role"],
                part_type=part["part_type"],
                payload=part["payload"],
                proposal_id=part["proposal_id"],
            )
        )
    database.commit()
    return _detail(database, conversation)


def conversation_retention_days(database: Session) -> int:
    setting = database.scalar(select(ApplicationSetting).where(ApplicationSetting.key == CONVERSATION_RETENTION_SETTING_KEY))
    value = setting.value_json if setting is not None else DEFAULT_CONVERSATION_RETENTION_DAYS
    if isinstance(value, bool) or not isinstance(value, int) or not MIN_CONVERSATION_RETENTION_DAYS <= value <= MAX_CONVERSATION_RETENTION_DAYS:
        return DEFAULT_CONVERSATION_RETENTION_DAYS
    return value


def set_conversation_retention(database: Session, actor_id: UUID, retention_days: int) -> ConversationRetentionResponse:
    if not MIN_CONVERSATION_RETENTION_DAYS <= retention_days <= MAX_CONVERSATION_RETENTION_DAYS:
        raise ConversationError("Retention must be between 1 and 365 days", code="invalid_retention")
    row = database.scalar(select(ApplicationSetting).where(ApplicationSetting.key == CONVERSATION_RETENTION_SETTING_KEY))
    if row is None:
        row = ApplicationSetting(key=CONVERSATION_RETENTION_SETTING_KEY, value_json=retention_days, created_by_id=actor_id, updated_by_id=actor_id)
        database.add(row)
    else:
        row.value_json = retention_days
        row.updated_by_id = actor_id
    record_audit(
        database,
        AuditEvent.ASSISTANT_CONVERSATION_RETENTION_UPDATED,
        actor_id,
        "application_setting",
        CONVERSATION_RETENTION_SETTING_KEY,
        result="succeeded",
        context={"retention_days": retention_days},
    )
    database.commit()
    return ConversationRetentionResponse(retention_days=retention_days)


def purge_expired_conversations(database: Session, actor_id: UUID | None = None) -> ConversationPurgeResponse:
    retention_days = conversation_retention_days(database)
    cutoff = _utc_now() - timedelta(days=retention_days)
    count = database.scalar(select(func.count()).select_from(AssistantConversation).where(AssistantConversation.updated_at < cutoff)) or 0
    expired_ids = select(AssistantConversation.id).where(AssistantConversation.updated_at < cutoff)
    database.execute(delete(AssistantConversationPart).where(AssistantConversationPart.conversation_id.in_(expired_ids)))
    database.execute(delete(AssistantConversation).where(AssistantConversation.updated_at < cutoff))
    if actor_id is not None or count:
        record_audit(
            database,
            AuditEvent.ASSISTANT_CONVERSATION_PURGED,
            actor_id,
            "assistant_conversation",
            "retention",
            result="succeeded",
            context={"deleted": count, "cutoff": cutoff.isoformat(), "retention_days": retention_days, "automated": actor_id is None},
        )
    database.commit()
    return ConversationPurgeResponse(deleted=count, cutoff=cutoff, retention_days=retention_days)


def cleanup_conversations(database: Session) -> int:
    return purge_expired_conversations(database).deleted
