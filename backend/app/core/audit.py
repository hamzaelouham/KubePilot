from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session as SQLAlchemySession

from app.models.entities import AuditAction


class AuditEvent:
    USER_CREATED = "USER_CREATED"
    USER_UPDATED = "USER_UPDATED"
    USER_DEACTIVATED = "USER_DEACTIVATED"
    USER_REACTIVATED = "USER_REACTIVATED"
    USER_DELETED = "USER_DELETED"
    USER_ROLE_CHANGED = "USER_ROLE_CHANGED"
    USER_PASSWORD_RESET = "USER_PASSWORD_RESET"
    USER_PASSWORD_CHANGED = "USER_PASSWORD_CHANGED"
    USER_FORCED_PASSWORD_CHANGE = "USER_FORCED_PASSWORD_CHANGE"
    USER_LOGIN_SUCCESS = "USER_LOGIN_SUCCESS"
    USER_LOGIN_FAILURE = "USER_LOGIN_FAILURE"
    CLUSTER_CREATED = "cluster.create"
    CLUSTER_STATUS_CHANGED = "cluster.status_change"


def record_audit(
    database: SQLAlchemySession,
    action: str,
    actor_id: UUID | None,
    resource_type: str,
    resource_id: str,
    *,
    target_user_id: UUID | None = None,
    result: str = "",
    context: Mapping[str, Any] | None = None,
) -> AuditAction:
    import json as json_module

    event = AuditAction(
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        target_user_id=target_user_id,
        result=result,
        context=json_module.dumps(context) if context is not None else None,
    )
    database.add(event)
    database.flush()
    return event