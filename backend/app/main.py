import re
import time
import uuid
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Scope, Receive, Send

from app.core.config import settings
from app.core.logging import (
    setup_logging,
    get_logger,
    get_request_id,
    set_request_id,
    reset_request_id,
)
from app.api.router import api_v1_router
from app.api.v1.health import router as health_router
from app.services.resume_service import close_http_client
from app.ai.providers.groq_provider import close_groq_client
from app.ai.providers.nvidia_provider import close_nvidia_client
from app.mcp.mcp_server import mcp_app

# Initialize centralized structured logging
setup_logging(settings.LOG_LEVEL)
logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Application Startup
    logger.info(
        "Starting ResumeIQ AI Backend Engine",
        extra={
            "event": "startup",
            "environment": settings.ENVIRONMENT,
            "provider": settings.AI_ANALYZER_PROVIDER,
            "model": settings.AI_ANALYZER_MODEL,
        },
    )
    yield
    # Application Shutdown - Cleanly close persistent HTTP & AI connection pools
    logger.info("Shutting down ResumeIQ AI Backend Engine", extra={"event": "shutdown"})
    await close_http_client()
    await close_groq_client()
    await close_nvidia_client()


app = FastAPI(
    title="ResumeIQ AI Engine",
    description="Dedicated FastAPI Backend & AI ATS Analyzer Engine for ResumeIQ",
    version="0.1.0",
    docs_url="/docs" if settings.ENVIRONMENT == "development" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT == "development" else None,
    lifespan=lifespan,
)


def _sanitize_request_id(incoming: str | None) -> str:
    """Validates and sanitizes incoming X-Request-ID or generates a clean UUID4 identifier."""
    if not incoming:
        return f"req_{uuid.uuid4().hex}"
    cleaned = incoming.strip()
    if len(cleaned) < 1 or len(cleaned) > 128:
        return f"req_{uuid.uuid4().hex}"
    if not re.match(r"^[A-Za-z0-9_\-]+$", cleaned):
        return f"req_{uuid.uuid4().hex}"
    return cleaned


class CorrelationIdAndAccessMiddleware:
    """
    Middleware that:
    1. Extracts or generates a sanitized X-Request-ID correlation identifier.
    2. Injects the request ID into async contextvars for structured logging across threads/tasks.
    3. Measures request latency with monotonic clock and injects X-Request-ID and X-Response-Time headers.
    4. Emits structured JSON access logs upon request completion.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        # Extract incoming X-Request-ID
        headers = dict(scope.get("headers", []))
        incoming_req_id = None
        for k, v in headers.items():
            if k.lower() == b"x-request-id":
                try:
                    incoming_req_id = v.decode("latin1")
                except Exception:
                    incoming_req_id = None
                break

        req_id = _sanitize_request_id(incoming_req_id)
        token = set_request_id(req_id)

        # Initialize request state for fast lookup
        if "state" not in scope:
            scope["state"] = {}
        scope["state"]["request_id"] = req_id

        start_time = time.perf_counter()
        status_code_holder = [200]

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code_holder[0] = message.get("status", 200)
                resp_headers = MutableHeaders(scope=message)
                resp_headers["X-Request-ID"] = req_id
                duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
                resp_headers["X-Response-Time"] = f"{duration_ms}ms"
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            status_code = status_code_holder[0]
            path = scope.get("path", "")
            method = scope.get("method", "GET")

            # Structured access logging (skip noisy health pings if 200)
            if path != "/health" or status_code >= 400:
                log_level = (
                    logging.ERROR
                    if status_code >= 500
                    else logging.WARNING
                    if status_code >= 400
                    else logging.INFO
                )
                logger.log(
                    log_level,
                    f"{method} {path} HTTP {status_code} - {duration_ms}ms",
                    extra={
                        "event": "http_request",
                        "method": method,
                        "path": path,
                        "status_code": status_code,
                        "duration_ms": duration_ms,
                        "request_id": req_id,
                    },
                )
            reset_request_id(token)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            await send(message)

        await self.app(scope, receive, send_wrapper)


# Configure Middleware Stack
app.add_middleware(CorrelationIdAndAccessMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# Global Request Validation Error Handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    req_id = getattr(request.state, "request_id", None) or get_request_id()
    errors = exc.errors()
    formatted = [
        f"{'.'.join(str(loc) for loc in err.get('loc', []))}: {err.get('msg', 'Invalid')}"
        for err in errors
    ]
    msg = f"Validation failed: {', '.join(formatted)}"
    logger.warning(
        f"Validation error on {request.method} {request.url.path}: {msg}",
        extra={
            "event": "validation_error",
            "method": request.method,
            "path": request.url.path,
            "status_code": 400,
            "request_id": req_id,
        },
    )
    headers = {"X-Request-ID": req_id} if req_id else {}
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": msg, "request_id": req_id},
        headers=headers,
    )


# Global Unhandled Exception Handler
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    req_id = getattr(request.state, "request_id", None) or get_request_id()
    logger.error(
        f"Unhandled server exception on {request.method} {request.url.path}: {str(exc)}",
        exc_info=exc,
        extra={
            "event": "unhandled_exception",
            "method": request.method,
            "path": request.url.path,
            "status_code": 500,
            "request_id": req_id,
        },
    )
    headers = {"X-Request-ID": req_id} if req_id else {}
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error. Please retry your request or contact support.",
            "request_id": req_id,
        },
        headers=headers,
    )


# Mount Routers
app.include_router(health_router, prefix="")  # Direct GET /health and /health/ready
app.include_router(api_v1_router, prefix="/api")  # /api/v1/...

# Mount MCP server (Streamable HTTP transport, stateless)
app.mount("/mcp", mcp_app)


@app.get("/", tags=["System"])
async def root():
    return {
        "service": "ResumeIQ AI Backend",
        "status": "operational",
        "version": "0.1.0",
    }
