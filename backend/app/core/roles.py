from typing import Annotated

from fastapi import Depends, HTTPException

from app.core.dependencies import AuthenticatedActor, get_current_actor

ROLE_RANK = {"viewer": 0, "operator": 1, "admin": 2}

_INSUFFICIENT_PERMISSIONS = {
    "code": "insufficient_permissions",
    "message": "Insufficient permissions for the required role",
}


def require_minimum_role(min_role: str):
    if min_role not in ROLE_RANK:
        raise ValueError(f"unknown role: {min_role}")

    def dependency(
        actor: Annotated[AuthenticatedActor, Depends(get_current_actor)],
    ) -> AuthenticatedActor:
        if ROLE_RANK.get(actor.role, -1) < ROLE_RANK[min_role]:
            raise HTTPException(status_code=403, detail=_INSUFFICIENT_PERMISSIONS)
        return actor

    return dependency