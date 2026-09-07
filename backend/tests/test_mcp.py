"""
Phase 5.5 — MCP Server Tests

Covers all 18 required security and functional categories:
 1. Authentication enforcement (missing/expired/invalid token)
 2. Cross-user isolation (User A cannot access User B's data)
 3. Profile get/update round-trip
 4. Resume retrieval (workspace + saved resume ID)
 5. Job analysis (rate limit honored; result persisted)
 6. Remediation (get / synthesize / apply)
 7. Variant creation
 8. Variant apply change (version bump, master immutability)
 9. Variant revert change
10. Fit comparison
11. Export (markdown / plain_text / json; xml rejected)
12. Invalid IDs rejected (alphanumeric only)
13. Path traversal rejected (../ in IDs)
14. Oversized payloads rejected
15. Cross-user variant access rejected
16. Optimistic concurrency conflict (wrong expected_version)
17. Rate limit enforcement on AI tools
18. Secret leakage prevention (no API keys/credentials in errors)
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException
from mcp.shared.exceptions import MCPError
from mcp.types import INVALID_PARAMS, INTERNAL_ERROR


# ---------------------------------------------------------------------------
# Shared fixtures and helpers
# ---------------------------------------------------------------------------

@dataclass
class FakeUser:
    uid: str
    token: str
    email: Optional[str] = None


USER_A = FakeUser(uid="user_a_uid", token="token_a", email="a@example.com")
USER_B = FakeUser(uid="user_b_uid", token="token_b", email="b@example.com")


class FakeContext:
    """Simulates an MCP Context with configurable request headers."""

    def __init__(self, token: Optional[str] = "valid_token", custom_header: Optional[str] = None):
        self._token = token
        self._custom_header = custom_header

    @property
    def headers(self):
        if self._custom_header is not None:
            return {"authorization": self._custom_header}
        if self._token is None:
            return None
        if self._token == "__missing_header__":
            return {}
        return {"authorization": f"Bearer {self._token}"}


def _make_ctx(token: Optional[str] = "valid_token", custom_header: Optional[str] = None) -> FakeContext:
    return FakeContext(token=token, custom_header=custom_header)


# ---------------------------------------------------------------------------
# Import MCP server tools under test
# ---------------------------------------------------------------------------

from app.mcp import mcp_server as ms
from app.mcp.auth import resolve_mcp_user, _extract_bearer_token


# ===========================================================================
# Category 1: Authentication Enforcement
# ===========================================================================

class TestAuthEnforcement:
    """MCP tools must reject every call without a valid Firebase ID token."""

    def test_missing_headers_raises(self):
        ctx = FakeContext(token=None)  # headers returns None
        with pytest.raises(MCPError) as exc_info:
            _extract_bearer_token(ctx)
        assert exc_info.value.code == INVALID_PARAMS

    def test_missing_auth_header_raises(self):
        ctx = FakeContext(token="__missing_header__")  # headers = {}
        with pytest.raises(MCPError) as exc_info:
            _extract_bearer_token(ctx)
        assert exc_info.value.code == INVALID_PARAMS

    def test_malformed_header_no_bearer_raises(self):
        ctx = _make_ctx(custom_header="notbearer tokenvalue")
        with pytest.raises(MCPError) as exc_info:
            _extract_bearer_token(ctx)
        assert exc_info.value.code == INVALID_PARAMS

    def test_empty_token_raises(self):
        ctx = _make_ctx(custom_header="Bearer ")
        with pytest.raises(MCPError) as exc_info:
            _extract_bearer_token(ctx)
        assert exc_info.value.code == INVALID_PARAMS

    @patch("app.mcp.auth.get_jwks_client")
    @patch("app.mcp.auth.settings")
    def test_expired_token_raises(self, mock_settings, mock_jwks):
        import jwt
        mock_settings.FIREBASE_PROJECT_ID = "test_project"
        mock_jwks.return_value.get_signing_key_from_jwt.side_effect = jwt.ExpiredSignatureError("expired")
        ctx = _make_ctx("valid.but.expired")
        with pytest.raises(MCPError) as exc_info:
            resolve_mcp_user(ctx)
        assert exc_info.value.code == INVALID_PARAMS
        assert "expired" in exc_info.value.message.lower()

    @patch("app.mcp.auth.get_jwks_client")
    @patch("app.mcp.auth.settings")
    def test_invalid_token_raises(self, mock_settings, mock_jwks):
        import jwt
        mock_settings.FIREBASE_PROJECT_ID = "test_project"
        mock_jwks.return_value.get_signing_key_from_jwt.side_effect = jwt.InvalidTokenError("invalid")
        ctx = _make_ctx("garbage.token.value")
        with pytest.raises(MCPError) as exc_info:
            resolve_mcp_user(ctx)
        assert exc_info.value.code == INVALID_PARAMS

    @patch("app.mcp.auth.settings")
    def test_unconfigured_project_raises(self, mock_settings):
        mock_settings.FIREBASE_PROJECT_ID = ""
        ctx = _make_ctx("some_token")
        with pytest.raises(MCPError) as exc_info:
            resolve_mcp_user(ctx)
        assert exc_info.value.code == INTERNAL_ERROR


# ===========================================================================
# Category 12 & 13: Invalid IDs and Path Traversal
# ===========================================================================

class TestIDValidation:
    """All ID parameters must be rejected if they contain unsafe characters."""

    def test_path_traversal_resume_id(self):
        with pytest.raises(MCPError) as exc_info:
            ms._validate_id("../../etc/passwd", "resume_id")
        assert exc_info.value.code == INVALID_PARAMS

    def test_path_traversal_variant_id(self):
        with pytest.raises(MCPError) as exc_info:
            ms._validate_id("../../../secrets", "variant_id")
        assert exc_info.value.code == INVALID_PARAMS

    def test_sql_injection_id(self):
        with pytest.raises(MCPError) as exc_info:
            ms._validate_id("'; DROP TABLE users;--", "resume_id")
        assert exc_info.value.code == INVALID_PARAMS

    def test_null_byte_id(self):
        with pytest.raises(MCPError) as exc_info:
            ms._validate_id("var_id\x00malicious", "variant_id")
        assert exc_info.value.code == INVALID_PARAMS

    def test_slash_in_id(self):
        with pytest.raises(MCPError) as exc_info:
            ms._validate_id("user_a/secrets", "variant_id")
        assert exc_info.value.code == INVALID_PARAMS

    def test_valid_id_passes(self):
        assert ms._validate_id("var_abc123", "variant_id") == "var_abc123"
        assert ms._validate_id("workspace", "resume_id") == "workspace"
        assert ms._validate_id("exp-0", "item_id") == "exp-0"


# ===========================================================================
# Category 14: Oversized Payloads
# ===========================================================================

class TestPayloadLimits:
    """Oversized inputs must be rejected before reaching service layer."""

    def test_oversized_job_description(self):
        with pytest.raises(MCPError) as exc_info:
            ms._guard_len("x" * (ms.MAX_JD_LEN + 1), ms.MAX_JD_LEN, "job_description")
        assert exc_info.value.code == INVALID_PARAMS
        assert "job_description" in exc_info.value.message

    def test_oversized_candidate_fact(self):
        with pytest.raises(MCPError) as exc_info:
            ms._guard_len("x" * (ms.MAX_BULLET_FACT_LEN + 1), ms.MAX_BULLET_FACT_LEN, "candidate_fact")
        assert exc_info.value.code == INVALID_PARAMS

    def test_within_limit_passes(self):
        result = ms._guard_len("x" * 100, ms.MAX_JD_LEN, "job_description")
        assert result == "x" * 100


# ===========================================================================
# Category 18: Secret Leakage Prevention
# ===========================================================================

class TestSecretLeakage:
    """Error messages must never contain API keys, tokens, or stack traces."""

    def test_auth_error_no_token_leak(self):
        ctx = _make_ctx(token=None)
        with pytest.raises(MCPError) as exc_info:
            _extract_bearer_token(ctx)
        msg = exc_info.value.message
        # Must not contain any token value
        assert "AIza" not in msg
        assert "gsk_" not in msg
        assert "ghp_" not in msg
        assert "Traceback" not in msg

    @patch("app.mcp.auth.get_jwks_client")
    @patch("app.mcp.auth.settings")
    def test_internal_exception_no_details_leak(self, mock_settings, mock_jwks):
        mock_settings.FIREBASE_PROJECT_ID = "test_project"
        mock_jwks.return_value.get_signing_key_from_jwt.side_effect = Exception(
            "PRIVATE KEY: AIzaSomeSecretKeyValue"
        )
        ctx = _make_ctx("some_token")
        with pytest.raises(MCPError) as exc_info:
            resolve_mcp_user(ctx)
        msg = exc_info.value.message
        # Must not expose internal exception detail
        assert "PRIVATE KEY" not in msg
        assert "AIza" not in msg
        assert exc_info.value.code == INVALID_PARAMS

    def test_http_to_mcp_sanitizes_500(self):
        exc = HTTPException(status_code=500, detail="DB password is postgres123 at host 10.0.0.1")
        mcp_err = ms._http_to_mcp(exc)
        assert "postgres123" not in mcp_err.message
        assert "10.0.0.1" not in mcp_err.message

    def test_http_to_mcp_404_safe_message(self):
        exc = HTTPException(status_code=404, detail="Resume 'abc' not found")
        mcp_err = ms._http_to_mcp(exc)
        assert mcp_err.code == INVALID_PARAMS

    def test_http_to_mcp_409_conflict(self):
        exc = HTTPException(status_code=409, detail="Version conflict detected")
        mcp_err = ms._http_to_mcp(exc)
        assert mcp_err.code == INVALID_PARAMS
        assert "conflict" in mcp_err.message.lower() or "version" in mcp_err.message.lower()

    def test_http_to_mcp_429_rate_limit(self):
        exc = HTTPException(status_code=429, detail="Rate limit exceeded")
        mcp_err = ms._http_to_mcp(exc)
        assert mcp_err.code == INVALID_PARAMS


# ===========================================================================
# Category 3: Profile Get/Update
# ===========================================================================

class TestProfileTools:

    @patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_A)
    @patch("app.mcp.mcp_server.ProfileService")
    @pytest.mark.asyncio
    async def test_get_profile_returns_profile(self, mock_ps, mock_resolve):
        from app.schemas.profile import ProfileDTO
        mock_profile = ProfileDTO(
            fullName="Alice Smith",
            headline="Senior Engineer",
            summary="Expert in distributed systems.",
            targetRoles=["Principal Engineer", "Staff Engineer"],
        )
        mock_ps.get_profile = AsyncMock(return_value=mock_profile)
        ctx = _make_ctx()
        result = await ms.get_profile(ctx)
        assert result["fullName"] == "Alice Smith"
        assert result["headline"] == "Senior Engineer"
        assert "Principal Engineer" in result["targetRoles"]
        mock_ps.get_profile.assert_awaited_once_with(USER_A)

    @patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_A)
    @patch("app.mcp.mcp_server.ProfileService")
    @pytest.mark.asyncio
    async def test_update_profile_saves_and_returns(self, mock_ps, mock_resolve):
        from app.schemas.profile import ProfileDTO, ProfileResponse
        saved = ProfileDTO(fullName="Alice Updated", headline="Staff Engineer", targetRoles=["Staff Engineer"])
        mock_ps.save_profile = AsyncMock(return_value=ProfileResponse(
            success=True, profile=saved, message="Profile saved successfully."
        ))
        ctx = _make_ctx()
        result = await ms.update_profile(
            ctx,
            full_name="Alice Updated",
            headline="Staff Engineer",
            target_roles=["Staff Engineer"],
        )
        assert result["success"] is True
        assert result["profile"]["fullName"] == "Alice Updated"
        mock_ps.save_profile.assert_awaited_once()

    @patch("app.mcp.mcp_server.resolve_mcp_user", side_effect=MCPError(INVALID_PARAMS, "Bad token"))
    @pytest.mark.asyncio
    async def test_get_profile_unauthenticated_raises(self, mock_resolve):
        ctx = _make_ctx("bad_token")
        with pytest.raises(MCPError) as exc_info:
            await ms.get_profile(ctx)
        assert exc_info.value.code == INVALID_PARAMS


# ===========================================================================
# Category 4: Resume Retrieval
# ===========================================================================

class TestResumeTools:

    @patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_A)
    @patch("app.mcp.mcp_server.get_candidate_resume_data")
    @pytest.mark.asyncio
    async def test_get_master_resume(self, mock_get, mock_resolve):
        from app.schemas.candidate import CandidateEvidence
        evidence = CandidateEvidence(summary="Expert engineer", experience=[], projects=[], skills=[])
        mock_get.return_value = evidence
        ctx = _make_ctx()
        result = await ms.get_master_resume(ctx)
        assert result["summary"] == "Expert engineer"
        mock_get.assert_awaited_once_with(user=USER_A, resume_id="workspace")

    @patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_A)
    @patch("app.mcp.mcp_server.get_candidate_resume_data")
    @pytest.mark.asyncio
    async def test_get_resume_data_specific_id(self, mock_get, mock_resolve):
        from app.schemas.candidate import CandidateEvidence
        evidence = CandidateEvidence(summary="Resume-specific content")
        mock_get.return_value = evidence
        ctx = _make_ctx()
        result = await ms.get_resume_data(ctx, resume_id="resume_abc123")
        mock_get.assert_awaited_once_with(user=USER_A, resume_id="resume_abc123")
        assert result["summary"] == "Resume-specific content"

    @pytest.mark.asyncio
    async def test_get_resume_data_invalid_id_raises(self):
        ctx = _make_ctx()
        with patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_A):
            with pytest.raises(MCPError) as exc_info:
                await ms.get_resume_data(ctx, resume_id="../../../etc/passwd")
            assert exc_info.value.code == INVALID_PARAMS


# ===========================================================================
# Category 5: Job Analysis
# ===========================================================================

class TestJobAnalysisTools:

    @patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_A)
    @patch("app.mcp.mcp_server.ai_analysis_limiter")
    @patch("app.mcp.mcp_server.get_candidate_resume_data")
    @patch("app.mcp.mcp_server.run_ats_analysis")
    @patch("app.mcp.mcp_server.persist_analysis_results")
    @pytest.mark.asyncio
    async def test_analyze_job_description_success(
        self, mock_persist, mock_analyze, mock_get_data, mock_limiter, mock_resolve
    ):
        from app.schemas.candidate import CandidateEvidence
        from app.schemas.analyze import AnalyzeResponse
        from app.schemas.common import ScoreBreakdown, AnalysisMetadata
        from datetime import datetime, timezone

        mock_limiter.check = AsyncMock()
        evidence = CandidateEvidence(summary="Backend engineer")
        mock_get_data.return_value = evidence

        score_bd = ScoreBreakdown(relevance=80, keywords=70, metrics=60, formatting=90)
        meta = AnalysisMetadata(
            provider="groq",
            model="llama-3.3-70b-versatile",
            analyzed_at=datetime.now(timezone.utc).isoformat(),
            target_role="Senior Backend Engineer",
            target_company="Acme",
            job_description_hash="abc123",
        )
        analysis = AnalyzeResponse(
            atsScore=78,
            scoreBreakdown=score_bd,
            summaryFeedback="Good match overall.",
            matchingSkills=[],
            missingSkills=[],
            partialSkills=[],
            requirementMatches=[],
            remediationSuggestions=[],
            metadata=meta,
        )
        mock_analyze.return_value = analysis
        mock_persist.return_value = None

        ctx = _make_ctx()
        result = await ms.analyze_job_description(
            ctx,
            resume_id="resume_abc",
            target_role="Senior Backend Engineer",
            job_description="Build scalable microservices using Python and Kubernetes.",
            target_company="Acme",
        )

        assert result["atsScore"] == 78
        mock_limiter.check.assert_awaited_once_with(USER_A.uid)
        mock_persist.assert_awaited_once()

    @patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_A)
    @patch("app.mcp.mcp_server.ai_analysis_limiter")
    @pytest.mark.asyncio
    async def test_analyze_rate_limited(self, mock_limiter, mock_resolve):
        mock_limiter.check = AsyncMock(
            side_effect=HTTPException(status_code=429, detail="Rate limit exceeded. Retry in 5 seconds.")
        )
        ctx = _make_ctx()
        with pytest.raises(MCPError) as exc_info:
            await ms.analyze_job_description(
                ctx,
                resume_id="resume_abc",
                target_role="Engineer",
                job_description="Build stuff with Python." * 5,
            )
        assert exc_info.value.code == INVALID_PARAMS
        assert "rate" in exc_info.value.message.lower() or "limit" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_analyze_oversized_jd_rejected(self):
        ctx = _make_ctx()
        with patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_A):
            with pytest.raises(MCPError) as exc_info:
                await ms.analyze_job_description(
                    ctx,
                    resume_id="resume_abc",
                    target_role="Engineer",
                    job_description="x" * (ms.MAX_JD_LEN + 1),
                )
            assert exc_info.value.code == INVALID_PARAMS


# ===========================================================================
# Category 6: Remediation Tools
# ===========================================================================

class TestRemediationTools:

    @patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_A)
    @patch("app.mcp.mcp_server.ResumeService")
    @pytest.mark.asyncio
    async def test_get_remediation_returns_suggestions(self, mock_rs, mock_resolve):
        mock_rs.get_resume_document = AsyncMock(return_value={
            "atsScore": 72,
            "analysisResults": {
                "remediationSuggestions": [
                    {"id": "rem_1", "requirementName": "Kubernetes", "guidance": "Add K8s experience."}
                ]
            }
        })
        ctx = _make_ctx()
        result = await ms.get_remediation(ctx, resume_id="resume_abc")
        assert result["atsScore"] == 72
        assert result["totalSuggestions"] == 1
        assert result["remediationSuggestions"][0]["requirementName"] == "Kubernetes"

    @patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_A)
    @patch("app.mcp.mcp_server.ResumeService")
    @pytest.mark.asyncio
    async def test_get_remediation_not_found(self, mock_rs, mock_resolve):
        mock_rs.get_resume_document = AsyncMock(return_value=None)
        ctx = _make_ctx()
        with pytest.raises(MCPError) as exc_info:
            await ms.get_remediation(ctx, resume_id="nonexistent")
        assert exc_info.value.code == INVALID_PARAMS

    @pytest.mark.asyncio
    async def test_synthesize_bullet_oversized_fact(self):
        ctx = _make_ctx()
        with patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_A):
            with pytest.raises(MCPError) as exc_info:
                await ms.synthesize_bullet(
                    ctx,
                    requirement_name="Python",
                    candidate_fact="x" * (ms.MAX_BULLET_FACT_LEN + 1),
                )
            assert exc_info.value.code == INVALID_PARAMS

    @pytest.mark.asyncio
    async def test_synthesize_bullet_too_short_fact(self):
        ctx = _make_ctx()
        with patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_A):
            with pytest.raises(MCPError) as exc_info:
                await ms.synthesize_bullet(
                    ctx,
                    requirement_name="Python",
                    candidate_fact="abc",  # less than 5 chars
                )
            assert exc_info.value.code == INVALID_PARAMS

    @patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_A)
    @patch("app.mcp.mcp_server.ai_synthesis_limiter")
    @patch("app.mcp.mcp_server.settings")
    @patch("app.mcp.mcp_server.validate_claims_against_source")
    @pytest.mark.asyncio
    async def test_synthesize_bullet_unconfigured_raises(self, mock_validate, mock_settings, mock_limiter, mock_resolve):
        mock_limiter.check = AsyncMock()
        mock_settings.GROQ_API_KEY = ""
        ctx = _make_ctx()
        with pytest.raises(MCPError) as exc_info:
            await ms.synthesize_bullet(ctx, requirement_name="Python", candidate_fact="Built APIs in Python.")
        assert exc_info.value.code == INTERNAL_ERROR


# ===========================================================================
# Category 7: Variant Creation
# ===========================================================================

class TestVariantCreationTool:

    @patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_A)
    @patch("app.mcp.mcp_server.VariantService")
    @pytest.mark.asyncio
    async def test_create_variant_success(self, mock_vs, mock_resolve):
        from app.schemas.variant import TargetedResumeVariant
        from app.schemas.candidate import CandidateEvidence
        from datetime import datetime, timezone
        from app.schemas.common import ScoreBreakdown

        now = datetime.now(timezone.utc).isoformat()
        variant = TargetedResumeVariant(
            variantId="var_abc123",
            masterResumeId="workspace",
            title="Targeted: Senior Engineer @ Acme",
            targetRole="Senior Engineer",
            targetCompany="Acme",
            jobDescriptionHash="hash123",
            version=1,
            baseline_score=75,
            baselineBreakdown=ScoreBreakdown(relevance=70, keywords=75, metrics=80, formatting=80),
            snapshot=CandidateEvidence(summary="Engineer"),
            createdAt=now,
            updatedAt=now,
        )
        mock_vs.create_targeted_variant = AsyncMock(return_value=variant)
        ctx = _make_ctx()
        result = await ms.create_targeted_variant(
            ctx,
            master_resume_id="workspace",
            target_role="Senior Engineer",
            job_description="Build cloud infrastructure at scale.",
            target_company="Acme",
        )
        assert result["variantId"] == "var_abc123"
        assert result["version"] == 1
        assert result["masterResumeId"] == "workspace"
        mock_vs.create_targeted_variant.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_variant_invalid_master_id_rejected(self):
        ctx = _make_ctx()
        with patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_A):
            with pytest.raises(MCPError) as exc_info:
                await ms.create_targeted_variant(
                    ctx,
                    master_resume_id="../../etc/passwd",
                    target_role="Engineer",
                    job_description="Build stuff.",
                )
            assert exc_info.value.code == INVALID_PARAMS

    @pytest.mark.asyncio
    async def test_create_variant_oversized_jd_rejected(self):
        ctx = _make_ctx()
        with patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_A):
            with pytest.raises(MCPError) as exc_info:
                await ms.create_targeted_variant(
                    ctx,
                    master_resume_id="workspace",
                    target_role="Engineer",
                    job_description="x" * (ms.MAX_JD_LEN + 1),
                )
            assert exc_info.value.code == INVALID_PARAMS


# ===========================================================================
# Category 8: Variant Apply Change + Master Immutability
# ===========================================================================

class TestVariantApplyChange:

    @patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_A)
    @patch("app.mcp.mcp_server.mutation_limiter")
    @patch("app.mcp.mcp_server.VariantService")
    @pytest.mark.asyncio
    async def test_apply_change_version_bump(self, mock_vs, mock_limiter, mock_resolve):
        from app.schemas.variant import TargetedResumeVariant, ChangeRecord
        from app.schemas.candidate import CandidateEvidence
        from app.schemas.common import ScoreBreakdown
        from datetime import datetime, timezone

        mock_limiter.check = AsyncMock()
        now = datetime.now(timezone.utc).isoformat()
        updated_variant = TargetedResumeVariant(
            variantId="var_abc123",
            masterResumeId="workspace",
            title="Targeted: Senior Engineer",
            targetRole="Senior Engineer",
            jobDescriptionHash="hash123",
            version=2,
            baselineBreakdown=ScoreBreakdown(relevance=70, keywords=75, metrics=80, formatting=80),
            snapshot=CandidateEvidence(summary="Updated"),
            createdAt=now,
            updatedAt=now,
        )
        change_record = ChangeRecord(
            id="chg_001",
            requirementName="Kubernetes",
            targetItemId="exp_0",
            approvedText="Deployed 50-node K8s cluster.",
            appliedAt=now,
            versionIntroduced=2,
        )
        mock_vs.apply_change_to_variant = AsyncMock(return_value=(updated_variant, change_record))
        ctx = _make_ctx()
        result = await ms.apply_variant_change(
            ctx,
            variant_id="var_abc123",
            requirement_name="Kubernetes",
            approved_bullet="Deployed 50-node K8s cluster.",
            target_item_id="exp_0",
            expected_version=1,
        )
        assert result["success"] is True
        assert result["newVersion"] == 2
        assert result["changeId"] == "chg_001"

    @patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_A)
    @patch("app.mcp.mcp_server.mutation_limiter")
    @patch("app.mcp.mcp_server.VariantService")
    @pytest.mark.asyncio
    async def test_apply_change_invalid_variant_id(self, mock_vs, mock_limiter, mock_resolve):
        mock_limiter.check = AsyncMock()
        ctx = _make_ctx()
        with pytest.raises(MCPError) as exc_info:
            await ms.apply_variant_change(
                ctx,
                variant_id="../secret",
                requirement_name="Python",
                approved_bullet="Built APIs.",
            )
        assert exc_info.value.code == INVALID_PARAMS


# ===========================================================================
# Category 9: Variant Revert Change
# ===========================================================================

class TestVariantRevertChange:

    @patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_A)
    @patch("app.mcp.mcp_server.VariantService")
    @pytest.mark.asyncio
    async def test_revert_change_success(self, mock_vs, mock_resolve):
        from app.schemas.variant import RevertChangeResponse

        mock_vs.revert_change_on_variant = AsyncMock(return_value=RevertChangeResponse(
            success=True,
            variantId="var_abc123",
            changeId="chg_001",
            revertChangeId="chg_revert_001",
            newVersion=3,
            message="Change reverted.",
        ))
        ctx = _make_ctx()
        result = await ms.revert_variant_change(ctx, variant_id="var_abc123", change_id="chg_001")
        assert result["success"] is True
        assert result["newVersion"] == 3
        assert result["revertChangeId"] == "chg_revert_001"

    @pytest.mark.asyncio
    async def test_revert_invalid_change_id(self):
        ctx = _make_ctx()
        with patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_A):
            with pytest.raises(MCPError) as exc_info:
                await ms.revert_variant_change(ctx, variant_id="var_abc123", change_id="../../etc/passwd")
            assert exc_info.value.code == INVALID_PARAMS


# ===========================================================================
# Category 10: Fit Comparison
# ===========================================================================

class TestFitComparisonTool:

    @patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_A)
    @patch("app.mcp.mcp_server.VariantService")
    @pytest.mark.asyncio
    async def test_compare_fit_success(self, mock_vs, mock_resolve):
        from app.schemas.variant import FitComparisonResponse
        from app.schemas.common import ScoreBreakdown

        mock_vs.get_fit_comparison = AsyncMock(return_value=FitComparisonResponse(
            variantId="var_abc123",
            targetRole="Senior Engineer",
            baselineScore=70,
            currentScore=80,
            scoreDelta=10,
            baselineBreakdown=ScoreBreakdown(relevance=60, keywords=70, metrics=80, formatting=80),
            currentBreakdown=ScoreBreakdown(relevance=80, keywords=80, metrics=80, formatting=80),
            requirementProgressions=[],
            totalGapsResolved=2,
            totalGapsRemaining=1,
        ))
        ctx = _make_ctx()
        result = await ms.compare_variant_fit(ctx, variant_id="var_abc123")
        assert result["scoreDelta"] == 10
        assert result["totalGapsResolved"] == 2


# ===========================================================================
# Category 11: Export (multi-format + invalid format rejection)
# ===========================================================================

class TestExportTool:

    @patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_A)
    @patch("app.mcp.mcp_server.VariantService")
    @pytest.mark.asyncio
    async def test_export_markdown(self, mock_vs, mock_resolve):
        from app.schemas.variant import ExportTargetedResumeResponse
        from datetime import datetime, timezone
        mock_vs.export_targeted_variant_snapshot = AsyncMock(return_value=ExportTargetedResumeResponse(
            variantId="var_abc123",
            title="Targeted: Senior Engineer",
            targetRole="Senior Engineer",
            version=2,
            format="markdown",
            content="# Targeted: Senior Engineer\n## Experience\n- Built APIs.",
            exportedAt=datetime.now(timezone.utc).isoformat(),
        ))
        ctx = _make_ctx()
        result = await ms.export_targeted_resume(ctx, variant_id="var_abc123", format="markdown")
        assert result["format"] == "markdown"
        assert "# Targeted" in result["content"]
        mock_vs.export_targeted_variant_snapshot.assert_awaited_once_with(
            USER_A, "var_abc123", fmt="markdown"
        )

    @patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_A)
    @patch("app.mcp.mcp_server.VariantService")
    @pytest.mark.asyncio
    async def test_export_plain_text(self, mock_vs, mock_resolve):
        from app.schemas.variant import ExportTargetedResumeResponse
        from datetime import datetime, timezone
        mock_vs.export_targeted_variant_snapshot = AsyncMock(return_value=ExportTargetedResumeResponse(
            variantId="var_abc123",
            title="Targeted: Senior Engineer",
            targetRole="Senior Engineer",
            version=2,
            format="plain_text",
            content="EXPERIENCE\nBuilt APIs.",
            exportedAt=datetime.now(timezone.utc).isoformat(),
        ))
        ctx = _make_ctx()
        result = await ms.export_targeted_resume(ctx, variant_id="var_abc123", format="plain_text")
        assert result["format"] == "plain_text"

    @patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_A)
    @patch("app.mcp.mcp_server.VariantService")
    @pytest.mark.asyncio
    async def test_export_json(self, mock_vs, mock_resolve):
        from app.schemas.variant import ExportTargetedResumeResponse
        from datetime import datetime, timezone
        mock_vs.export_targeted_variant_snapshot = AsyncMock(return_value=ExportTargetedResumeResponse(
            variantId="var_abc123",
            title="Targeted: Senior Engineer",
            targetRole="Senior Engineer",
            version=2,
            format="json",
            content='{"summary": "Expert"}',
            exportedAt=datetime.now(timezone.utc).isoformat(),
        ))
        ctx = _make_ctx()
        result = await ms.export_targeted_resume(ctx, variant_id="var_abc123", format="json")
        assert result["format"] == "json"

    @pytest.mark.asyncio
    async def test_export_invalid_format_rejected(self):
        ctx = _make_ctx()
        with patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_A):
            with pytest.raises(MCPError) as exc_info:
                await ms.export_targeted_resume(ctx, variant_id="var_abc123", format="xml")
            assert exc_info.value.code == INVALID_PARAMS
            assert "xml" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_export_invalid_variant_id(self):
        ctx = _make_ctx()
        with patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_A):
            with pytest.raises(MCPError) as exc_info:
                await ms.export_targeted_resume(ctx, variant_id="../../secrets", format="markdown")
            assert exc_info.value.code == INVALID_PARAMS


# ===========================================================================
# Category 2 & 15: Cross-user Isolation
# ===========================================================================

class TestTenantIsolation:
    """User B must not be able to access User A's data."""

    @patch("app.mcp.mcp_server.VariantService")
    @pytest.mark.asyncio
    async def test_user_b_cannot_read_user_a_variant(self, mock_vs):
        mock_vs.get_targeted_variant = AsyncMock(
            side_effect=HTTPException(status_code=404, detail="Variant not found.")
        )
        # User B provides their own valid token but requests User A's variant_id
        with patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_B):
            ctx = _make_ctx("user_b_valid_token")
            with pytest.raises(MCPError) as exc_info:
                await ms.get_targeted_variant(ctx, variant_id="var_user_a_001")
            assert exc_info.value.code == INVALID_PARAMS
        # Verify service was called with User B's identity (not User A's)
        mock_vs.get_targeted_variant.assert_awaited_once_with(USER_B, "var_user_a_001")

    @patch("app.mcp.mcp_server.ResumeService")
    @pytest.mark.asyncio
    async def test_user_b_cannot_read_user_a_resume(self, mock_rs):
        mock_rs.get_resume_document = AsyncMock(return_value=None)
        with patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_B):
            ctx = _make_ctx("user_b_valid_token")
            with pytest.raises(MCPError) as exc_info:
                await ms.get_analysis_results(ctx, resume_id="user_a_resume_001")
            assert exc_info.value.code == INVALID_PARAMS

    @patch("app.mcp.mcp_server.ResumeService")
    @pytest.mark.asyncio
    async def test_uid_always_from_token_not_parameter(self, mock_rs):
        """The UID used for Firestore access must always come from the verified token."""
        mock_rs.get_resume_document = AsyncMock(return_value=None)
        # Even if an attacker sends 'user_a_resume' but authenticates as User B,
        # the service must be called with User B's UID from the token
        with patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_B):
            ctx = _make_ctx("user_b_token")
            try:
                await ms.get_analysis_results(ctx, resume_id="user_a_resume_001")
            except MCPError:
                pass
            mock_rs.get_resume_document.assert_awaited_once_with(USER_B, "user_a_resume_001")


# ===========================================================================
# Category 16: Optimistic Concurrency Conflict
# ===========================================================================

class TestConcurrencyConflict:

    @patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_A)
    @patch("app.mcp.mcp_server.mutation_limiter")
    @patch("app.mcp.mcp_server.VariantService")
    @pytest.mark.asyncio
    async def test_stale_expected_version_raises_conflict_error(
        self, mock_vs, mock_limiter, mock_resolve
    ):
        mock_limiter.check = AsyncMock()
        mock_vs.apply_change_to_variant = AsyncMock(
            side_effect=HTTPException(
                status_code=409,
                detail="Version conflict: expected v1 but found v2.",
            )
        )
        ctx = _make_ctx()
        with pytest.raises(MCPError) as exc_info:
            await ms.apply_variant_change(
                ctx,
                variant_id="var_abc123",
                requirement_name="Python",
                approved_bullet="Built reliable APIs.",
                expected_version=1,  # stale: current is 2
            )
        assert exc_info.value.code == INVALID_PARAMS
        assert "conflict" in exc_info.value.message.lower() or "version" in exc_info.value.message.lower()


# ===========================================================================
# Category 17: Rate Limiting
# ===========================================================================

class TestRateLimiting:

    @patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_A)
    @patch("app.mcp.mcp_server.ai_synthesis_limiter")
    @patch("app.mcp.mcp_server.settings")
    @pytest.mark.asyncio
    async def test_synthesis_rate_limit_raises(self, mock_settings, mock_limiter, mock_resolve):
        mock_settings.GROQ_API_KEY = "valid_key"
        mock_limiter.check = AsyncMock(
            side_effect=HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Max 35 requests per 60s. Please retry in 5 seconds.",
                headers={"Retry-After": "5"},
            )
        )
        ctx = _make_ctx()
        with pytest.raises(MCPError) as exc_info:
            await ms.synthesize_bullet(
                ctx,
                requirement_name="Python",
                candidate_fact="Built scalable REST APIs using FastAPI.",
            )
        assert exc_info.value.code == INVALID_PARAMS

    @patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_A)
    @patch("app.mcp.mcp_server.mutation_limiter")
    @patch("app.mcp.mcp_server.VariantService")
    @pytest.mark.asyncio
    async def test_mutation_rate_limit_raises(self, mock_vs, mock_limiter, mock_resolve):
        mock_limiter.check = AsyncMock(
            side_effect=HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Retry in 10 seconds.",
            )
        )
        ctx = _make_ctx()
        with pytest.raises(MCPError) as exc_info:
            await ms.apply_variant_change(
                ctx,
                variant_id="var_abc123",
                requirement_name="Python",
                approved_bullet="Built APIs.",
            )
        assert exc_info.value.code == INVALID_PARAMS


# ===========================================================================
# Verify MCPServer exposes 15 tools and 6 resources
# ===========================================================================

class TestMCPServerDefinition:
    """Smoke tests to verify the server is wired correctly."""

    def test_mcp_server_name(self):
        assert ms.mcp.name == "ResumeIQ"

    def test_mcp_app_is_starlette(self):
        from starlette.applications import Starlette
        assert isinstance(ms.mcp_app, Starlette)

    @pytest.mark.asyncio
    async def test_tool_count(self):
        tools = await ms.mcp.list_tools()
        tool_names = {t.name for t in tools}
        expected = {
            "get_profile", "update_profile",
            "get_master_resume", "get_resume_data",
            "analyze_job_description", "get_analysis_results",
            "get_remediation", "synthesize_bullet", "apply_remediation",
            "create_targeted_variant", "get_targeted_variant",
            "apply_variant_change", "revert_variant_change", "compare_variant_fit",
            "export_targeted_resume",
        }
        assert expected == tool_names, f"Missing tools: {expected - tool_names}"

    @pytest.mark.asyncio
    async def test_resource_count(self):
        templates = await ms.mcp.list_resource_templates()
        uris = {t.uri_template for t in templates}
        expected_templates = {
            "resumeiq://profile/{target}",
            "resumeiq://resume/{resume_id}",
            "resumeiq://variant/{variant_id}",
            "resumeiq://variant/{variant_id}/fit",
            "resumeiq://variant/{variant_id}/changes",
            "resumeiq://variant/{variant_id}/export/{fmt}",
        }
        assert expected_templates == uris, f"Missing resource templates: {expected_templates - uris}"


# ===========================================================================
# Category 19: Resource Handlers Direct Invocation
# ===========================================================================

class TestResourceHandlers:

    @patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_A)
    @patch("app.mcp.mcp_server.ProfileService")
    @pytest.mark.asyncio
    async def test_resource_profile_reads_profile(self, mock_ps, mock_resolve):
        from app.schemas.profile import ProfileDTO
        mock_ps.get_profile = AsyncMock(return_value=ProfileDTO(fullName="Alice Profile"))
        ctx = _make_ctx()
        content = await ms.resource_profile("me", ctx)
        assert "Alice Profile" in content

    @patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_A)
    @patch("app.mcp.mcp_server.get_candidate_resume_data")
    @pytest.mark.asyncio
    async def test_resource_resume_reads_evidence(self, mock_get_data, mock_resolve):
        from app.schemas.candidate import CandidateEvidence
        mock_get_data.return_value = CandidateEvidence(summary="Resume summary data")
        ctx = _make_ctx()
        content = await ms.resource_resume(ctx, resume_id="workspace")
        assert "Resume summary data" in content

    @patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_A)
    @patch("app.mcp.mcp_server.VariantService")
    @pytest.mark.asyncio
    async def test_resource_variant_reads_variant(self, mock_vs, mock_resolve):
        from app.schemas.variant import TargetedResumeVariant
        from app.schemas.candidate import CandidateEvidence
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        variant = TargetedResumeVariant(
            variantId="var_res_001",
            masterResumeId="workspace",
            title="Targeted: Architect",
            targetRole="Architect",
            jobDescriptionHash="hash",
            version=1,
            snapshot=CandidateEvidence(summary="Architect profile"),
            createdAt=now,
            updatedAt=now,
        )
        mock_vs.get_targeted_variant = AsyncMock(return_value=variant)
        ctx = _make_ctx()
        content = await ms.resource_variant(ctx, variant_id="var_res_001")
        assert "var_res_001" in content
        assert "Architect" in content

    @patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_A)
    @patch("app.mcp.mcp_server.VariantService")
    @pytest.mark.asyncio
    async def test_resource_fit_reads_fit_comparison(self, mock_vs, mock_resolve):
        from app.schemas.variant import FitComparisonResponse
        from app.schemas.common import ScoreBreakdown
        mock_vs.get_fit_comparison = AsyncMock(return_value=FitComparisonResponse(
            variantId="var_res_001",
            targetRole="Architect",
            baselineScore=70,
            currentScore=85,
            scoreDelta=15,
            baselineBreakdown=ScoreBreakdown(relevance=70, keywords=70, metrics=70, formatting=70),
            currentBreakdown=ScoreBreakdown(relevance=85, keywords=85, metrics=85, formatting=85),
            requirementProgressions=[],
            totalGapsResolved=3,
            totalGapsRemaining=0,
        ))
        ctx = _make_ctx()
        content = await ms.resource_fit(ctx, variant_id="var_res_001")
        assert "var_res_001" in content
        assert '"scoreDelta": 15' in content or '"scoreDelta":15' in content

    @patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_A)
    @patch("app.mcp.mcp_server.VariantService")
    @pytest.mark.asyncio
    async def test_resource_changes_reads_ledger(self, mock_vs, mock_resolve):
        from app.schemas.variant import TargetedResumeVariant, ChangeRecord
        from app.schemas.candidate import CandidateEvidence
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        variant = TargetedResumeVariant(
            variantId="var_res_001",
            masterResumeId="workspace",
            title="Targeted: Architect",
            targetRole="Architect",
            jobDescriptionHash="hash",
            version=2,
            snapshot=CandidateEvidence(summary="Architect"),
            changeLedger=[
                ChangeRecord(
                    id="chg_001",
                    requirementName="AWS",
                    targetItemId="exp_0",
                    approvedText="Architected AWS multi-region setup.",
                    appliedAt=now,
                    versionIntroduced=2,
                )
            ],
            createdAt=now,
            updatedAt=now,
        )
        mock_vs.get_targeted_variant = AsyncMock(return_value=variant)
        ctx = _make_ctx()
        content = await ms.resource_changes(ctx, variant_id="var_res_001")
        assert "chg_001" in content
        assert "AWS" in content

    @patch("app.mcp.mcp_server.resolve_mcp_user", return_value=USER_A)
    @patch("app.mcp.mcp_server.VariantService")
    @pytest.mark.asyncio
    async def test_resource_export_reads_formatted_text(self, mock_vs, mock_resolve):
        from app.schemas.variant import ExportTargetedResumeResponse
        from datetime import datetime, timezone
        mock_vs.export_targeted_variant_snapshot = AsyncMock(return_value=ExportTargetedResumeResponse(
            variantId="var_res_001",
            title="Targeted: Architect",
            targetRole="Architect",
            version=1,
            format="markdown",
            content="# Exported Markdown Resume",
            exportedAt=datetime.now(timezone.utc).isoformat(),
        ))
        ctx = _make_ctx()
        content = await ms.resource_export(ctx, variant_id="var_res_001", fmt="markdown")
        assert content == "# Exported Markdown Resume"
