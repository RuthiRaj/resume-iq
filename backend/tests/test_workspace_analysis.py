import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.core.auth import get_authenticated_user, AuthenticatedUser
from app.schemas.analyze import (
    AnalyzeResponse,
    ScoreBreakdown,
    SkillMatchItem,
    SkillMissingItem,
    SkillPartialItem,
    AnalysisMetadata,
)
from app.schemas.candidate import CandidateEvidence
from app.services.resume_service import ResumeService
from app.services.profile_service import ProfileService

client = TestClient(app)

SAMPLE_METADATA = AnalysisMetadata(
    provider="gemini",
    model="gemini-2.5-flash",
    analyzed_at="2026-09-28T12:00:00Z",
    job_description_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    target_role="Staff Systems Engineer",
    target_company="Stripe",
)

SAMPLE_ANALYSIS = AnalyzeResponse(
    ats_score=92,
    score_breakdown=ScoreBreakdown(relevance=95, keywords=90, metrics=92, formatting=91),
    summary_feedback="Exceptional candidate evidence matching backend distributed systems requirements.",
    matching_skills=[SkillMatchItem(name="Python", context="10+ years distributed systems")],
    missing_skills=[SkillMissingItem(name="Rust", priority="Low", reason="Nice to have")],
    partial_skills=[SkillPartialItem(name="Kubernetes", note="Basic production usage")],
    metadata=SAMPLE_METADATA,
)


def test_get_workspace_analysis_unauthenticated_returns_401():
    response = client.get("/api/v1/ai/workspace-analysis")
    assert response.status_code == 401


def test_get_workspace_analysis_not_found_returns_404(monkeypatch):
    mock_user = AuthenticatedUser(uid="user_no_analysis", token="token_123")
    app.dependency_overrides[get_authenticated_user] = lambda: mock_user

    from app.api.v1 import analyze as analyze_module

    async def mock_get_workspace_analysis(user):
        assert user.uid == "user_no_analysis"
        return None

    monkeypatch.setattr(analyze_module, "get_workspace_analysis", mock_get_workspace_analysis)

    response = client.get(
        "/api/v1/ai/workspace-analysis",
        headers={"Authorization": "Bearer token_123"},
    )
    app.dependency_overrides.clear()
    assert response.status_code == 404
    assert "No workspace analysis found for this candidate" in response.json()["detail"]


def test_get_workspace_analysis_success_returns_200(monkeypatch):
    mock_user = AuthenticatedUser(uid="user_has_analysis", token="token_456")
    app.dependency_overrides[get_authenticated_user] = lambda: mock_user

    from app.api.v1 import analyze as analyze_module

    async def mock_get_workspace_analysis(user):
        assert user.uid == "user_has_analysis"
        return SAMPLE_ANALYSIS

    monkeypatch.setattr(analyze_module, "get_workspace_analysis", mock_get_workspace_analysis)

    response = client.get(
        "/api/v1/ai/workspace-analysis",
        headers={"Authorization": "Bearer token_456"},
    )
    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert data["atsScore"] == 92
    assert data["scoreBreakdown"]["relevance"] == 95
    assert data["metadata"]["targetRole"] == "Staff Systems Engineer"
    assert data["metadata"]["jobDescriptionHash"] == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_analyze_workspace_source_persists_to_analyses_workspace(monkeypatch):
    mock_user = AuthenticatedUser(uid="user_workspace_source", token="token_789")
    app.dependency_overrides[get_authenticated_user] = lambda: mock_user

    from app.api.v1 import analyze as analyze_module

    # Mock candidate evidence retrieval
    mock_evidence = CandidateEvidence(
        headline="Principal Architect",
        summary="Deep experience in cloud architecture and microservices.",
    )

    async def mock_get_candidate_resume_data(user, resume_id):
        assert user.uid == "user_workspace_source"
        assert resume_id == "workspace"
        return mock_evidence

    monkeypatch.setattr(analyze_module, "get_candidate_resume_data", mock_get_candidate_resume_data)

    # Mock AI orchestrator
    async def mock_run_ats_analysis(target_role, target_company, job_description, candidate_evidence):
        return SAMPLE_ANALYSIS

    monkeypatch.setattr(analyze_module, "run_ats_analysis", mock_run_ats_analysis)

    # Track persistence call
    persisted_destinations = []

    async def mock_persist_analysis_results(user, resume_id, analysis):
        persisted_destinations.append((user.uid, resume_id, analysis.ats_score))

    monkeypatch.setattr(analyze_module, "persist_analysis_results", mock_persist_analysis_results)

    response = client.post(
        "/api/v1/ai/analyze",
        headers={"Authorization": "Bearer token_789"},
        json={
            "resumeId": "workspace",
            "targetRole": "Staff Systems Engineer",
            "targetCompany": "Stripe",
            "jobDescription": "We are seeking a Staff Systems Engineer to design scalable payment platforms.",
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert len(persisted_destinations) == 1
    assert persisted_destinations[0] == ("user_workspace_source", "workspace", 92)


@pytest.mark.asyncio
async def test_resume_service_persist_and_retrieve_workspace_analysis(monkeypatch):
    mock_user = AuthenticatedUser(uid="user_tenant_iso_1", token="iso_token_1")
    captured_patch_urls = []
    captured_get_urls = []

    mock_client = AsyncMock()

    async def mock_patch(url, headers=None, json=None):
        captured_patch_urls.append(url)
        return MagicMock(status_code=200)

    async def mock_get(url, headers=None):
        captured_get_urls.append(url)
        # Return encoded Firestore document format
        from app.services.resume_service import _encode_firestore_fields
        payload = SAMPLE_ANALYSIS.model_dump(by_alias=True)
        return MagicMock(status_code=200, json=lambda: {"fields": _encode_firestore_fields(payload)})

    mock_client.patch = mock_patch
    mock_client.get = mock_get
    monkeypatch.setattr("app.services.resume_service.get_http_client", lambda: mock_client)

    # 1. Test persist
    await ResumeService.persist_analysis_results(mock_user, "workspace", SAMPLE_ANALYSIS)
    assert len(captured_patch_urls) == 1
    assert "users/user_tenant_iso_1/analyses/workspace" in captured_patch_urls[0]

    # 2. Test retrieve
    retrieved = await ResumeService.get_workspace_analysis(mock_user)
    assert retrieved is not None
    assert retrieved.ats_score == 92
    assert retrieved.metadata.job_description_hash == SAMPLE_METADATA.job_description_hash
    assert len(captured_get_urls) == 1
    assert "users/user_tenant_iso_1/analyses/workspace" in captured_get_urls[0]


@pytest.mark.asyncio
async def test_tenant_isolation_between_users(monkeypatch):
    user_a = AuthenticatedUser(uid="user_AAA", token="token_AAA")
    user_b = AuthenticatedUser(uid="user_BBB", token="token_BBB")

    captured_urls = []
    mock_client = AsyncMock()

    async def mock_get(url, headers=None):
        captured_urls.append((url, headers.get("Authorization")))
        return MagicMock(status_code=404)

    mock_client.get = mock_get
    monkeypatch.setattr("app.services.resume_service.get_http_client", lambda: mock_client)

    await ResumeService.get_workspace_analysis(user_a)
    assert "users/user_AAA/analyses/workspace" in captured_urls[0][0]
    assert "token_AAA" in captured_urls[0][1]

    await ResumeService.get_workspace_analysis(user_b)
    assert "users/user_BBB/analyses/workspace" in captured_urls[1][0]
    assert "token_BBB" in captured_urls[1][1]


@pytest.mark.asyncio
async def test_gdpr_export_and_delete_includes_analyses_subcollection(monkeypatch):
    user = AuthenticatedUser(uid="user_gdpr_test", email="gdpr@resumeiq.test", token="gdpr_token")

    mock_client = AsyncMock()
    deleted_urls = []
    get_urls = []

    async def mock_get(url, headers=None, timeout=None):
        get_urls.append(url)
        if "/profile/main" in url:
            return MagicMock(status_code=200, json=lambda: {"fields": {"fullName": {"stringValue": "GDPR User"}}})
        if "/analyses" in url:
            return MagicMock(
                status_code=200,
                json=lambda: {
                    "documents": [
                        {
                            "name": "projects/proj/databases/(default)/documents/users/user_gdpr_test/analyses/workspace",
                            "fields": {"atsScore": {"integerValue": "92"}},
                        }
                    ]
                },
            )
        # Empty for other subcollections
        return MagicMock(status_code=200, json=lambda: {"documents": []})

    async def mock_delete(url, headers=None, timeout=None):
        deleted_urls.append(url)
        return MagicMock(status_code=204)

    mock_client.get = mock_get
    mock_client.delete = mock_delete
    monkeypatch.setattr("app.services.profile_service.get_http_client", lambda: mock_client)

    # 1. Export User Data
    exported = await ProfileService.export_user_data(user)
    assert "derived_analyses" in exported
    assert len(exported["derived_analyses"]) == 1
    assert exported["derived_analyses"][0]["id"] == "workspace"
    assert exported["derived_analyses"][0]["atsScore"] == 92

    # 2. Delete User Account
    res = await ProfileService.delete_account(user)
    assert res["success"] is True
    # Verify that the analyses workspace document was targeted for deletion
    analyses_deletion_targeted = any("analyses/workspace" in u for u in deleted_urls)
    assert analyses_deletion_targeted, "Expected users/user_gdpr_test/analyses/workspace to be deleted"
