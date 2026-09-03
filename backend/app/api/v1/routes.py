from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import (
    AuthenticatedActor,
    DatabaseSession,
    get_current_actor,
    get_database_session,
    get_settings,
)
from app.core.config import Settings

from .schemas import ActorResponse, HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    return HealthResponse(status="ok", service=settings.service_name)


@router.get("/auth/context", response_model=ActorResponse)
async def auth_context(
    actor: Annotated[AuthenticatedActor, Depends(get_current_actor)],
    _database: Annotated[DatabaseSession, Depends(get_database_session)],
) -> ActorResponse:
    return ActorResponse(identifier=actor.identifier, role=actor.role)
