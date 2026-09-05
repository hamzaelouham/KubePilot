from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session as SQLAlchemySession

from app.core.config import Settings
from app.core.dependencies import (
    AuthenticatedActor,
    get_database_session,
    get_settings,
    require_admin,
)
from app.core.passwords import hash_password
from app.models.entities import UserAccount

from .users_schemas import (
    CreateUserRequest,
    DeactivatedUserResponse,
    UserItem,
    UserListResponse,
    UserRole,
)

router = APIRouter()

_EMAIL_IN_USE = {"code": "email_in_use", "message": "A user with this email already exists"}
_PROTECTED_ADMIN = {"code": "protected_admin_account", "message": "The configured admin account is protected"}


def _to_item(user: UserAccount) -> UserItem:
    return UserItem(
        id=user.id,
        email=user.email,
        role=user.role,
        isActive=user.is_active,
        createdAt=user.created_at,
    )


@router.get("/users", response_model=UserListResponse)
def list_users(
    _actor: Annotated[AuthenticatedActor, Depends(require_admin)],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> UserListResponse:
    users = database.scalars(select(UserAccount).order_by(UserAccount.created_at.desc(), UserAccount.email)).all()
    return UserListResponse(items=[_to_item(user) for user in users])


@router.post("/users", response_model=UserItem, status_code=201)
def create_user(
    request: CreateUserRequest,
    _actor: Annotated[AuthenticatedActor, Depends(require_admin)],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> UserItem:
    email = request.email.strip().lower()
    existing = database.scalar(select(UserAccount).where(UserAccount.email == email))
    if existing is not None:
        raise HTTPException(status_code=409, detail=_EMAIL_IN_USE)
    user = UserAccount(email=email, password_hash=hash_password(request.password), role=request.role)
    database.add(user)
    database.commit()
    database.refresh(user)
    return _to_item(user)


@router.patch("/users/{user_id}/role", response_model=UserItem)
def update_user_role(
    user_id: UUID,
    request: UserRole,
    _actor: Annotated[AuthenticatedActor, Depends(require_admin)],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserItem:
    user = database.get(UserAccount, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail={"code": "user_not_found", "message": "User not found"})
    if user.email == settings.admin_email:
        raise HTTPException(status_code=422, detail=_PROTECTED_ADMIN)
    user.role = request.role
    database.commit()
    database.refresh(user)
    return _to_item(user)


@router.post("/users/{user_id}/deactivate", response_model=DeactivatedUserResponse)
def deactivate_user(
    user_id: UUID,
    _actor: Annotated[AuthenticatedActor, Depends(require_admin)],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DeactivatedUserResponse:
    user = database.get(UserAccount, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail={"code": "user_not_found", "message": "User not found"})
    if user.email == settings.admin_email:
        raise HTTPException(status_code=422, detail=_PROTECTED_ADMIN)
    user.is_active = False
    database.commit()
    database.refresh(user)
    return DeactivatedUserResponse(id=user.id, isActive=False)