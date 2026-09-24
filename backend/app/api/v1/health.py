from typing import List, Dict, Any
from fastapi import APIRouter
from app.core.config import settings
from app.ai.providers.groq_provider import GroqAnalyzerProvider
from app.ai.providers.gemini_provider import GeminiAnalyzerProvider
from app.ai.providers.nvidia_provider import NvidiaAnalyzerProvider

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
        "provider_chain": settings.AI_PROVIDER_CHAIN,
    }


@router.get("/health/providers", tags=["System"])
async def health_providers_check() -> List[Dict[str, Any]]:
    """
    Runs a 1-token health ping with 5s timeout for each provider.
    Returns status, ok, latency_ms, and error without leaking any key values.
    """
    providers = [
        GroqAnalyzerProvider(),
        GeminiAnalyzerProvider(),
        NvidiaAnalyzerProvider(),
    ]
    results = []
    for p in providers:
        res = await p.ping(timeout=5.0)
        results.append(res)
    return results
