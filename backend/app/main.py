from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.core.config import settings
from app.api.router import api_v1_router
from app.api.v1.health import router as health_router
from app.services.resume_service import close_http_client
from app.ai.providers.groq_provider import close_groq_client
from app.ai.providers.nvidia_provider import close_nvidia_client
from app.mcp.mcp_server import mcp_app


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Application Startup
    yield
    # Application Shutdown - Cleanly close persistent HTTP & AI connection pools
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

# Configure CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Scope, Receive, Send


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


app.add_middleware(SecurityHeadersMiddleware)

# Global Request Validation Error Handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    formatted = [
        f"{'.'.join(str(loc) for loc in err.get('loc', []))}: {err.get('msg', 'Invalid')}"
        for err in errors
    ]
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": f"Validation failed: {', '.join(formatted)}"},
    )


# Mount Routers
app.include_router(health_router, prefix="")  # Direct GET /health
app.include_router(api_v1_router, prefix="/api")  # /api/v1/...

# Mount MCP server (Streamable HTTP transport, stateless)
# AI agents connect via: POST /mcp with Authorization: Bearer <Firebase_ID_Token>
app.mount("/mcp", mcp_app)


@app.get("/", tags=["System"])
async def root():
    return {
        "service": "ResumeIQ AI Backend",
        "status": "operational",
        "version": "0.1.0",
    }
