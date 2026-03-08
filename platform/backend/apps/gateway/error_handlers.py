"""Centralized error handlers — maps AppError hierarchy to HTTP responses."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from packages.core.context import get_request_id
from packages.core.errors import AppError, RateLimitError
from packages.observability.setup import get_logger

logger = get_logger("gateway.errors")


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        request_id = get_request_id()
        logger.warning(
            "app_error",
            error_code=exc.error_code,
            message=exc.message,
            context=exc.context,
            request_id=request_id,
        )
        headers = {}
        if isinstance(exc, RateLimitError):
            headers["Retry-After"] = str(exc.retry_after_seconds)

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "context": exc.context,
                },
                "request_id": request_id,
            },
            headers=headers,
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = get_request_id()
        logger.exception("unhandled_error", request_id=request_id)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An internal error occurred",
                },
                "request_id": request_id,
            },
        )
