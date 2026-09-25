from typing import List, Dict, Any
from fastapi import APIRouter, Response, status
from app.core.config import settings

router = APIRouter()


@router.get("/health", tags=["System"])
async def health_check():
    """Lightweight system liveness probe."""
    return {
        "status": "healthy",
        "service": "resumeiq-backend",
        "environment": settings.ENVIRONMENT,
        "provider": settings.AI_ANALYZER_PROVIDER,
        "model": settings.AI_ANALYZER_MODEL,
        "provider_chain": settings.AI_PROVIDER_CHAIN,
    }


@router.get("/health/ready", tags=["System"])
async def readiness_check(response: Response):
    """
    Deterministic system readiness probe.
    Validates essential configuration, auth JWKS client readiness,
    and HTTP connection pool readiness without executing expensive AI calls.
    """
    from app.core.auth import get_jwks_client
    from app.services.resume_service import get_http_client

    checks: Dict[str, str] = {}
    is_ready = True

    # 1. Config Validation
    if not settings.FIREBASE_PROJECT_ID or not settings.AI_PROVIDER_CHAIN:
        checks["config"] = "misconfigured"
        is_ready = False
    else:
        checks["config"] = "ok"

    # 2. Auth JWKS Client Readiness
    try:
        jwks = get_jwks_client()
        if jwks is not None:
            checks["auth_jwks"] = "ok"
        else:
            checks["auth_jwks"] = "failed"
            is_ready = False
    except Exception:
        checks["auth_jwks"] = "failed"
        is_ready = False

    # 3. HTTP Client Connection Pool Readiness
    try:
        client = get_http_client()
        if client is not None and not client.is_closed:
            checks["http_pool"] = "ok"
        else:
            checks["http_pool"] = "closed"
            is_ready = False
    except Exception:
        checks["http_pool"] = "failed"
        is_ready = False

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if is_ready else "not_ready",
        "service": "resumeiq-backend",
        "environment": settings.ENVIRONMENT,
        "checks": checks,
    }


@router.get("/health/providers", tags=["System"])
async def health_providers_check() -> List[Dict[str, Any]]:
    """
    Runs a 1-token health ping with 5s timeout for each provider.
    Returns status, ok, latency_ms, and error without leaking any key values.
    """
    from app.ai.providers.groq_provider import GroqAnalyzerProvider
    from app.ai.providers.gemini_provider import GeminiAnalyzerProvider
    from app.ai.providers.nvidia_provider import NvidiaAnalyzerProvider

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
