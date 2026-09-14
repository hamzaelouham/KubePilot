from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as SQLAlchemySession

from app.core.dependencies import AuthenticatedActor, get_current_actor, get_database_session, get_settings
from app.core.config import Settings
from app.core.rbac import Permission, require_permission

from app.services.settings import get_user_preferences, update_user_preferences
from app.services.application_settings import (
    SettingsServiceError,
    delete_application_setting,
    delete_credential,
    list_application_settings,
    list_credential_metadata,
    replace_credential,
    upsert_application_setting,
)

from .settings_schemas import (
    SettingsAccessResponse,
    SettingsPreferencesResponse,
    SettingsPreferencesUpdate,
    ApplicationSettingItem,
    ApplicationSettingsResponse,
    ApplicationSettingValueRequest,
    CredentialMetadata,
    CredentialValueRequest,
    CredentialsResponse,
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


def _settings_service_error(error: SettingsServiceError) -> HTTPException:
    return HTTPException(
        status_code=error.status_code,
        detail={"code": error.code, "message": str(error)},
    )


@router.get("/settings/configuration", response_model=ApplicationSettingsResponse)
def application_settings(
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.SETTINGS_READ))],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> ApplicationSettingsResponse:
    return ApplicationSettingsResponse(settings=list_application_settings(database))


@router.put("/settings/configuration/{key}", response_model=ApplicationSettingItem)
def update_application_setting(
    key: str,
    changes: ApplicationSettingValueRequest,
    actor: Annotated[AuthenticatedActor, Depends(require_permission(Permission.SETTINGS_WRITE))],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> ApplicationSettingItem:
    try:
        return upsert_application_setting(database, actor.user_id, key, changes.value)
    except SettingsServiceError as error:
        raise _settings_service_error(error) from error


@router.delete("/settings/configuration/{key}", response_model=ApplicationSettingItem)
def remove_application_setting(
    key: str,
    actor: Annotated[AuthenticatedActor, Depends(require_permission(Permission.SETTINGS_WRITE))],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> ApplicationSettingItem:
    try:
        return delete_application_setting(database, actor.user_id, key)
    except SettingsServiceError as error:
        raise _settings_service_error(error) from error


@router.get("/settings/credentials", response_model=CredentialsResponse)
def credential_metadata(
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.SETTINGS_READ))],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> CredentialsResponse:
    return CredentialsResponse(credentials=list_credential_metadata(database))


@router.put("/settings/credentials/{credential_key}", response_model=CredentialMetadata)
def put_credential(
    credential_key: str,
    changes: CredentialValueRequest,
    actor: Annotated[AuthenticatedActor, Depends(require_permission(Permission.SETTINGS_WRITE))],
    settings: Annotated[Settings, Depends(get_settings)],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> CredentialMetadata:
    try:
        return replace_credential(database, settings, actor.user_id, credential_key, changes.value)
    except SettingsServiceError as error:
        raise _settings_service_error(error) from error


@router.delete("/settings/credentials/{credential_key}", response_model=CredentialMetadata)
def remove_credential(
    credential_key: str,
    actor: Annotated[AuthenticatedActor, Depends(require_permission(Permission.SETTINGS_WRITE))],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> CredentialMetadata:
    try:
        return delete_credential(database, actor.user_id, credential_key)
    except SettingsServiceError as error:
        raise _settings_service_error(error) from error
