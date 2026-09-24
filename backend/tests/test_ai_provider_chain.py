import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
import httpx

from app.core import config
from app.ai.factory import (
    get_ai_analyzer_provider,
    create_provider_by_name,
    ConfigError,
)
from app.ai.providers.groq_provider import GroqAnalyzerProvider
from app.ai.providers.gemini_provider import GeminiAnalyzerProvider
from app.ai.providers.nvidia_provider import NvidiaAnalyzerProvider
from app.ai.fallback_provider import FallbackProvider
from app.schemas.candidate import CandidateEvidence
from app.schemas.analyze import AnalyzeResponse, ScoreBreakdown, AnalysisMetadata


def test_nvidia_provider_name():
    provider = NvidiaAnalyzerProvider()
    assert provider.name == "nvidia"


def test_factory_resolves_all_providers(monkeypatch):
    monkeypatch.setattr(config.settings, "AI_ANALYZER_PROVIDER", "groq")
    assert isinstance(get_ai_analyzer_provider(), GroqAnalyzerProvider)

    monkeypatch.setattr(config.settings, "AI_ANALYZER_PROVIDER", "gemini")
    assert isinstance(get_ai_analyzer_provider(), GeminiAnalyzerProvider)

    monkeypatch.setattr(config.settings, "AI_ANALYZER_PROVIDER", "nvidia")
    assert isinstance(get_ai_analyzer_provider(), NvidiaAnalyzerProvider)

    monkeypatch.setattr(config.settings, "AI_ANALYZER_PROVIDER", "fallback")
    assert isinstance(get_ai_analyzer_provider(), FallbackProvider)


def test_factory_raises_config_error_on_unknown_provider(monkeypatch):
    monkeypatch.setattr(config.settings, "AI_ANALYZER_PROVIDER", "unsupported_provider_xyz")
    with pytest.raises(ConfigError) as exc_info:
        get_ai_analyzer_provider()
    assert "Unknown AI provider 'unsupported_provider_xyz'" in str(exc_info.value)

    with pytest.raises(ConfigError) as exc_info2:
        create_provider_by_name("unknown_llm")
    assert "Unknown AI provider 'unknown_llm'" in str(exc_info2.value)


@pytest.mark.asyncio
async def test_nvidia_provider_missing_key_raises_503(monkeypatch):
    monkeypatch.setattr(config.settings, "NVIDIA_API_KEY", "")
    provider = NvidiaAnalyzerProvider()
    evidence = CandidateEvidence(headline="Engineer", summary="Test")

    with pytest.raises(HTTPException) as exc_info:
        await provider.analyze(
            target_role="Software Engineer",
            target_company="Google",
            job_description="Need Python and TypeScript experience.",
            job_description_hash="hash123",
            candidate_evidence=evidence,
        )

    assert exc_info.value.status_code == 503
    assert "NVIDIA_API_KEY is not configured" in exc_info.value.detail


@pytest.mark.asyncio
async def test_nvidia_provider_timeout_mapping(monkeypatch):
    monkeypatch.setattr(config.settings, "NVIDIA_API_KEY", "mock_nvidia_test_key")
    provider = NvidiaAnalyzerProvider()
    evidence = CandidateEvidence(headline="Engineer", summary="Test")

    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Read timed out"))
    monkeypatch.setattr("app.ai.providers.nvidia_provider.get_shared_nvidia_client", lambda: mock_client)

    with pytest.raises(HTTPException) as exc_info:
        await provider.analyze(
            target_role="Software Engineer",
            target_company="NVIDIA",
            job_description="High-performance computing with C++ and CUDA.",
            job_description_hash="hash123",
            candidate_evidence=evidence,
        )

    assert exc_info.value.status_code == 504
    assert "timed out after 60 seconds" in exc_info.value.detail


@pytest.mark.asyncio
async def test_nvidia_provider_429_rate_limit_mapping(monkeypatch):
    monkeypatch.setattr(config.settings, "NVIDIA_API_KEY", "mock_nvidia_test_key")
    provider = NvidiaAnalyzerProvider()
    evidence = CandidateEvidence(headline="Engineer", summary="Test")

    mock_response = MagicMock(status_code=429, text="Rate limit exceeded")
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    monkeypatch.setattr("app.ai.providers.nvidia_provider.get_shared_nvidia_client", lambda: mock_client)

    with pytest.raises(HTTPException) as exc_info:
        await provider.analyze(
            target_role="Software Engineer",
            target_company="NVIDIA",
            job_description="High-performance computing with C++ and CUDA.",
            job_description_hash="hash123",
            candidate_evidence=evidence,
        )

    assert exc_info.value.status_code == 429
    assert "rate limit reached" in exc_info.value.detail


@pytest.mark.asyncio
async def test_fallback_provider_order_success(monkeypatch):
    """Fallback provider tries provider 1; if it fails with 504/429/5xx, it falls back to provider 2."""
    p1 = MagicMock()
    p1.name = "mock_p1"
    p1.analyze = AsyncMock(side_effect=HTTPException(status_code=504, detail="Service timed out"))

    mock_success_response = AnalyzeResponse(
        ats_score=85,
        score_breakdown=ScoreBreakdown(relevance=80, keywords=90, metrics=85, formatting=85),
        summary_feedback="Candidate has strong match.",
        matching_skills=[],
        missing_skills=[],
        partial_skills=[],
        metadata=AnalysisMetadata(
            provider="mock_p2",
            model="mock-model",
            analyzed_at="2026-09-21T00:00:00Z",
            job_description_hash="abc",
            target_role="Software Engineer",
            target_company="Google",
        ),
    )

    p2 = MagicMock()
    p2.name = "mock_p2"
    p2.analyze = AsyncMock(return_value=mock_success_response)

    fallback = FallbackProvider(providers=[p1, p2])
    evidence = CandidateEvidence(headline="Engineer", summary="Test")

    result = await fallback.analyze(
        target_role="Software Engineer",
        target_company="Google",
        job_description="Python experience required.",
        job_description_hash="abc",
        candidate_evidence=evidence,
    )

    assert result.ats_score == 85
    assert result.metadata.provider == "mock_p2"
    p1.analyze.assert_awaited_once()
    p2.analyze.assert_awaited_once()


@pytest.mark.asyncio
async def test_fallback_provider_skips_missing_key(monkeypatch):
    """FallbackProvider automatically skips providers with empty or placeholder keys."""
    monkeypatch.setattr(config.settings, "GROQ_API_KEY", "")
    monkeypatch.setattr(config.settings, "GEMINI_API_KEY", "valid_gemini_key")
    monkeypatch.setattr(config.settings, "NVIDIA_API_KEY", "")
    monkeypatch.setattr(config.settings, "AI_PROVIDER_CHAIN", "groq,gemini,nvidia")

    fallback = FallbackProvider()
    # Only Gemini should be in the active providers list
    assert len(fallback.providers) == 1
    assert isinstance(fallback.providers[0], GeminiAnalyzerProvider)


@pytest.mark.asyncio
async def test_fallback_provider_no_fallback_on_validation_error(monkeypatch):
    """FallbackProvider must NOT fall back when a validation or client error (400) occurs."""
    p1 = MagicMock()
    p1.name = "mock_p1"
    p1.analyze = AsyncMock(side_effect=ValueError("Invalid resume schema format"))

    p2 = MagicMock()
    p2.name = "mock_p2"
    p2.analyze = AsyncMock()

    fallback = FallbackProvider(providers=[p1, p2])
    evidence = CandidateEvidence(headline="Engineer", summary="Test")

    with pytest.raises(ValueError) as exc_info:
        await fallback.analyze(
            target_role="Software Engineer",
            target_company="Google",
            job_description="Python experience required.",
            job_description_hash="abc",
            candidate_evidence=evidence,
        )

    assert "Invalid resume schema format" in str(exc_info.value)
    p1.analyze.assert_awaited_once()
    p2.analyze.assert_not_awaited()


@pytest.mark.asyncio
async def test_fallback_provider_no_fallback_on_400_bad_request(monkeypatch):
    """FallbackProvider must NOT fall back on HTTP 400 Bad Request."""
    p1 = MagicMock()
    p1.name = "mock_p1"
    p1.analyze = AsyncMock(side_effect=HTTPException(status_code=400, detail="Malformed prompt"))

    p2 = MagicMock()
    p2.name = "mock_p2"
    p2.analyze = AsyncMock()

    fallback = FallbackProvider(providers=[p1, p2])
    evidence = CandidateEvidence(headline="Engineer", summary="Test")

    with pytest.raises(HTTPException) as exc_info:
        await fallback.analyze(
            target_role="Software Engineer",
            target_company="Google",
            job_description="Python experience required.",
            job_description_hash="abc",
            candidate_evidence=evidence,
        )

    assert exc_info.value.status_code == 400
    p1.analyze.assert_awaited_once()
    p2.analyze.assert_not_awaited()


@pytest.mark.asyncio
async def test_health_providers_endpoint(async_client):
    """Test GET /api/v1/health/providers returns list of {name, ok, latency_ms, error} without secrets."""
    response = await async_client.get("/api/v1/health/providers")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 3

    provider_names = [p["name"] for p in data]
    assert "groq" in provider_names
    assert "gemini" in provider_names
    assert "nvidia" in provider_names

    for item in data:
        assert "name" in item
        assert "ok" in item
        assert "latency_ms" in item
        assert "error" in item
        # Verify no secret leakage
        raw_str = str(item)
        assert "key" not in raw_str.lower() or "not configured" in raw_str.lower() or "api key" in raw_str.lower()
