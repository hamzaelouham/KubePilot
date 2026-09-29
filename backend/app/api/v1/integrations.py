from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as SQLAlchemySession

from app.core.dependencies import AuthenticatedActor, get_database_session, get_settings
from app.core.rbac import Permission, require_permission
from app.core.config import Settings
from app.services.integrations import (
    IntegrationServiceError,
    begin_authorization,
    complete_authorization,
    disconnect,
    list_connection_metadata,
    test_connection,
)

from .integration_schemas import (
    IntegrationActionResponse,
    IntegrationAuthorizeResponse,
    IntegrationCallbackResponse,
    IntegrationListResponse,
)


router = APIRouter()


@router.get("/settings/integrations", response_model=IntegrationListResponse)
def integrations(
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.SETTINGS_READ))],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> IntegrationListResponse:
    return IntegrationListResponse(integrations=list_connection_metadata(database))


@router.post("/settings/integrations/{provider_id}/authorize", response_model=IntegrationAuthorizeResponse)
def authorize_integration(
    provider_id: str,
    actor: Annotated[AuthenticatedActor, Depends(require_permission(Permission.SETTINGS_WRITE))],
    settings: Annotated[Settings, Depends(get_settings)],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> IntegrationAuthorizeResponse:
    try:
        return IntegrationAuthorizeResponse(**begin_authorization(database, settings, actor.user_id, provider_id))
    except IntegrationServiceError as error:
        raise _service_error(error) from error


@router.get("/settings/integrations/{provider_id}/callback", response_model=IntegrationCallbackResponse)
def integration_callback(
    provider_id: str,
    state: Annotated[str, Query(min_length=16, max_length=256)],
    settings: Annotated[Settings, Depends(get_settings)],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
    code: Annotated[str | None, Query(min_length=1, max_length=4096)] = None,
    error: Annotated[str | None, Query(min_length=1, max_length=256)] = None,
) -> IntegrationCallbackResponse:
    try:
        result = complete_authorization(database, settings, provider_id, state, code, error)
    except IntegrationServiceError as service_error:
        raise _service_error(service_error) from service_error
    return IntegrationCallbackResponse(
        provider_id=provider_id,
        status="connected",
        connected=True,
        message="The integration is connected",
    )


@router.post("/settings/integrations/{provider_id}/test", response_model=IntegrationActionResponse)
def test_integration(
    provider_id: str,
    actor: Annotated[AuthenticatedActor, Depends(require_permission(Permission.SETTINGS_WRITE))],
    settings: Annotated[Settings, Depends(get_settings)],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> IntegrationActionResponse:
    try:
        result = test_connection(database, settings, actor.user_id, provider_id)
    except IntegrationServiceError as error:
        raise _service_error(error) from error
    return IntegrationActionResponse(**result, message="The integration connection test succeeded")


@router.delete("/settings/integrations/{provider_id}", response_model=IntegrationActionResponse)
def disconnect_integration(
    provider_id: str,
    actor: Annotated[AuthenticatedActor, Depends(require_permission(Permission.SETTINGS_WRITE))],
    settings: Annotated[Settings, Depends(get_settings)],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> IntegrationActionResponse:
    try:
        result = disconnect(database, settings, actor.user_id, provider_id)
    except IntegrationServiceError as error:
        raise _service_error(error) from error
    return IntegrationActionResponse(**result, message="The integration was disconnected")


def _service_error(error: IntegrationServiceError) -> HTTPException:
    return HTTPException(
        status_code=error.status_code,
        detail={"code": error.code, "message": str(error)},
    )
