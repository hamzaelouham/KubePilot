from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import AuthenticatedActor
from app.core.rbac import Permission, require_permission

from .settings_schemas import SettingsAccessResponse

router = APIRouter()


@router.get("/settings/access", response_model=SettingsAccessResponse)
def settings_access(
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.SETTINGS_READ))],
) -> SettingsAccessResponse:
    return SettingsAccessResponse(allowed=True)
