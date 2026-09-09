from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.schemas.common import err

log = get_logger(__name__)


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        rid = getattr(request.state, "request_id", None)
        log.warning(
            "api.app_error",
            code=exc.code.value,
            message=exc.message,
            path=request.url.path,
            request_id=rid,
            **exc.context,
        )
        return JSONResponse(
            status_code=exc.http_status,
            content=err(exc.code.value, exc.message, exc.context or None),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=err(
                "VALIDATION_ERROR",
                "Request validation failed",
                {"errors": exc.errors()},
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        rid = getattr(request.state, "request_id", str(uuid.uuid4()))
        log.error(
            "api.unhandled_exception",
            error=str(exc),
            error_type=type(exc).__name__,
            path=request.url.path,
            request_id=rid,
            exc_info=True,
        )
        detail = str(exc) if get_settings().debug else "An internal error occurred"
        return JSONResponse(
            status_code=500,
            content=err("INTERNAL_ERROR", detail, {"request_id": rid}),
        )
