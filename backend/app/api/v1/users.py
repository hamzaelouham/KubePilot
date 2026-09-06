import re
from datetime import timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as SQLAlchemySession

from app.core.audit import AuditEvent, record_audit
from app.core.dependencies import AuthenticatedActor, get_database_session, get_settings
from app.core.passwords import hash_password, validate_password_policy
from app.core.rbac import Permission, Role, require_permission
from app.core.config import Settings
from app.core.timeutils import is_expired, now
from app.models.entities import AuditAction, Session, UserAccount

from .users_schemas import (
    PasswordResetRequest,
    UserCreateRequest,
    UserListResponse,
    UserSummary,
    UserUpdateRequest,
)

router = APIRouter()

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _is_active_admin(database: SQLAlchemySession, user_id: UUID) -> bool:
    user = database.get(UserAccount, user_id)
    return user is not None and user.role == Role.ADMIN.value and user.is_active


def _only_active_admin(database: SQLAlchemySession, user_id: UUID) -> bool:
    count = database.scalar(
        select(func.count(UserAccount.id)).where(
            UserAccount.role == Role.ADMIN.value,
            UserAccount.is_active.is_(True),
        )
    )
    return count == 1 and _is_active_admin(database, user_id)


def _get_user_or_404(database: SQLAlchemySession, user_id: UUID) -> UserAccount:
    user = database.scalar(select(UserAccount).where(UserAccount.id == user_id))
    if user is None:
        raise HTTPException(status_code=404, detail={"code": "user_not_found", "message": "User was not found"})
    return user


def _summary(user: UserAccount, settings: Settings) -> UserSummary:
    return UserSummary(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        password_expires_at=user.password_expires_at,
        password_expired=is_expired(user.password_expires_at),
        must_change_password=user.must_change_password,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def _parse_role(value: str) -> Role:
    try:
        return Role(value)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_role", "message": f"{value!r} is not a valid role"},
        )


def _validate_email(email: str) -> str:
    normalized = email.strip().lower()
    if not normalized or not _EMAIL_PATTERN.match(normalized):
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_email", "message": "A valid email address is required"},
        )
    return normalized


def _validate_new_password(password: str, settings: Settings) -> None:
    valid, reason = validate_password_policy(password, settings.password_min_length)
    if not valid:
        raise HTTPException(status_code=422, detail={"code": "invalid_password", "message": reason})


def _invalidate_sessions(database: SQLAlchemySession, user_id: UUID) -> None:
    database.execute(delete(Session).where(Session.user_id == user_id))


@router.get("/users", response_model=UserListResponse)
def list_users(
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.USERS_READ))],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserListResponse:
    users = database.scalars(select(UserAccount).order_by(UserAccount.email)).all()
    return UserListResponse(items=[_summary(user, settings) for user in users])


@router.post("/users", response_model=UserSummary, status_code=201)
def create_user(
    request: UserCreateRequest,
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.USERS_CREATE))],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserSummary:
    email = _validate_email(request.email)
    _validate_new_password(request.password, settings)
    role = _parse_role(request.role).value

    existing = database.scalar(select(UserAccount).where(UserAccount.email == email))
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail={"code": "user_email_conflict", "message": "A user with this email already exists"},
        )

    current = now()
    ttl_days = request.password_expires_in_days if request.password_expires_in_days is not None else settings.password_ttl_days
    user = UserAccount(
        email=email,
        password_hash=hash_password(request.password),
        role=role,
        is_active=True,
        must_change_password=False,
        password_changed_at=current,
        password_expires_at=current + timedelta(days=ttl_days),
        updated_at=current,
    )
    database.add(user)
    database.flush()
    record_audit(
        database,
        AuditEvent.USER_CREATED,
        actor_id=_authorized.user_id,
        resource_type="user",
        resource_id=str(user.id),
        target_user_id=user.id,
        result="success",
        context={"email": email, "role": role},
    )
    database.commit()
    return _summary(user, settings)


@router.get("/users/{user_id}", response_model=UserSummary)
def get_user(
    user_id: UUID,
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.USERS_READ))],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserSummary:
    return _summary(_get_user_or_404(database, user_id), settings)


@router.patch("/users/{user_id}", response_model=UserSummary)
def update_user(
    user_id: UUID,
    request: UserUpdateRequest,
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.USERS_UPDATE))],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserSummary:
    user = _get_user_or_404(database, user_id)
    current = now()
    is_self = _authorized.user_id == user.id

    if request.is_active is False and user.is_active:
        if is_self:
            raise HTTPException(
                status_code=422,
                detail={"code": "cannot_deactivate_self", "message": "You cannot deactivate your own account"},
            )
        if _only_active_admin(database, user.id):
            raise HTTPException(
                status_code=422,
                detail={"code": "cannot_deactivate_last_admin", "message": "The last active admin cannot be deactivated"},
            )

    if request.force_password_change and not user.must_change_password:
        if is_self:
            raise HTTPException(
                status_code=422,
                detail={"code": "cannot_force_own_password_change", "message": "You cannot force your own password change"},
            )

    changes: list[tuple[str, str]] = []
    if request.role is not None and request.role != user.role:
        new_role = _parse_role(request.role).value
        if new_role != user.role:
            if is_self:
                raise HTTPException(
                    status_code=422,
                    detail={"code": "cannot_change_own_role", "message": "You cannot change your own role"},
                )
            if user.role == Role.ADMIN.value and _only_active_admin(database, user.id):
                raise HTTPException(
                    status_code=422,
                    detail={"code": "cannot_demote_last_admin", "message": "The last active admin cannot be demoted"},
                )
            previous = user.role
            user.role = new_role
            changes.append((AuditEvent.USER_ROLE_CHANGED, f"{previous}->{new_role}"))

    if request.is_active is not None and request.is_active != user.is_active:
        user.is_active = request.is_active
        changes.append((AuditEvent.USER_REACTIVATED if request.is_active else AuditEvent.USER_DEACTIVATED, ""))
        if not request.is_active:
            _invalidate_sessions(database, user.id)

    if request.force_password_change and not user.must_change_password:
        user.must_change_password = True
        changes.append((AuditEvent.USER_FORCED_PASSWORD_CHANGE, ""))
        _invalidate_sessions(database, user.id)

    if request.password_expires_in_days is not None:
        user.password_expires_at = current + timedelta(days=request.password_expires_in_days)

    if changes or request.password_expires_in_days is not None:
        user.updated_at = current
        for action, detail in changes:
            record_audit(
                database,
                action,
                actor_id=_authorized.user_id,
                resource_type="user",
                resource_id=str(user.id),
                target_user_id=user.id,
                result="success",
                context={"detail": detail} if detail else None,
            )
        database.commit()

    return _summary(user, settings)


@router.post("/users/{user_id}/reset-password", response_model=UserSummary)
def reset_user_password(
    user_id: UUID,
    request: PasswordResetRequest,
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.USERS_RESET_PASSWORD))],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserSummary:
    user = _get_user_or_404(database, user_id)
    if _authorized.user_id == user.id:
        raise HTTPException(
            status_code=422,
            detail={"code": "cannot_reset_own_password", "message": "Use the change-password endpoint for your own password"},
        )
    _validate_new_password(request.new_password, settings)
    user.password_hash = hash_password(request.new_password)
    user.must_change_password = True
    user.updated_at = now()
    _invalidate_sessions(database, user.id)
    record_audit(
        database,
        AuditEvent.USER_PASSWORD_RESET,
        actor_id=_authorized.user_id,
        resource_type="user",
        resource_id=str(user.id),
        target_user_id=user.id,
        result="success",
    )
    database.commit()
    return _summary(user, settings)


@router.post("/users/{user_id}/force-password-change", response_model=UserSummary)
def force_user_password_change(
    user_id: UUID,
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.USERS_FORCE_PASSWORD_CHANGE))],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserSummary:
    user = _get_user_or_404(database, user_id)
    if _authorized.user_id == user.id:
        raise HTTPException(
            status_code=422,
            detail={"code": "cannot_force_own_password_change", "message": "You cannot force your own password change"},
        )
    user.must_change_password = True
    user.updated_at = now()
    _invalidate_sessions(database, user.id)
    record_audit(
        database,
        AuditEvent.USER_FORCED_PASSWORD_CHANGE,
        actor_id=_authorized.user_id,
        resource_type="user",
        resource_id=str(user.id),
        target_user_id=user.id,
        result="success",
    )
    database.commit()
    return _summary(user, settings)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: UUID,
    _authorized: Annotated[AuthenticatedActor, Depends(require_permission(Permission.USERS_DELETE))],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> None:
    user = _get_user_or_404(database, user_id)
    if _authorized.user_id == user.id:
        raise HTTPException(
            status_code=422,
            detail={"code": "cannot_delete_self", "message": "You cannot delete your own account"},
        )
    if _only_active_admin(database, user.id):
        raise HTTPException(
            status_code=422,
            detail={"code": "cannot_delete_last_admin", "message": "The last active admin cannot be deleted"},
        )
    email = user.email
    history_count = database.scalar(
        select(func.count())
        .select_from(AuditAction)
        .where((AuditAction.actor_id == user.id) | (AuditAction.target_user_id == user.id))
    )
    if history_count:
        raise HTTPException(
            status_code=409,
            detail={"code": "user_has_history", "message": "User is referenced by audit history and cannot be deleted from the database"},
        )
    database.delete(user)
    try:
        database.flush()
    except IntegrityError:
        database.rollback()
        raise HTTPException(
            status_code=409,
            detail={"code": "user_has_history", "message": "User is referenced by audit history and cannot be deleted from the database"},
        )
    record_audit(
        database,
        AuditEvent.USER_DELETED,
        actor_id=_authorized.user_id,
        resource_type="user",
        resource_id=str(user_id),
        result="success",
        context={"deleted_user": email},
    )
    database.commit()