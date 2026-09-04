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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Application Startup
    yield
    # Application Shutdown - Cleanly close persistent HTTP & AI connection pools
    await close_http_client()
    await close_groq_client()


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


@app.get("/", tags=["System"])
async def root():
    return {
        "service": "ResumeIQ AI Backend",
        "status": "operational",
        "version": "0.1.0",
    }
