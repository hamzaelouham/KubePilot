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
    CLUSTER_UPDATED = "cluster.update"
    CLUSTER_STATUS_CHANGED = "cluster.status_change"
    CLUSTER_DELETED = "cluster.delete"
    MARKETPLACE_INSTALL_QUEUED = "marketplace.install_queued"
    MARKETPLACE_INSTALL_SUCCEEDED = "marketplace.install_succeeded"
    MARKETPLACE_INSTALL_FAILED = "marketplace.install_failed"
    MARKETPLACE_ROLLBACK_QUEUED = "marketplace.rollback_queued"
    MARKETPLACE_ROLLBACK_SUCCEEDED = "marketplace.rollback_succeeded"
    MARKETPLACE_ROLLBACK_FAILED = "marketplace.rollback_failed"
    MARKETPLACE_UNINSTALL_QUEUED = "marketplace.uninstall_queued"
    MARKETPLACE_UNINSTALL_SUCCEEDED = "marketplace.uninstall_succeeded"
    MARKETPLACE_UNINSTALL_FAILED = "marketplace.uninstall_failed"
    RESOURCE_CREATE_REQUESTED = "resource.create_requested"
    RESOURCE_CREATE_RESULT = "resource.create_result"
    RESOURCE_DELETE_REQUESTED = "resource.delete_requested"
    RESOURCE_DELETE_RESULT = "resource.delete_result"


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
