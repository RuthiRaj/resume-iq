"""
Comprehensive Test Suite for Data Lifecycle, Account Deletion, Export,
Firestore Transient Retries, and Roadmap History Bounding.
Phase 6.0 — Milestone 3
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import httpx
from httpx import AsyncClient, ASGITransport
from fastapi import HTTPException, status

from app.main import app
from app.core.auth import AuthenticatedUser, get_authenticated_user
from app.core.retry import async_retry_transient, is_transient_exception
from app.services.profile_service import ProfileService
from app.services.career_roadmap_service import CareerRoadmapService
from app.schemas.career_roadmap import (
    RoadmapPlan,
    RoadmapMilestone,
    RoadmapSnapshotRecord,
    RoadmapLifecycle,
    RefreshRoadmapRequest,
)
from app.schemas.candidate import CandidateEvidence


@pytest.fixture
def mock_user_alice():
    return AuthenticatedUser(uid="usr_alice_123", token="tok_alice_123", email="alice@example.com")


@pytest.fixture
def mock_user_bob():
    return AuthenticatedUser(uid="usr_bob_456", token="tok_bob_456", email="bob@example.com")


# =====================================================================
# 1. Centralized Transient Retry Utility Tests
# =====================================================================

@pytest.mark.asyncio
async def test_retry_succeeds_on_transient_network_error():
    attempts = 0

    async def flaky_operation():
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise httpx.NetworkError("Transient connection reset")
        return {"status": "success"}

    result = await async_retry_transient(flaky_operation, max_retries=2, base_delay=0.01)
    assert result == {"status": "success"}
    assert attempts == 2


@pytest.mark.asyncio
async def test_retry_succeeds_on_http_503_or_429():
    attempts = 0

    async def rate_limited_call():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise HTTPException(status_code=503, detail="Service Unavailable")
        return "recovered"

    result = await async_retry_transient(rate_limited_call, max_retries=2, base_delay=0.01)
    assert result == "recovered"
    assert attempts == 2


@pytest.mark.asyncio
async def test_retry_does_not_retry_client_errors():
    attempts = 0

    async def bad_request_call():
        nonlocal attempts
        attempts += 1
        raise HTTPException(status_code=400, detail="Invalid payload")

    with pytest.raises(HTTPException) as exc_info:
        await async_retry_transient(bad_request_call, max_retries=3, base_delay=0.01)

    assert exc_info.value.status_code == 400
    assert attempts == 1  # No retries on 400


@pytest.mark.asyncio
async def test_retry_does_not_retry_value_error():
    attempts = 0

    async def validation_bug():
        nonlocal attempts
        attempts += 1
        raise ValueError("Invalid parameter value")

    with pytest.raises(ValueError):
        await async_retry_transient(validation_bug, max_retries=3, base_delay=0.01)

    assert attempts == 1


@pytest.mark.asyncio
async def test_retry_exhaustion_raises_last_exception():
    attempts = 0

    async def permanently_down():
        nonlocal attempts
        attempts += 1
        raise httpx.TimeoutException("Persistent gateway timeout")

    with pytest.raises(httpx.TimeoutException):
        await async_retry_transient(permanently_down, max_retries=2, base_delay=0.01)

    assert attempts == 3  # Initial + 2 retries


# =====================================================================
# 2. Data Export (GDPR Portability) Tests
# =====================================================================

@pytest.mark.asyncio
async def test_user_data_export_structure_and_isolation(mock_user_alice, monkeypatch):
    """Verifies full structured JSON export under authenticated user UID."""
    
    async def mock_get(url, *args, **kwargs):
        mock_res = MagicMock()
        mock_res.status_code = 200
        if "profile/main" in url:
            mock_res.json.return_value = {
                "fields": {
                    "full_name": {"stringValue": "Alice Engineer"},
                    "email": {"stringValue": "alice@example.com"},
                    "summary": {"stringValue": "Full-stack cloud developer"},
                }
            }
        elif "experience" in url:
            mock_res.json.return_value = {
                "documents": [
                    {
                        "name": "projects/resumeiq/databases/(default)/documents/users/usr_alice_123/experience/exp_1",
                        "fields": {
                            "role": {"stringValue": "Senior Engineer"},
                            "company": {"stringValue": "Tech Corp"},
                        },
                    }
                ]
            }
        else:
            mock_res.json.return_value = {"documents": []}
        return mock_res

    client_mock = MagicMock()
    client_mock.get = AsyncMock(side_effect=mock_get)
    monkeypatch.setattr("app.services.profile_service.get_http_client", lambda: client_mock)

    app.dependency_overrides[get_authenticated_user] = lambda: mock_user_alice
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    try:
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            res = await client.get("/api/v1/profile/export")
            assert res.status_code == 200
            data = res.json()

            assert data["user_id"] == "usr_alice_123"
            assert data["email"] == "alice@example.com"
            assert "master_workspace" in data
            assert "targeted_variants" in data
            assert "career_roadmaps" in data
            assert "ingestion_drafts" in data
            assert data["profile"]["full_name"] == "Alice Engineer"
            assert len(data["master_workspace"]["experience"]) == 1

            # Assert no secret or token fields
            dumped_str = str(data)
            assert "AIzaSy" not in dumped_str
            assert "gsk_" not in dumped_str
            assert "nvapi-" not in dumped_str
            assert "tok_alice_123" not in dumped_str
    finally:
        app.dependency_overrides.pop(get_authenticated_user, None)


# =====================================================================
# 3. Account Deletion (GDPR Right to Erasure) Tests
# =====================================================================

@pytest.mark.asyncio
async def test_account_deletion_cascading_cleanup(mock_user_alice, monkeypatch):
    """Verifies that DELETE /api/v1/account purges all subcollection documents under user.uid."""
    deleted_urls = []

    async def mock_get(url, *args, **kwargs):
        mock_res = MagicMock()
        mock_res.status_code = 200
        if "roadmaps" in url:
            mock_res.json.return_value = {
                "documents": [
                    {"name": "projects/resumeiq/databases/(default)/documents/users/usr_alice_123/roadmaps/rdm_1"},
                    {"name": "projects/resumeiq/databases/(default)/documents/users/usr_alice_123/roadmaps/rdm_2"},
                ]
            }
        elif "experience" in url:
            mock_res.json.return_value = {
                "documents": [
                    {"name": "projects/resumeiq/databases/(default)/documents/users/usr_alice_123/experience/exp_1"},
                ]
            }
        else:
            mock_res.json.return_value = {"documents": []}
        return mock_res

    async def mock_delete(url, *args, **kwargs):
        deleted_urls.append(url)
        mock_res = MagicMock()
        mock_res.status_code = 200
        return mock_res

    client_mock = MagicMock()
    client_mock.get = AsyncMock(side_effect=mock_get)
    client_mock.delete = AsyncMock(side_effect=mock_delete)
    monkeypatch.setattr("app.services.profile_service.get_http_client", lambda: client_mock)

    app.dependency_overrides[get_authenticated_user] = lambda: mock_user_alice
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    try:
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            res = await client.delete("/api/v1/account")
            assert res.status_code == 200
            data = res.json()
            assert data["success"] is True
            assert data["user_id"] == "usr_alice_123"
            assert data["deleted_documents_count"] >= 3

            # Verify every deleted URL is strictly scoped to usr_alice_123
            for url in deleted_urls:
                assert "usr_alice_123" in url
    finally:
        app.dependency_overrides.pop(get_authenticated_user, None)


# =====================================================================
# 4. Roadmap History Bounding Tests
# =====================================================================

@pytest.mark.asyncio
async def test_roadmap_history_snapshots_bounded_to_ten(mock_user_alice, monkeypatch):
    """Verifies that repeated refreshes cap in-document history_snapshots at max 10 records."""
    existing_snapshots = [
        RoadmapSnapshotRecord(
            snapshotId=f"snp_{i}",
            version=i,
            workspaceEvidenceHash=f"hash_{i}",
            targetRole="Engineer",
            targetCompany="",
            milestoneCount=3,
            completedMilestones=1,
            overallProgressPct=33,
            createdAt="2026-09-21T00:00:00Z",
            lifecycle="ACTIVE",
        )
        for i in range(12)  # 12 pre-existing snapshots
    ]

    mock_roadmap = RoadmapPlan(
        roadmapId="rdm_bound_test",
        userId=mock_user_alice.uid,
        title="Senior Cloud Architect Roadmap",
        targetRole="Senior Cloud Architect",
        milestones=[
            RoadmapMilestone(
                milestoneId="m1",
                orderIndex=0,
                title="System Design",
                category="VerifiableProject",
                requirementName="System Architecture",
                targetCapability="Distributed Systems",
                rationale="Required for architectural mastery",
                state="VERIFIED_PROJECT",
            ),
            RoadmapMilestone(
                milestoneId="m2",
                orderIndex=1,
                title="Kubernetes",
                category="VerifiableProject",
                requirementName="Container Orchestration",
                targetCapability="Kubernetes Deployment",
                rationale="Core container deployment skill",
                state="NOT_STARTED",
            ),
        ],
        version=13,
        lifecycle="ACTIVE",
        history_snapshots=existing_snapshots,
        createdAt="2026-09-20T00:00:00Z",
        updatedAt="2026-09-21T00:00:00Z",
    )

    monkeypatch.setattr(CareerRoadmapService, "get_roadmap", AsyncMock(return_value=mock_roadmap))
    monkeypatch.setattr(CareerRoadmapService, "_save_roadmap_doc", AsyncMock(return_value=True))
    monkeypatch.setattr("app.services.career_roadmap_service.load_master_profile", AsyncMock(return_value=CandidateEvidence()))
    
    reconcile_mock = MagicMock()
    reconcile_mock.updated_plan = mock_roadmap
    monkeypatch.setattr(CareerRoadmapService, "reconcile_roadmap", AsyncMock(return_value=reconcile_mock))

    # Trigger refresh
    refresh_req = RefreshRoadmapRequest(expectedVersion=13)
    refreshed_resp = await CareerRoadmapService.refresh_roadmap(mock_user_alice, "rdm_bound_test", refresh_req)
    refreshed = refreshed_resp.updated_plan

    # Assert bounded to 10
    assert len(refreshed.history_snapshots) <= 10
    assert len(refreshed.history_snapshots) == 10
    # Preserves completed milestone
    assert refreshed.milestones[0].state == "VERIFIED_PROJECT"


# =====================================================================
# 5. Targeted Deletion Failure & Resilience Scenarios
# =====================================================================

@pytest.mark.asyncio
async def test_account_deletion_cross_tenant_isolation(mock_user_alice, mock_user_bob, monkeypatch):
    """Verifies that Alice deleting her account never targets or deletes Bob's documents."""
    deleted_urls = []

    async def mock_get(url, *args, **kwargs):
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.json.return_value = {
            "documents": [{"name": f"projects/p/databases/(default)/documents/users/usr_alice_123/experience/exp_1"}]
        }
        return mock_res

    async def mock_delete(url, *args, **kwargs):
        deleted_urls.append(url)
        mock_res = MagicMock()
        mock_res.status_code = 200
        return mock_res

    client_mock = MagicMock()
    client_mock.get = AsyncMock(side_effect=mock_get)
    client_mock.delete = AsyncMock(side_effect=mock_delete)
    monkeypatch.setattr("app.services.profile_service.get_http_client", lambda: client_mock)

    app.dependency_overrides[get_authenticated_user] = lambda: mock_user_alice
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    try:
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            res = await client.delete("/api/v1/account")
            assert res.status_code == 200
            data = res.json()
            assert data["user_id"] == "usr_alice_123"

            for url in deleted_urls:
                assert "usr_alice_123" in url
                assert "usr_bob_456" not in url
    finally:
        app.dependency_overrides.pop(get_authenticated_user, None)


@pytest.mark.asyncio
async def test_account_deletion_empty_account_idempotent(mock_user_alice, monkeypatch):
    """Verifies that deleting an empty or previously deleted account succeeds idempotently without error."""
    async def mock_get(url, *args, **kwargs):
        mock_res = MagicMock()
        mock_res.status_code = 404
        return mock_res

    async def mock_delete(url, *args, **kwargs):
        mock_res = MagicMock()
        mock_res.status_code = 404
        return mock_res

    client_mock = MagicMock()
    client_mock.get = AsyncMock(side_effect=mock_get)
    client_mock.delete = AsyncMock(side_effect=mock_delete)
    monkeypatch.setattr("app.services.profile_service.get_http_client", lambda: client_mock)

    app.dependency_overrides[get_authenticated_user] = lambda: mock_user_alice
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    try:
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            res = await client.delete("/api/v1/account")
            assert res.status_code == 200
            data = res.json()
            assert data["success"] is True
            assert data["deleted_documents_count"] == 0
            assert len(data["errors"]) == 0
    finally:
        app.dependency_overrides.pop(get_authenticated_user, None)


@pytest.mark.asyncio
async def test_account_deletion_partial_firestore_failure_reported(mock_user_alice, monkeypatch):
    """Verifies that partial failure during Firestore deletion reports errors and success=False."""
    async def mock_get(url, *args, **kwargs):
        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.json.return_value = {
            "documents": [{"name": "projects/p/databases/(default)/documents/users/usr_alice_123/experience/exp_1"}]
        }
        return mock_res

    async def mock_delete(url, *args, **kwargs):
        mock_res = MagicMock()
        if "experience" in url:
            mock_res.status_code = 500  # Simulate backend error on experience document delete
        else:
            mock_res.status_code = 200
        return mock_res

    client_mock = MagicMock()
    client_mock.get = AsyncMock(side_effect=mock_get)
    client_mock.delete = AsyncMock(side_effect=mock_delete)
    monkeypatch.setattr("app.services.profile_service.get_http_client", lambda: client_mock)

    app.dependency_overrides[get_authenticated_user] = lambda: mock_user_alice
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    try:
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            res = await client.delete("/api/v1/account")
            assert res.status_code == 200
            data = res.json()
            assert data["success"] is False  # Partial deletion failed
            assert len(data["errors"]) > 0
            assert any("experience" in err for err in data["errors"])
    finally:
        app.dependency_overrides.pop(get_authenticated_user, None)


@pytest.mark.asyncio
async def test_profile_mutation_retry_idempotency_safety(mock_user_alice, monkeypatch):
    """Verifies that save_profile retry on transient errors safely succeeds without duplicating documents."""
    patch_calls = 0

    async def mock_patch(url, *args, **kwargs):
        nonlocal patch_calls
        patch_calls += 1
        mock_res = MagicMock()
        if patch_calls == 1:
            mock_res.status_code = 503  # First attempt fails transiently
            return mock_res
        mock_res.status_code = 200
        mock_res.json.return_value = {
            "fields": {
                "full_name": {"stringValue": "Alice Engineer Updated"},
                "email": {"stringValue": "alice@example.com"},
            }
        }
        return mock_res

    client_mock = MagicMock()
    client_mock.patch = AsyncMock(side_effect=mock_patch)
    monkeypatch.setattr("app.services.profile_service.get_http_client", lambda: client_mock)

    from app.schemas.profile import ProfileDTO
    dto = ProfileDTO(fullName="Alice Engineer Updated", email="alice@example.com")

    saved = await ProfileService.save_profile(mock_user_alice, dto)
    assert saved.profile.full_name == "Alice Engineer Updated"
    assert patch_calls == 2  # Exactly 2 calls: initial transient fail + retry success


@pytest.mark.asyncio
async def test_error_response_contains_request_id_and_message():
    """Verifies that error responses return actionable messages and correlation X-Request-ID headers."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Unauthenticated request (401)
        res_401 = await client.get("/api/v1/profile/export")
        assert res_401.status_code in (401, 403)
        assert "x-request-id" in res_401.headers
        data_401 = res_401.json()
        assert "detail" in data_401 or "error" in data_401

        # 2. Validation error or bad request
        res_400 = await client.post("/api/v1/career/roadmaps/generate", json={"invalid": 123})
        assert res_400.status_code in (400, 401, 422)
        assert "x-request-id" in res_400.headers
        data_400 = res_400.json()
        assert "error" in data_400 or "detail" in data_400


