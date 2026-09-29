from typing import Annotated

from datetime import datetime
from uuid import UUID

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
from app.services.integration_delivery import (
    DeliveryServiceError,
    get_delivery_job,
    list_delivery_jobs,
    retry_delivery,
)

from .integration_schemas import (
    IntegrationActionResponse,
    IntegrationAuthorizeResponse,
    IntegrationCallbackResponse,
    IntegrationDeliveryItem,
    IntegrationDeliveryListResponse,
    IntegrationDeliveryRetryResponse,
    IntegrationListResponse,
)


router = APIRouter()


@router.get("/settings/integrations/deliveries", response_model=IntegrationDeliveryListResponse)
def delivery_history(
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.SETTINGS_READ))],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
    provider: str | None = Query(default=None, min_length=1, max_length=32),
    status: str | None = Query(default=None, min_length=1, max_length=32),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1, le=10_000),
    limit: int = Query(default=20, ge=1, le=100),
) -> IntegrationDeliveryListResponse:
    try:
        result = list_delivery_jobs(
            database,
            provider=provider,
            status=status,
            date_from=date_from,
            date_to=date_to,
            page=page,
            limit=limit,
        )
    except DeliveryServiceError as error:
        raise _delivery_error(error) from error
    return IntegrationDeliveryListResponse(
        items=[IntegrationDeliveryItem(**item) for item in result["items"]],
        total=result["total"],
        page=result["page"],
        limit=result["limit"],
    )


@router.get("/settings/integrations/deliveries/{delivery_id}", response_model=IntegrationDeliveryItem)
def delivery_detail(
    delivery_id: UUID,
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.SETTINGS_READ))],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> IntegrationDeliveryItem:
    try:
        return IntegrationDeliveryItem(**get_delivery_job(database, delivery_id))
    except DeliveryServiceError as error:
        raise _delivery_error(error) from error


@router.post("/settings/integrations/deliveries/{delivery_id}/retry", response_model=IntegrationDeliveryRetryResponse)
def retry_delivery_job(
    delivery_id: UUID,
    actor: Annotated[AuthenticatedActor, Depends(require_permission(Permission.SETTINGS_WRITE))],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> IntegrationDeliveryRetryResponse:
    try:
        result = retry_delivery(database, actor.user_id, delivery_id)
    except DeliveryServiceError as error:
        raise _delivery_error(error) from error
    return IntegrationDeliveryRetryResponse(**result, message="The delivery was queued for retry")


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


def _delivery_error(error: DeliveryServiceError) -> HTTPException:
    return HTTPException(
        status_code=error.status_code,
        detail={"code": error.code, "message": str(error)},
    )
