# ruff: noqa: BLE001
import logging
import time

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.redis_client import redis_client

# Standard English docstring.
"""Middleware and exception handling configuration module.
Sets up request logging, CORS, rate limiting, and unified exception formats.
"""

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Standard English docstring: Middleware to log all incoming HTTP requests and processing time."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start_time = time.time()
        client_host = request.client.host if request.client else "unknown"

        # Hinglish explanation: Processing start time and request path target ko log karo.
        logger.info(
            f"Incoming request: {request.method} {request.url.path} from {client_host}"
        )

        try:
            response = await call_next(request)
            process_time = (time.time() - start_time) * 1000
            # Hinglish explanation: Processing successfully finish hone par code and time report karo.
            logger.info(
                f"Completed request: {request.method} {request.url.path} - "
                f"Status: {response.status_code} - Duration: {process_time:.2f}ms"
            )
            # Hinglish explanation: Response headers mein debugging and performance logs track karne ke liye header attach karo.
            response.headers["X-Process-Time-Ms"] = f"{process_time:.2f}"
            return response
        except Exception as e:
            process_time = (time.time() - start_time) * 1000
            logger.error(
                f"Failed request: {request.method} {request.url.path} - "
                f"Error: {e!s} - Duration: {process_time:.2f}ms"
            )
            raise


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """Standard English docstring: Middleware to enforce IP/User API rate limits."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path

        # Hinglish explanation: Health check endpoints aur Swagger UI/Docs ko limit criteria se exclude karo.
        if (
            path.startswith(("/docs", "/redoc", "/openapi.json")) or path == "/health" or path == f"/api/{settings.API_VERSION}/health"
        ):
            return await call_next(request)

        client_host = request.client.host if request.client else "unknown"
        # Hinglish explanation: Har separate network host IP ke liye user rate limit counters configure kiya hai.
        key = f"rate_limit:{client_host}"

        try:
            count = await redis_client.incr(key)
            if count == 1:
                # Hinglish explanation: Expiry 60 seconds (1 minute) ka set kar rahe hain.
                await redis_client.expire(key, 60)

            limit = settings.RATE_LIMIT_REQUESTS_PER_MINUTE
            if count > limit:
                # Hinglish explanation: Too Many Requests response return karo clean structures mein.
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "TOO_MANY_REQUESTS",
                            "message": "Rate limit exceeded. Please try again later.",
                        }
                    },
                )
        except Exception as e:
            logger.error(f"Rate limiting check failed: {e}")
            # Hinglish explanation: Rate limit module error aane par main service request fail open strategy follow karegi.

        return await call_next(request)


# ── Exception Handlers ────────────────────────────────────────────────────────


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    # Hinglish explanation: Custom validation / unauthorized exception details handle karke standard formatting mapping return karega.
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


async def validation_exception_handler(
        request: Request, exc: RequestValidationError
) -> JSONResponse:
    # Hinglish explanation: Query parameter validation, request fields data mismatch, or Pydantic errors parsing format.
    details = exc.errors()
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Validation failed",
                "details": details,
            }
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Hinglish explanation: Generic standard handling framework base code.
    logger.exception(f"Unhandled system error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred. Please contact system support.",
            }
        },
    )


def setup_middleware(app: FastAPI) -> None:
    # Hinglish explanation: CORS options setup from configuration settings.
    origins = settings.CORS_ORIGINS
    if isinstance(origins, str):
        origins = [origins]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Hinglish explanation: Application logic request profiling and metrics middlewares.
    app.add_middleware(RateLimitingMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    # Hinglish explanation: FastAPI validation errors, custom business failures, and raw code exception configuration mapping.
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
