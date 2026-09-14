from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as SQLAlchemySession

from app.core.dependencies import AuthenticatedActor, get_current_actor, get_database_session
from app.core.rbac import Permission, require_permission

from app.services.settings import get_user_preferences, update_user_preferences

from .settings_schemas import (
    SettingsAccessResponse,
    SettingsPreferencesResponse,
    SettingsPreferencesUpdate,
)

router = APIRouter()


@router.get("/settings/access", response_model=SettingsAccessResponse)
def settings_access(
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.SETTINGS_READ))],
) -> SettingsAccessResponse:
    return SettingsAccessResponse(allowed=True)


@router.get("/settings/preferences", response_model=SettingsPreferencesResponse)
def settings_preferences(
    actor: Annotated[AuthenticatedActor, Depends(get_current_actor)],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> SettingsPreferencesResponse:
    return get_user_preferences(database, actor.user_id)


@router.patch("/settings/preferences", response_model=SettingsPreferencesResponse)
def update_settings_preferences(
    changes: SettingsPreferencesUpdate,
    actor: Annotated[AuthenticatedActor, Depends(get_current_actor)],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> SettingsPreferencesResponse:
    return update_user_preferences(database, actor.user_id, changes)
