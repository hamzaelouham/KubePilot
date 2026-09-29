import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.marketplace import router as marketplace_router
from app.api.v1.helm_releases import router as helm_releases_router
from app.api.v1.helm_repositories import router as helm_repositories_router
from app.api.v1.resource_management import router as resource_management_router
from app.api.v1.assistant import router as assistant_router
from app.api.v1.agents import router as agents_router
from app.api.v1.settings import router as settings_router
from app.api.v1.integrations import router as integrations_router
from app.kubernetes.resource_management import ResourceManagementError
from app.api.v1.routes import router as v1_router
from app.api.v1.schemas import ErrorResponse
from app.api.v1.users import router as users_router
from app.core.config import ConfigurationError, Settings
from app.db.session import create_session_factory
from app.jobs.worker import requeue_running_deliveries, requeue_running_jobs, _worker_loop
from app.models.entities import ClusterConnection
from app.kubernetes.client import (
    ClusterClientError,
    ClusterForbiddenError,
    ClusterUnavailableError,
    ResourceNotFoundError,
)

logger = logging.getLogger(__name__)


def _seed_default_cluster(settings: Settings) -> None:
    session_factory = create_session_factory(settings)
    database = session_factory()
    try:
        existing = database.scalar(
            select(ClusterConnection).where(ClusterConnection.name == settings.cluster_name)
        )
        if existing is not None:
            return
        database.add(
            ClusterConnection(
                name=settings.cluster_name,
                endpoint="in-cluster",
                kubeconfig_ref="in-cluster",
                status="active",
            )
        )
        database.commit()
    except Exception as error:  # noqa: BLE001
        logger.warning("Skipped default cluster seeding: %s", error)
    finally:
        database.close()


def _requeue_orphaned_jobs(settings: Settings) -> None:
    database = create_session_factory(settings)()
    try:
        requeue_running_jobs(database)
        requeue_running_deliveries(database)
    except Exception as error:  # noqa: BLE001
        logger.warning("Skipped installation job requeue: %s", error)
    finally:
        database.close()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = Settings.from_env()
    app.state.settings = settings
    _seed_default_cluster(settings)
    _requeue_orphaned_jobs(settings)

    worker_task = None
    if settings.worker_enabled:
        worker_task = asyncio.create_task(_worker_loop(settings))
    try:
        yield
    finally:
        if worker_task is not None:
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass


def create_app() -> FastAPI:
    app = FastAPI(
        title="KubePilot API",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.exception_handler(ResourceManagementError)
    async def resource_management_error_handler(
        _request: Request, exception: ResourceManagementError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exception.status,
            content=ErrorResponse(code=exception.code, message=exception.message).model_dump(),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        _request: Request, exception: StarletteHTTPException
    ) -> JSONResponse:
        if isinstance(exception.detail, dict):
            code = str(exception.detail.get("code", "http_error"))
            message = str(exception.detail.get("message", "Request failed"))
        else:
            code = "http_error"
            message = "Request failed"
        return JSONResponse(
            status_code=exception.status_code,
            content=ErrorResponse(code=code, message=message).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request, _exception: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                code="validation_error", message="Request validation failed"
            ).model_dump(),
        )

    @app.exception_handler(ConfigurationError)
    async def configuration_exception_handler(
        _request: Request, _exception: ConfigurationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content=ErrorResponse(
                code="service_unavailable", message="Service configuration is unavailable"
            ).model_dump(),
        )

    @app.exception_handler(ClusterForbiddenError)
    async def cluster_forbidden_handler(
        _request: Request, _exception: ClusterForbiddenError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content=ErrorResponse(
                code="cluster_forbidden", message="Kubernetes access is forbidden"
            ).model_dump(),
        )

    @app.exception_handler(ClusterUnavailableError)
    async def cluster_unavailable_handler(
        _request: Request, exception: ClusterUnavailableError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content=ErrorResponse(
                code="cluster_unavailable", message=str(exception)
            ).model_dump(),
        )

    @app.exception_handler(ClusterClientError)
    async def cluster_error_handler(
        _request: Request, _exception: ClusterClientError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content=ErrorResponse(
                code="cluster_error", message="Kubernetes request failed"
            ).model_dump(),
        )

    @app.exception_handler(ResourceNotFoundError)
    async def resource_not_found_handler(
        _request: Request, _exception: ResourceNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                code="resource_not_found", message="Kubernetes resource was not found"
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def unexpected_exception_handler(
        _request: Request, exception: Exception
    ) -> JSONResponse:
        logger.exception("Unexpected API failure: %s", type(exception).__name__)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                code="internal_error", message="An unexpected error occurred"
            ).model_dump(),
        )

    app.include_router(v1_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(marketplace_router, prefix="/api/v1")
    app.include_router(helm_releases_router, prefix="/api/v1")
    app.include_router(helm_repositories_router, prefix="/api/v1")
    app.include_router(resource_management_router, prefix="/api/v1")
    app.include_router(assistant_router, prefix="/api/v1")
    app.include_router(agents_router, prefix="/api/v1")
    app.include_router(settings_router, prefix="/api/v1")
    app.include_router(integrations_router, prefix="/api/v1")
    return app


app = create_app()
