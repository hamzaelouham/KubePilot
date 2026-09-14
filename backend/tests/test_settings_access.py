import pytest
from fastapi import HTTPException

from app.api.v1.settings import settings_access
from app.core.dependencies import AuthenticatedActor
from app.core.rbac import Permission, has_permission, require_permission


def test_settings_permission_is_admin_only() -> None:
    assert has_permission("admin", Permission.SETTINGS_READ) is True
    assert has_permission("operator", Permission.SETTINGS_READ) is False
    assert has_permission("viewer", Permission.SETTINGS_READ) is False

    authorized = require_permission(Permission.SETTINGS_READ)
    admin = AuthenticatedActor("admin@example.com", "admin")
    assert authorized(admin) is admin

    for role in ("operator", "viewer"):
        with pytest.raises(HTTPException) as error:
            authorized(AuthenticatedActor(f"{role}@example.com", role))
        assert error.value.status_code == 403
        assert error.value.detail["code"] == "insufficient_permissions"


def test_settings_access_response_is_stable() -> None:
    response = settings_access(AuthenticatedActor("admin@example.com", "admin"))
    assert response.model_dump() == {"allowed": True}
