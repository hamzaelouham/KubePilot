import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.routes import router as v1_router
from app.api.v1.schemas import ErrorResponse
from app.core.config import ConfigurationError, Settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.settings = Settings.from_env()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="KubePilot API",
        version="0.1.0",
        lifespan=lifespan,
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
    return app


app = create_app()
