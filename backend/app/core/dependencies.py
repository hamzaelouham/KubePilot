from collections.abc import Iterator
import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session as SQLAlchemySession
from sqlalchemy import select

from app.core.config import Settings
from app.db.session import get_database_session as open_database_session
from app.models.entities import UserAccount
from app.kubernetes.client import ClusterClient, create_cluster_client


@dataclass(frozen=True)
class AuthenticatedActor:
    identifier: str
    role: str


async def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_database_session(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Iterator[SQLAlchemySession]:
    yield from open_database_session(settings)


async def get_current_actor(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> AuthenticatedActor:
    cookie = request.cookies.get("kubepilot_session")
    actor = _resolve_cookie_actor(cookie, settings.auth_secret, database)
    if actor is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "authentication_required", "message": "Authentication is required"},
        )
    return actor


def _resolve_cookie_actor(
    cookie: str | None,
    secret: str,
    database: SQLAlchemySession,
) -> AuthenticatedActor | None:
    if not cookie or cookie.count(".") != 1:
        return None
    payload, signature = cookie.split(".")
    expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
    try:
        actual = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
        if not hmac.compare_digest(actual, expected):
            return None
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        email = claims.get("email")
        expires_at = claims.get("expiresAt")
        if not isinstance(email, str) or not isinstance(expires_at, (int, float)):
            return None
        if datetime.fromtimestamp(expires_at / 1000, tz=timezone.utc) <= datetime.now(timezone.utc):
            return None
        user = database.scalar(select(UserAccount).where(UserAccount.email == email.lower().strip()))
        if user is None or not user.is_active:
            return None
        from app.models.entities import Session

        active_session = database.scalar(
            select(Session).where(
                Session.user_id == user.id,
                Session.token_hash == hashlib.sha256(payload.encode()).hexdigest(),
                Session.expires_at > datetime.now(timezone.utc),
            )
        )
        if active_session is None:
            return None
        return AuthenticatedActor(identifier=user.email, role=user.role)
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def require_admin(
    actor: Annotated[AuthenticatedActor, Depends(get_current_actor)],
) -> AuthenticatedActor:
    if actor.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "insufficient_permissions", "message": "Admin access is required"},
        )
    return actor


def get_cluster_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ClusterClient:
    return create_cluster_client(settings)


