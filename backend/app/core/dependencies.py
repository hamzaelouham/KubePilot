from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session as SQLAlchemySession

from app.core.config import Settings
from app.db.session import get_database_session as open_database_session


@dataclass(frozen=True)
class AuthenticatedActor:
    identifier: str
    role: str


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


def get_database_session(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Iterator[SQLAlchemySession]:
    yield from open_database_session(settings)


