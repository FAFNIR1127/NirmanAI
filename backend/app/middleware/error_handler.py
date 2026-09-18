"""
backend/app/middleware/error_handler.py

Phase 9D — Global Exception & Error Handler Middleware.
Ensures standardized, sanitized JSON error responses across all FastAPI endpoints:
- Formats error payloads: {"error": true, "message": "...", "status_code": N}
- Catches HTTPExceptions (400, 404, 422, 429, 503)
- Intercepts RequestValidationErrors
- Intercepts unhandled Server Exceptions (500), recording tracebacks in internal logs
  while preventing sensitive stack traces from leaking to public HTTP responses.
"""

import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("nirman.errors")


async def http_exception_handler(request: Request, exc: HTTPException | StarletteHTTPException) -> JSONResponse:
    """Handle standard FastAPI/Starlette HTTP exceptions."""
    logger.warning(f"HTTP {exc.status_code} on {request.method} {request.url.path}: {exc.detail}")

    message = exc.detail if isinstance(exc.detail, str) else "HTTP Request Error"

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": message,
            "status_code": exc.status_code
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle Pydantic request validation errors (HTTP 422)."""
    errors = exc.errors()
    msg = errors[0].get("msg", "Invalid request parameters") if errors else "Invalid request body or query parameters"
    logger.warning(f"Validation Error 422 on {request.method} {request.url.path}: {errors}")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": True,
            "message": f"Invalid request parameters: {msg}",
            "status_code": 422
        }
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch unhandled server exceptions (HTTP 500) and mask tracebacks."""
    logger.error(f"Unhandled Exception 500 on {request.method} {request.url.path}: {exc}", exc_info=True)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": True,
            "message": "Internal server error occurred. Please try again or contact support.",
            "status_code": 500
        }
    )
