import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session as SQLAlchemySession

from app.core.dependencies import (
    AuthenticatedActor,
    get_cluster_client,
    get_current_actor,
    get_database_session,
    get_settings,
)
from app.core.config import Settings
from app.models.entities import Session, UserAccount

from .schemas import ActorResponse, HealthResponse
from .discovery_schemas import (
    ClusterStatusResponse,
    NamespaceItem,
    NamespaceResponse,
    ResourceItem,
    ResourceResponse,
    ResourceType,
)
from .auth_schemas import LoginRequest, LoginResponse
from app.kubernetes.client import ClusterClient

router = APIRouter()


def _password_hash(password: str) -> str:
    salt = hashlib.sha256(b"kubepilot-password-salt").digest()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
    return "pbkdf2_sha256$120000$" + digest.hex()


def _signed_cookie(email: str, expires_at: int, secret: str) -> tuple[str, str]:
    payload = base64.urlsafe_b64encode(
        json.dumps({"email": email, "expiresAt": expires_at}, separators=(",", ":")).encode()
    ).decode().rstrip("=")
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
    signature_text = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    return f"{payload}.{signature_text}", hashlib.sha256(payload.encode()).hexdigest()


@router.get("/health", response_model=HealthResponse)
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    return HealthResponse(status="ok", service=settings.service_name)


@router.get("/auth/context", response_model=ActorResponse)
async def auth_context(
    actor: Annotated[AuthenticatedActor, Depends(get_current_actor)],
    _database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> ActorResponse:
    return ActorResponse(identifier=actor.identifier, role=actor.role)


@router.post("/auth/login", response_model=LoginResponse)
def login(
    credentials: LoginRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> LoginResponse:
    if credentials.email.strip().lower() != settings.admin_email or credentials.password != settings.admin_password:
        raise HTTPException(status_code=401, detail={"code": "authentication_required", "message": "Authentication is required"})
    user = database.scalar(select(UserAccount).where(UserAccount.email == settings.admin_email))
    if user is None:
        user = UserAccount(email=settings.admin_email, password_hash=_password_hash(credentials.password), role="admin")
        database.add(user)
        database.flush()
    expires_at = int((time.time() + 60 * 60 * 12) * 1000)
    cookie, token_hash = _signed_cookie(settings.admin_email, expires_at, settings.auth_secret)
    database.add(Session(user_id=user.id, token_hash=token_hash, expires_at=datetime.fromtimestamp(expires_at / 1000, tz=timezone.utc)))
    database.commit()
    return LoginResponse(cookie=cookie, expires_at=expires_at)


@router.get("/cluster/status", response_model=ClusterStatusResponse)
def cluster_status(
    _actor: Annotated[AuthenticatedActor, Depends(get_current_actor)],
    cluster: Annotated[ClusterClient, Depends(get_cluster_client)],
) -> ClusterStatusResponse:
    cluster.namespaces()
    return ClusterStatusResponse(status="connected", cluster=cluster.cluster_name)


@router.get("/cluster/namespaces", response_model=NamespaceResponse)
def cluster_namespaces(
    _actor: Annotated[AuthenticatedActor, Depends(get_current_actor)],
    cluster: Annotated[ClusterClient, Depends(get_cluster_client)],
) -> NamespaceResponse:
    return NamespaceResponse(
        items=[NamespaceItem(name=name, status=status) for name, status in cluster.namespaces()]
    )


@router.get("/cluster/resources/{resource_type}", response_model=ResourceResponse)
def cluster_resources(
    resource_type: ResourceType,
    _actor: Annotated[AuthenticatedActor, Depends(get_current_actor)],
    cluster: Annotated[ClusterClient, Depends(get_cluster_client)],
    namespace: str | None = None,
) -> ResourceResponse:
    if resource_type == "nodes" and namespace is not None:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_namespace_scope", "message": "Nodes are cluster-scoped"},
        )
    return ResourceResponse(
        items=[
            ResourceItem(
                cluster=item.cluster,
                namespace=item.namespace,
                kind=item.kind,
                name=item.name,
                status=item.status,
            )
            for item in cluster.resources(resource_type, namespace)
        ]
    )
