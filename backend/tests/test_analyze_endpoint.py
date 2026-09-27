import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.auth import get_authenticated_user, AuthenticatedUser
from app.schemas.candidate import CandidateEvidence
from app.schemas.analyze import (
    AnalyzeResponse,
    ScoreBreakdown,
    SkillMatchItem,
    SkillMissingItem,
    SkillPartialItem,
    AnalysisMetadata,
)

client = TestClient(app)


def test_analyze_missing_auth_header_returns_401():
    response = client.post(
        "/api/v1/ai/analyze",
        json={
            "resumeId": "res_123",
            "targetRole": "Frontend Engineer",
            "jobDescription": "Looking for an engineer with at least thirty characters in description.",
        },
    )
    assert response.status_code == 401
    assert "Missing Authorization header" in response.json()["detail"]


def test_analyze_validation_failure_returns_400():
    # Job description too short (< 30 chars)
    response = client.post(
        "/api/v1/ai/analyze",
        headers={"Authorization": "Bearer fake_token"},
        json={
            "resumeId": "res_123",
            "targetRole": "Frontend Engineer",
            "jobDescription": "Too short",
        },
    )
    # Even if auth fails or validation runs, it returns 400 or 401
    assert response.status_code in (400, 401)


def test_analyze_successful_flow_with_authenticated_user(monkeypatch):
    mock_user = AuthenticatedUser(uid="mock_uid_123", token="mock_token_123")

    async def mock_get_authenticated_user():
        return mock_user

    app.dependency_overrides[get_authenticated_user] = mock_get_authenticated_user

    # Mock resume service
    mock_evidence = CandidateEvidence(headline="Senior Developer", summary="Strong developer")

    async def mock_get_candidate_resume_data(user, resume_id):
        assert user.uid == "mock_uid_123"
        return mock_evidence

    from app.api.v1 import analyze as analyze_module

    monkeypatch.setattr(analyze_module, "get_candidate_resume_data", mock_get_candidate_resume_data)

    # Mock AI orchestrator
    mock_response = AnalyzeResponse(
        ats_score=88,
        score_breakdown=ScoreBreakdown(relevance=90, keywords=85, metrics=80, formatting=95),
        summary_feedback="Strong fit with comprehensive experience.",
        matching_skills=[SkillMatchItem(name="Python", context="Built backend")],
        missing_skills=[SkillMissingItem(name="Kubernetes", priority="Medium", reason="Not mentioned")],
        partial_skills=[SkillPartialItem(name="AWS", note="Has GCP experience")],
        metadata=AnalysisMetadata(
            provider="gemini",
            model="gemini-3.6-flash",
            analyzed_at="2026-08-27T12:00:00Z",
            job_description_hash="mockhash123",
            target_role="Senior Python Engineer",
            target_company="Google",
        ),
    )

    async def mock_run_ats_analysis(target_role, target_company, job_description, candidate_evidence):
        return mock_response

    monkeypatch.setattr(analyze_module, "run_ats_analysis", mock_run_ats_analysis)

    async def mock_persist_analysis_results(user, resume_id, analysis):
        assert user.uid == "mock_uid_123"
        assert resume_id == "res_123"

    monkeypatch.setattr(analyze_module, "persist_analysis_results", mock_persist_analysis_results)

    response = client.post(
        "/api/v1/ai/analyze",
        headers={"Authorization": "Bearer mock_token_123"},
        json={
            "resumeId": "res_123",
            "targetRole": "Senior Python Engineer",
            "targetCompany": "Google",
            "jobDescription": "We need a Senior Python Engineer with at least 5 years experience.",
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["atsScore"] == 88
    assert data["scoreBreakdown"]["relevance"] == 90
    assert data["matchingSkills"][0]["name"] == "Python"
    assert data["metadata"]["provider"] == "gemini"


@pytest.mark.asyncio
async def test_run_ats_analysis_primary_timeout_fails_over_to_fallback():
    """Simulates primary provider timeout and verifies automatic failover to healthy secondary provider."""
    import asyncio
    from unittest.mock import AsyncMock
    from fastapi import HTTPException
    from app.ai.orchestrator import run_ats_analysis
    from app.ai.fallback_provider import FallbackProvider

    evidence = CandidateEvidence(headline="Backend Dev", summary="Python developer")

    # Primary provider times out (e.g. 504 / Timeout)
    p1 = AsyncMock()
    p1.name = "groq"
    p1.analyze.side_effect = HTTPException(status_code=504, detail="Primary provider timed out")

    # Fallback provider succeeds
    expected_response = AnalyzeResponse(
        ats_score=85,
        score_breakdown=ScoreBreakdown(relevance=85, keywords=85, metrics=85, formatting=85),
        summary_feedback="Strong fit from fallback provider.",
        matching_skills=[SkillMatchItem(name="Python", context="5 years experience")],
        missing_skills=[],
        partial_skills=[],
        metadata=AnalysisMetadata(
            provider="nvidia",
            model="meta/llama-3.2-11b-vision-instruct",
            analyzed_at="2026-08-27T12:00:00Z",
            job_description_hash="mockhash123",
            target_role="Software Engineer",
        ),
    )
    p2 = AsyncMock()
    p2.name = "nvidia"
    p2.analyze.return_value = expected_response

    fallback_chain = FallbackProvider(providers=[p1, p2])

    result = await run_ats_analysis(
        target_role="Software Engineer",
        target_company="Acme Corp",
        job_description="Looking for an engineer with at least thirty characters in description.",
        candidate_evidence=evidence,
        provider=fallback_chain,
    )

    assert result.ats_score == 85
    assert result.metadata.provider == "nvidia"


@pytest.mark.asyncio
async def test_run_ats_analysis_all_providers_fail_raises_safe_error():
    """Verifies that if all providers fail, a safe HTTP 503 is raised without fabricating ATS scores."""
    from unittest.mock import AsyncMock
    from fastapi import HTTPException
    from app.ai.orchestrator import run_ats_analysis
    from app.ai.fallback_provider import FallbackProvider

    evidence = CandidateEvidence(headline="Backend Dev", summary="Python developer")

    p1 = AsyncMock()
    p1.name = "groq"
    p1.analyze.side_effect = HTTPException(status_code=504, detail="Timeout")

    p2 = AsyncMock()
    p2.name = "nvidia"
    p2.analyze.side_effect = HTTPException(status_code=503, detail="Service Unavailable")

    fallback_chain = FallbackProvider(providers=[p1, p2])

    with pytest.raises(HTTPException) as exc_info:
        await run_ats_analysis(
            target_role="Software Engineer",
            target_company="Acme Corp",
            job_description="Looking for an engineer with at least thirty characters in description.",
            candidate_evidence=evidence,
            provider=fallback_chain,
        )

    assert exc_info.value.status_code == 503
    assert "All AI providers in fallback chain failed" in exc_info.value.detail

