from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as SQLAlchemySession

from app.core.dependencies import (
    AuthenticatedActor,
    get_cluster_client,
    get_current_actor,
    get_database_session,
    get_settings,
)
from app.core.config import Settings

from .schemas import ActorResponse, HealthResponse
from .discovery_schemas import (
    ClusterStatusResponse,
    NamespaceItem,
    NamespaceResponse,
    ResourceItem,
    ResourceResponse,
    ResourceType,
)
from app.kubernetes.client import ClusterClient

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    return HealthResponse(status="ok", service=settings.service_name)


@router.get("/auth/context", response_model=ActorResponse)
async def auth_context(
    actor: Annotated[AuthenticatedActor, Depends(get_current_actor)],
    _database: Annotated[SQLAlchemySession, Depends(get_database_session)],
) -> ActorResponse:
    return ActorResponse(identifier=actor.identifier, role=actor.role)


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
