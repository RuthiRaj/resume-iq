import pytest
from fastapi import HTTPException
from app.ai.providers.gemini_provider import GeminiAnalyzerProvider
from app.core.config import Settings


def test_gemini_provider_name():
    provider = GeminiAnalyzerProvider()
    assert provider.name == "gemini"


@pytest.mark.asyncio
async def test_gemini_provider_missing_key_raises_503(monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "GEMINI_API_KEY", "")
    provider = GeminiAnalyzerProvider()

    from app.schemas.candidate import CandidateEvidence

    evidence = CandidateEvidence(headline="Engineer", summary="Test")

    with pytest.raises(HTTPException) as exc_info:
        await provider.analyze(
            target_role="Software Engineer",
            target_company="Google",
            job_description="We need a strong software engineer with python and typescript.",
            job_description_hash="abcdef",
            candidate_evidence=evidence,
        )

    assert exc_info.value.status_code == 503
    assert "GEMINI_API_KEY is not configured" in exc_info.value.detail
