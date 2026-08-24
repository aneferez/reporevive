"""Structured error codes, the ``AppError`` exception, and exception handlers.

Every error response follows the shape in PRD section 11::

    {"error": {"code": ..., "message": ..., "request_id": ...}}
"""

from __future__ import annotations

import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..models.schemas import ErrorDetail, ErrorResponse

logger = logging.getLogger("reporevive.errors")


# Suggested error codes from PRD section 11. Kept as plain constants so they
# read identically in code and in responses.
class ErrorCode:
    INVALID_REPOSITORY_URL = "INVALID_REPOSITORY_URL"
    REPOSITORY_NOT_FOUND = "REPOSITORY_NOT_FOUND"
    PRIVATE_REPOSITORY_UNSUPPORTED = "PRIVATE_REPOSITORY_UNSUPPORTED"
    REPOSITORY_TOO_LARGE = "REPOSITORY_TOO_LARGE"
    INVALID_ARCHIVE = "INVALID_ARCHIVE"
    ARCHIVE_TOO_LARGE = "ARCHIVE_TOO_LARGE"
    UNSAFE_ARCHIVE_ENTRY = "UNSAFE_ARCHIVE_ENTRY"
    ANALYSIS_NOT_FOUND = "ANALYSIS_NOT_FOUND"
    ANALYSIS_NOT_READY = "ANALYSIS_NOT_READY"
    AI_PROVIDER_UNAVAILABLE = "AI_PROVIDER_UNAVAILABLE"
    AI_QUOTA_EXCEEDED = "AI_QUOTA_EXCEEDED"
    RATE_LIMITED = "RATE_LIMITED"
    OWNER_TOKEN_INVALID = "OWNER_TOKEN_INVALID"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class AppError(Exception):
    """Domain error that maps cleanly onto the structured error response."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = HTTPStatus.BAD_REQUEST,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.headers = headers


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _error_response(
    status_code: int,
    code: str,
    message: str,
    request_id: str | None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    payload = ErrorResponse(
        error=ErrorDetail(code=code, message=message, request_id=request_id)
    )
    return JSONResponse(
        status_code=status_code, content=payload.model_dump(), headers=headers
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return _error_response(
            exc.status_code, exc.code, exc.message, _request_id(request), exc.headers
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Summarize without echoing full payloads (which may contain secrets).
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        message = first.get("msg", "Request validation failed")
        if loc:
            message = f"{message} ({loc})"
        return _error_response(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            ErrorCode.VALIDATION_ERROR,
            message,
            _request_id(request),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code = ErrorCode.INTERNAL_ERROR
        if exc.status_code == HTTPStatus.NOT_FOUND:
            code = ErrorCode.ANALYSIS_NOT_FOUND
        elif exc.status_code == HTTPStatus.TOO_MANY_REQUESTS:
            code = ErrorCode.RATE_LIMITED
        message = exc.detail if isinstance(exc.detail, str) else "Request failed"
        return _error_response(exc.status_code, code, message, _request_id(request))

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        # Log the traceback server-side; never leak internals to the client.
        logger.exception("Unhandled error: %s", exc)
        return _error_response(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            ErrorCode.INTERNAL_ERROR,
            "An unexpected error occurred.",
            _request_id(request),
        )
