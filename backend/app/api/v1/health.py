from fastapi import APIRouter
from app.core.config import settings

router = APIRouter()


@router.get("/health", tags=["System"])
async def health_check():
    """System health check endpoint."""
    return {
        "status": "healthy",
        "service": "resumeiq-backend",
        "environment": settings.ENVIRONMENT,
        "provider": settings.AI_ANALYZER_PROVIDER,
        "model": settings.AI_ANALYZER_MODEL,
    }
