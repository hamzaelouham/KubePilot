from enum import Enum
from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.core.dependencies import AuthenticatedActor, get_current_actor


class Role(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class Permission:
    CLUSTERS_READ = "clusters:read"
    CLUSTERS_CREATE = "clusters:create"
    CLUSTERS_UPDATE = "clusters:update"
    CLUSTERS_DELETE = "clusters:delete"
    RESOURCES_READ = "resources:read"
    RESOURCES_CREATE = "resources:create"
    RESOURCES_UPDATE = "resources:update"
    RESOURCES_DELETE = "resources:delete"
    USERS_READ = "users:read"
    USERS_CREATE = "users:create"
    USERS_UPDATE = "users:update"
    USERS_DELETE = "users:delete"
    USERS_RESET_PASSWORD = "users:reset_password"
    USERS_FORCE_PASSWORD_CHANGE = "users:force_password_change"


ALL_PERMISSIONS: frozenset[str] = frozenset(
    {
        getattr(Permission, name)
        for name in dir(Permission)
        if name.isupper() and isinstance(getattr(Permission, name), str)
    }
)

ROLE_PERMISSIONS: dict[Role, frozenset[str]] = {
    Role.VIEWER: frozenset(
        {
            Permission.CLUSTERS_READ,
            Permission.RESOURCES_READ,
        }
    ),
    Role.OPERATOR: frozenset(
        {
            Permission.CLUSTERS_READ,
            Permission.CLUSTERS_CREATE,
            Permission.CLUSTERS_UPDATE,
            Permission.RESOURCES_READ,
            Permission.RESOURCES_CREATE,
            Permission.RESOURCES_UPDATE,
            Permission.RESOURCES_DELETE,
        }
    ),
    Role.ADMIN: ALL_PERMISSIONS,
}


def has_permission(role: str, permission: str) -> bool:
    try:
        permitted = ROLE_PERMISSIONS[Role(role)]
    except (KeyError, ValueError):
        return False
    return permission in permitted


def require_permission(permission: str):
    def dependency(
        actor: Annotated[AuthenticatedActor, Depends(get_current_actor)],
    ) -> AuthenticatedActor:
        if actor.restricted:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "password_change_required",
                    "message": "Password change required before accessing this resource",
                },
            )
        if not has_permission(actor.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "insufficient_permissions",
                    "message": "Insufficient permissions for the required role",
                },
            )
        return actor

    return dependency