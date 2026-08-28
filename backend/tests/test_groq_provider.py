import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException
from app.ai.providers.groq_provider import GroqAnalyzerProvider
from app.schemas.candidate import CandidateEvidence, ExperienceItem
from app.ai.factory import get_ai_analyzer_provider
import app.ai.providers.groq_provider as groq_provider_module


def test_groq_provider_name():
    provider = GroqAnalyzerProvider()
    assert provider.name == "groq"


def test_factory_returns_configured_providers(monkeypatch):
    from app.core import config
    from app.ai.providers.gemini_provider import GeminiAnalyzerProvider

    monkeypatch.setattr(config.settings, "AI_ANALYZER_PROVIDER", "groq")
    p_groq = get_ai_analyzer_provider()
    assert isinstance(p_groq, GroqAnalyzerProvider)

    monkeypatch.setattr(config.settings, "AI_ANALYZER_PROVIDER", "gemini")
    p_gemini = get_ai_analyzer_provider()
    assert isinstance(p_gemini, GeminiAnalyzerProvider)


@pytest.mark.asyncio
async def test_groq_provider_missing_key_raises_503(monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "GROQ_API_KEY", "")
    provider = GroqAnalyzerProvider()
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
    assert "GROQ_API_KEY is not configured" in exc_info.value.detail


@pytest.mark.asyncio
async def test_groq_provider_timeout_raises_gateway_timeout(monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "GROQ_API_KEY", "mock_groq_test_key")

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=Exception("Request timed out after 60 seconds"))
    monkeypatch.setattr(groq_provider_module, "AsyncGroq", lambda *args, **kwargs: mock_client)

    provider = GroqAnalyzerProvider()
    evidence = CandidateEvidence(headline="Engineer", summary="Test")

    with pytest.raises(HTTPException) as exc_info:
        await provider.analyze(
            target_role="Software Engineer",
            target_company="Google",
            job_description="Need Python and TypeScript experience.",
            job_description_hash="hash123",
            candidate_evidence=evidence,
        )

    assert exc_info.value.status_code == 504
    assert "timed out after 60 seconds" in exc_info.value.detail
    assert "mock_groq_test_key" not in exc_info.value.detail


@pytest.mark.asyncio
async def test_groq_provider_rate_limit_raises_429(monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "GROQ_API_KEY", "mock_groq_test_key")

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=Exception("Rate limit reached for model (429)"))
    monkeypatch.setattr(groq_provider_module, "AsyncGroq", lambda *args, **kwargs: mock_client)

    provider = GroqAnalyzerProvider()
    evidence = CandidateEvidence(headline="Engineer", summary="Test")

    with pytest.raises(HTTPException) as exc_info:
        await provider.analyze(
            target_role="Software Engineer",
            target_company="Google",
            job_description="Need Python and TypeScript experience.",
            job_description_hash="hash123",
            candidate_evidence=evidence,
        )

    assert exc_info.value.status_code == 429
    assert "rate limit reached" in exc_info.value.detail.lower()
    assert "mock_groq_test_key" not in exc_info.value.detail


@pytest.mark.asyncio
async def test_groq_provider_invalid_key_raises_503(monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "GROQ_API_KEY", "mock_invalid_key")

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=Exception("401 invalid_api_key: Invalid API Key"))
    monkeypatch.setattr(groq_provider_module, "AsyncGroq", lambda *args, **kwargs: mock_client)

    provider = GroqAnalyzerProvider()
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
    assert "Invalid Groq API key" in exc_info.value.detail
    assert "mock_invalid_key" not in exc_info.value.detail


@pytest.mark.asyncio
async def test_groq_provider_malformed_json_raises_500(monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "GROQ_API_KEY", "mock_groq_test_key")

    mock_choice = MagicMock()
    mock_choice.message.content = "This is not valid JSON string"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    monkeypatch.setattr(groq_provider_module, "AsyncGroq", lambda *args, **kwargs: mock_client)

    provider = GroqAnalyzerProvider()
    evidence = CandidateEvidence(headline="Engineer", summary="Test")

    with pytest.raises(HTTPException) as exc_info:
        await provider.analyze(
            target_role="Software Engineer",
            target_company="Google",
            job_description="Need Python and TypeScript experience.",
            job_description_hash="hash123",
            candidate_evidence=evidence,
        )

    assert exc_info.value.status_code == 500
    assert "invalid JSON response format" in exc_info.value.detail


@pytest.mark.asyncio
async def test_groq_provider_successful_analysis(monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "GROQ_API_KEY", "mock_groq_test_key")
    monkeypatch.setattr(config.settings, "AI_ANALYZER_MODEL", "llama-3.3-70b-versatile")

    mock_json_content = json.dumps({
        "scoreBreakdown": {
            "relevance": 85,
            "keywords": 80,
            "metrics": 70,
            "formatting": 90,
        },
        "summaryFeedback": "Exceptional fit with deep experience in Python and FastAPI.",
        "matchingSkills": [
            {"name": "python", "context": "5 years building backend microservices"},
            {"name": "FastAPI", "context": "Designed high-throughput REST APIs"},
        ],
        "missingSkills": [
            {"name": "k8s", "priority": "High", "reason": "Kubernetes orchestration required"},
        ],
        "partialSkills": [
            {"name": "AWS", "note": "Has extensive GCP Cloud Run experience"},
        ],
    })

    mock_choice = MagicMock()
    mock_choice.message.content = mock_json_content
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    monkeypatch.setattr(groq_provider_module, "AsyncGroq", lambda *args, **kwargs: mock_client)

    provider = GroqAnalyzerProvider()
    evidence = CandidateEvidence(
        headline="Senior Backend Engineer",
        summary="Experienced Python engineer",
        experience=[
            ExperienceItem(
                role="Senior Engineer",
                company="Acme",
                bullets=["Built REST services in Python and FastAPI"],
            )
        ],
    )

    result = await provider.analyze(
        target_role="Senior Python Engineer",
        target_company="Stripe",
        job_description="Looking for Senior Python Engineer with FastAPI and Kubernetes skills.",
        job_description_hash="mock_hash_xyz",
        candidate_evidence=evidence,
    )

    # 1. Deterministic score verification:
    # 85*0.4 (34) + 80*0.3 (24) + 70*0.15 (10.5) + 90*0.15 (13.5) = 82.0 -> 82
    assert result.ats_score == 82
    assert result.score_breakdown.relevance == 85
    assert result.score_breakdown.keywords == 80
    assert result.score_breakdown.metrics == 70
    assert result.score_breakdown.formatting == 90

    # 2. Canonical skill normalization verification:
    matching_names = [s.name for s in result.matching_skills]
    assert "Python" in matching_names
    assert "FastAPI" in matching_names

    missing_names = [s.name for s in result.missing_skills]
    assert "Kubernetes" in missing_names  # "k8s" normalized to "Kubernetes"

    # 3. Metadata verification:
    assert result.metadata.provider == "groq"
    assert result.metadata.model == "llama-3.3-70b-versatile"
    assert result.metadata.job_description_hash == "mock_hash_xyz"
