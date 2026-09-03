from dataclasses import dataclass
from typing import Annotated, AsyncIterator

from fastapi import Depends, HTTPException, Request, status

from app.core.config import Settings


@dataclass(frozen=True)
class AuthenticatedActor:
    identifier: str
    role: str


@dataclass(frozen=True)
class DatabaseSession:
    connection_url: str


async def get_settings(request: Request) -> Settings:
    return request.app.state.settings


async def get_current_actor(request: Request) -> AuthenticatedActor:
    actor = getattr(request.state, "actor", None)
    if not isinstance(actor, AuthenticatedActor):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "authentication_required", "message": "Authentication is required"},
        )
    return actor


async def get_database_session(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncIterator[DatabaseSession]:
    yield DatabaseSession(connection_url=settings.database_url)
