from collections.abc import Iterator
import base64
import hashlib
import hmac
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session as SQLAlchemySession
from sqlalchemy import select

from app.core.config import Settings
from app.db.session import get_database_session as open_database_session
from app.models.entities import UserAccount, ClusterConnection
from app.kubernetes.client import ClusterClient, create_cluster_client


@dataclass(frozen=True)
class AuthenticatedActor:
    identifier: str
    role: str
    user_id: UUID = field(default_factory=uuid4)
    session_id: UUID = field(default_factory=uuid4)
    restricted: bool = False


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
        if user is None:
            return None
        if not user.is_active:
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
        return AuthenticatedActor(
            identifier=user.email,
            role=user.role,
            user_id=user.id,
            session_id=active_session.id,
            restricted=active_session.restricted,
        )
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
        return None
def get_cluster_client(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> ClusterClient:
    cluster_name = request.query_params.get("cluster") or settings.cluster_name
    row = database.scalar(select(ClusterConnection).where(ClusterConnection.name == cluster_name))
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "cluster_not_found", "message": "Cluster was not found"},
        )
    if row.status == "inactive":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "cluster_not_found", "message": "Cluster was not found"},
        )
    return create_cluster_client(settings, kubeconfig_content=row.kubeconfig_content, cluster_name=row.name)


