import pytest
import hashlib
import json
import asyncio
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, status

from app.core.auth import AuthenticatedUser
from app.schemas.candidate import (
    CandidateEvidence,
    ExperienceItem,
    ProjectItem,
    SkillItem,
)
from app.schemas.plan import (
    ResumePlan,
    RequirementStrategy,
    HardGap,
    SelectedEvidenceItem,
    PrioritizedSkill,
)
from app.schemas.variant import (
    ResumeGenerationOutput,
    BulletRewriteItem,
    GenerateResumeRequest,
)
from app.ai.resilience import (
    ProviderErrorType,
    ProviderExecutionEvent,
    ProviderResilienceError,
    classify_provider_exception,
    is_transient_error,
    repair_and_parse_json,
)
from app.ai.fallback_provider import FallbackProvider
from app.ai.claim_validator import validate_claims_against_source, validate_summary_grounding
from app.services.resume_generation_service import (
    ResumeGenerationService,
    GENERATION_SYSTEM_PROMPT,
    SCHEMA_HINT,
)
from app.services.resume_service import ResumeService


# =====================================================================
# 1. Deterministic JSON Repair & Parsing Tests
# =====================================================================

class TestJsonRepairAndParsing:
    def test_parse_valid_json_directly(self):
        payload = '{"summary": "Experienced engineer", "experienceRewrites": []}'
        res = repair_and_parse_json(payload)
        assert res["summary"] == "Experienced engineer"
        assert res["experienceRewrites"] == []

    def test_strip_markdown_code_fences(self):
        fenced_payload = (
            "```json\n"
            '{\n  "summary": "Fenced summary",\n  "experienceRewrites": []\n}\n'
            "```"
        )
        res = repair_and_parse_json(fenced_payload)
        assert res["summary"] == "Fenced summary"

    def test_strip_generic_markdown_code_fences(self):
        fenced_payload = (
            "```\n"
            '{\n  "summary": "Generic fenced summary"\n}\n'
            "```"
        )
        res = repair_and_parse_json(fenced_payload)
        assert res["summary"] == "Generic fenced summary"

    def test_extract_outermost_json_surrounded_by_prose(self):
        prose_payload = (
            "Here is the generated resume JSON:\n\n"
            '{\n  "summary": "Prose wrapped summary",\n  "count": 42\n}\n\n'
            "I hope this helps your application!"
        )
        res = repair_and_parse_json(prose_payload)
        assert res["summary"] == "Prose wrapped summary"
        assert res["count"] == 42

    def test_safe_trailing_comma_removal(self):
        trailing_comma_payload = """
        {
            "summary": "Trailing comma summary",
            "skills": ["Python", "FastAPI", ],
            "meta": {
                "version": 1,
            },
        }
        """
        res = repair_and_parse_json(trailing_comma_payload)
        assert res["summary"] == "Trailing comma summary"
        assert res["skills"] == ["Python", "FastAPI"]
        assert res["meta"]["version"] == 1

    def test_control_character_normalization(self):
        # String containing unescaped null byte and bell character
        raw_text = '{\n  "summary": "Clean\x00 summary with\x07 control chars"\n}'
        res = repair_and_parse_json(raw_text)
        assert res["summary"] == "Clean summary with control chars"

    def test_irreparably_malformed_json_raises_resilience_error(self):
        malformed = "This is not JSON at all and contains no braces."
        with pytest.raises(ProviderResilienceError) as exc_info:
            repair_and_parse_json(malformed)
        assert exc_info.value.error_type == ProviderErrorType.MALFORMED_JSON
        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_truncated_json_does_not_invent_tokens(self):
        truncated = '{"summary": "Incomplete sentence that cut off midway'
        with pytest.raises(ProviderResilienceError) as exc_info:
            repair_and_parse_json(truncated)
        assert exc_info.value.error_type == ProviderErrorType.MALFORMED_JSON

    def test_empty_string_raises_malformed_json(self):
        with pytest.raises(ProviderResilienceError) as exc_info:
            repair_and_parse_json("   ")
        assert exc_info.value.error_type == ProviderErrorType.MALFORMED_JSON


# =====================================================================
# 2. Schema Validation Contract Tests
# =====================================================================

class TestSchemaValidationContracts:
    def test_valid_generation_output_validation(self):
        raw = {
            "summary": "Targeted Python Specialist",
            "experienceRewrites": [
                {
                    "itemId": "exp_0",
                    "bulletIndex": 0,
                    "originalBullet": "Built API in FastAPI.",
                    "rewrittenBullet": "Engineered high-throughput API in FastAPI.",
                }
            ],
            "projectRewrites": [
                {
                    "itemId": "proj_0",
                    "bulletIndex": 0,
                    "originalBullet": "Created auth service.",
                    "rewrittenBullet": "Developed authentication service.",
                }
            ],
        }
        output = ResumeGenerationOutput.model_validate(raw)
        assert output.summary == "Targeted Python Specialist"
        assert len(output.experience_rewrites) == 1
        assert output.experience_rewrites[0].item_id == "exp_0"
        assert output.experience_rewrites[0].bullet_index == 0
        assert len(output.project_rewrites) == 1

    def test_invalid_generation_output_missing_item_id_fails_validation(self):
        raw = {
            "summary": "Targeted summary",
            "experienceRewrites": [
                {
                    # Missing itemId
                    "bulletIndex": 0,
                    "rewrittenBullet": "Engineered API.",
                }
            ],
        }
        with pytest.raises(Exception):
            ResumeGenerationOutput.model_validate(raw)

    def test_negative_bullet_index_fails_validation(self):
        raw = {
            "summary": "Targeted summary",
            "experienceRewrites": [
                {
                    "itemId": "exp_0",
                    "bulletIndex": -1,  # Negative index not allowed
                    "rewrittenBullet": "Engineered API.",
                }
            ],
        }
        with pytest.raises(Exception):
            ResumeGenerationOutput.model_validate(raw)


# =====================================================================
# 3. Provider Error Taxonomy & Classification Tests
# =====================================================================

class TestErrorTaxonomyAndClassification:
    def test_classify_http_exceptions(self):
        assert classify_provider_exception(HTTPException(status_code=429)) == ProviderErrorType.RATE_LIMIT_429
        assert classify_provider_exception(HTTPException(status_code=504)) == ProviderErrorType.TIMEOUT
        assert classify_provider_exception(HTTPException(status_code=401)) == ProviderErrorType.AUTH_ERROR
        assert classify_provider_exception(HTTPException(status_code=503)) == ProviderErrorType.SERVER_ERROR_5XX

    def test_classify_string_patterns(self):
        assert classify_provider_exception(RuntimeError("Request timed out after 60s")) == ProviderErrorType.TIMEOUT
        assert classify_provider_exception(RuntimeError("Resource exhausted: 429 quota exceeded")) == ProviderErrorType.RATE_LIMIT_429
        assert classify_provider_exception(RuntimeError("Invalid API key provided")) == ProviderErrorType.AUTH_ERROR
        assert classify_provider_exception(RuntimeError("Content filter blocked prompt due to safety policy")) == ProviderErrorType.CONTENT_FILTER
        assert classify_provider_exception(RuntimeError("Connection refused / network error")) == ProviderErrorType.NETWORK_ERROR

    def test_is_transient_error(self):
        assert is_transient_error(ProviderErrorType.TIMEOUT) is True
        assert is_transient_error(ProviderErrorType.RATE_LIMIT_429) is True
        assert is_transient_error(ProviderErrorType.SERVER_ERROR_5XX) is True
        assert is_transient_error(ProviderErrorType.NETWORK_ERROR) is True
        assert is_transient_error(ProviderErrorType.AUTH_ERROR) is False
        assert is_transient_error(ProviderErrorType.CONTENT_FILTER) is False
        assert is_transient_error(ProviderErrorType.MALFORMED_JSON) is False


# =====================================================================
# 4. Mock Providers for Offline Testing
# =====================================================================

class MockFailureProvider:
    def __init__(
        self,
        name: str,
        fail_mode: str,
        succeed_after_attempts: int = 999,
        success_payload: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.fail_mode = fail_mode
        self.attempts = 0
        self.succeed_after_attempts = succeed_after_attempts
        self.success_payload = success_payload or {
            "summary": f"Tailored by {name}",
            "experienceRewrites": [],
            "projectRewrites": [],
        }

    @property
    def model_name(self) -> str:
        return f"{self.name}-test-model"

    async def generate_json(self, system_instruction: str, user_prompt: str, schema_hint: Optional[str] = None) -> Dict[str, Any]:
        self.attempts += 1
        if self.attempts > self.succeed_after_attempts:
            return self.success_payload

        if self.fail_mode == "timeout":
            raise asyncio.TimeoutError("Mock timeout after 60s")
        elif self.fail_mode == "429":
            raise HTTPException(status_code=429, detail="Mock rate limit 429")
        elif self.fail_mode == "500":
            raise HTTPException(status_code=500, detail="Mock server error 500")
        elif self.fail_mode == "503":
            raise HTTPException(status_code=503, detail="Mock service unavailable 503")
        elif self.fail_mode == "auth":
            raise HTTPException(status_code=401, detail="Mock invalid auth key")
        elif self.fail_mode == "content_filter":
            raise RuntimeError("Content filter blocked content for safety")
        elif self.fail_mode == "malformed":
            raise ProviderResilienceError(
                error_type=ProviderErrorType.MALFORMED_JSON,
                detail="Mock irreparably malformed JSON",
            )
        elif self.fail_mode == "client_error":
            raise ValueError("Client bad parameter")
        return self.success_payload

    async def analyze(self, *args, **kwargs):
        return await self.generate_json("", "")


# =====================================================================
# 5. Bounded Retry & Fallback Chain Tests
# =====================================================================

@pytest.mark.asyncio
class TestBoundedRetryAndFallback:
    async def test_transient_failure_retried_once_and_succeeds(self):
        # Fails on attempt 1 with timeout, succeeds on attempt 2
        provider = MockFailureProvider("groq", fail_mode="timeout", succeed_after_attempts=1)
        fallback = FallbackProvider(providers=[provider], max_retries_per_provider=1)

        res = await fallback.generate_json("sys", "user")
        assert res["summary"] == "Tailored by groq"
        assert provider.attempts == 2
        events = fallback.execution_events
        assert len(events) == 2
        assert events[0].success is False
        assert events[0].error_type == ProviderErrorType.TIMEOUT
        assert events[1].success is True
        assert fallback.last_provider == "groq"

    async def test_non_transient_auth_error_is_not_retried(self):
        p1 = MockFailureProvider("groq", fail_mode="auth")
        p2 = MockFailureProvider("gemini", fail_mode="none", succeed_after_attempts=0)
        fallback = FallbackProvider(providers=[p1, p2], max_retries_per_provider=1)

        # Groq auth fails without in-provider retry (attempts == 1), but chain does not fail over on client auth/forbidden
        # Re-raises the auth error directly
        with pytest.raises(HTTPException) as exc_info:
            await fallback.generate_json("sys", "user")
        assert exc_info.value.status_code == 401
        assert p1.attempts == 1
        assert p2.attempts == 0

    async def test_content_filter_is_not_retried_indefinitely(self):
        p1 = MockFailureProvider("groq", fail_mode="content_filter")
        p2 = MockFailureProvider("gemini", fail_mode="none", succeed_after_attempts=0)
        fallback = FallbackProvider(providers=[p1, p2], max_retries_per_provider=1)

        res = await fallback.generate_json("sys", "user")
        assert res["summary"] == "Tailored by gemini"
        # p1 should have attempted only 1 time because content_filter is not transient
        assert p1.attempts == 1
        assert p2.attempts == 1
        assert len(fallback.failover_log) == 1

    async def test_failover_across_chain_groq_to_gemini(self):
        # Groq fails with 429 twice (attempt 1 + retry 1) -> fails over to Gemini -> succeeds
        p1 = MockFailureProvider("groq", fail_mode="429")
        p2 = MockFailureProvider("gemini", fail_mode="none", succeed_after_attempts=0)
        fallback = FallbackProvider(providers=[p1, p2], max_retries_per_provider=1)

        res = await fallback.generate_json("sys", "user")
        assert res["summary"] == "Tailored by gemini"
        assert p1.attempts == 2  # 1 initial + 1 bounded retry
        assert p2.attempts == 1
        assert fallback.last_provider == "gemini"
        assert len(fallback.failover_log) == 1
        assert fallback.failover_log[0]["provider"] == "groq"

    async def test_failover_chain_exhaustion_raises_503(self):
        p1 = MockFailureProvider("groq", fail_mode="timeout")
        p2 = MockFailureProvider("gemini", fail_mode="500")
        p3 = MockFailureProvider("nvidia", fail_mode="503")
        fallback = FallbackProvider(providers=[p1, p2, p3], max_retries_per_provider=1)

        with pytest.raises(HTTPException) as exc_info:
            await fallback.generate_json("sys", "user")
        assert exc_info.value.status_code == 503
        assert "All AI providers in fallback chain failed" in exc_info.value.detail
        assert p1.attempts == 2
        assert p2.attempts == 2
        assert p3.attempts == 2
        assert len(fallback.failover_log) == 3


# =====================================================================
# 6. Provider Fallback Invariant: "Provider Fallback ≠ Evidence Fallback"
# =====================================================================

@pytest.mark.asyncio
class TestProviderFallbackInvariant:
    async def test_exact_context_and_plan_immutability_across_failover(self, monkeypatch):
        """
        Proves that when failing over from Groq to Gemini to NVIDIA:
        1. The exact same ResumePlan is preserved.
        2. The exact same candidate evidence snapshot is supplied.
        3. Hard gaps and negative constraints are identical.
        4. No evidence re-retrieval or re-ranking occurs.
        """
        captured_prompts: List[str] = []
        captured_hashes: List[str] = []

        class InvariantCapturingProvider:
            def __init__(self, name: str, should_fail: bool = True):
                self.name = name
                self.should_fail = should_fail
                self.attempts = 0

            @property
            def model_name(self) -> str:
                return f"{self.name}-model"

            async def generate_json(self, system_instruction: str, user_prompt: str, schema_hint: Optional[str] = None) -> Dict[str, Any]:
                self.attempts += 1
                captured_prompts.append(user_prompt)
                # Compute deterministic hash of user prompt
                p_hash = hashlib.sha256(user_prompt.encode("utf-8")).hexdigest()
                captured_hashes.append(p_hash)

                if self.should_fail:
                    raise HTTPException(status_code=504, detail="Timeout")

                return {
                    "summary": "Senior Python Engineer with 6 years experience in FastAPI and PostgreSQL.",
                    "experienceRewrites": [
                        {
                            "itemId": "exp_0",
                            "bulletIndex": 0,
                            "originalBullet": "Built API service in Python.",
                            "rewrittenBullet": "Developed API service in Python.",
                        }
                    ],
                    "projectRewrites": [],
                }

        p1 = InvariantCapturingProvider("groq", should_fail=True)
        p2 = InvariantCapturingProvider("gemini", should_fail=False)
        fallback = FallbackProvider(providers=[p1, p2], max_retries_per_provider=0)

        # Setup mock user and resume data
        user = AuthenticatedUser(uid="test_user_inv_123", token="token_inv_123", email="user@test.com")
        evidence = CandidateEvidence(
            headline="Backend Developer",
            summary="Python developer with FastAPI experience.",
            experience=[
                ExperienceItem(
                    id="exp_0",
                    company="Tech Corp",
                    role="Software Engineer",
                    start_date="2020",
                    end_date="Present",
                    bullets=["Built API service in Python."],
                    technologies=["Python", "FastAPI"],
                )
            ],
            projects=[],
            skills=[SkillItem(name="Python"), SkillItem(name="FastAPI")],
        )

        async def mock_get_resume_data(u, r_id):
            return evidence

        async def mock_save_snapshot(u, v_id, doc):
            return True

        monkeypatch.setattr(ResumeService, "get_candidate_resume_data", mock_get_resume_data)
        monkeypatch.setattr(ResumeService, "save_resume_snapshot", mock_save_snapshot)

        req = GenerateResumeRequest(
            target_role="Senior Backend Engineer",
            target_company="Stripe",
            job_description="Must have 5+ years Python and FastAPI experience.",
        )

        variant = await ResumeGenerationService.generate_role_targeted_resume(
            user=user,
            req=req,
            provider=fallback,
        )

        # Assert that both providers received the exact same prompt & deterministic prompt hash
        assert len(captured_prompts) == 2
        assert captured_prompts[0] == captured_prompts[1]
        assert captured_hashes[0] == captured_hashes[1]

        # Verify generation metadata contains failover proof
        assert variant.generation_metadata["provider"] == "gemini"
        assert variant.generation_metadata["fallback_occurred"] is True
        assert len(variant.generation_metadata["failover_log"]) == 1
        assert variant.generation_metadata["failover_log"][0]["provider"] == "groq"


# =====================================================================
# 7. Grounding & Claim Validation Preservation on Fallback Output
# =====================================================================

@pytest.mark.asyncio
class TestGroundingOnFallbackOutput:
    async def test_fallback_output_with_hallucinated_claims_is_rejected(self, monkeypatch):
        """
        Verifies that even if primary provider fails and fallback provider responds,
        the fallback provider's output is STRICTLY passed through ClaimValidator.
        Ungrounded claims (e.g. invented Kubernetes / 10M QPS) are rejected and reverted to original bullet.
        """
        class HallucinatingFallbackProvider:
            def __init__(self):
                self.name = "gemini"
                self.attempts = 0

            @property
            def model_name(self) -> str:
                return "gemini-2.5-flash"

            async def generate_json(self, system_instruction: str, user_prompt: str, schema_hint: Optional[str] = None) -> Dict[str, Any]:
                self.attempts += 1
                if self.attempts == 1:
                    # First call returns hallucinated bullet with ungrounded tech and metrics
                    return {
                        "summary": "Experienced Python Engineer",
                        "experienceRewrites": [
                            {
                                "itemId": "exp_0",
                                "bulletIndex": 0,
                                "originalBullet": "Wrote internal script for data export.",
                                "rewrittenBullet": "Architected Kubernetes cluster handling 10,000,000 requests per second.",  # Hallucination!
                            }
                        ],
                        "projectRewrites": [],
                    }
                else:
                    # Retry call also tries to inflate
                    return {
                        "experienceRewrites": [
                            {
                                "itemId": "exp_0",
                                "bulletIndex": 0,
                                "originalBullet": "Wrote internal script for data export.",
                                "rewrittenBullet": "Designed distributed Kafka stream.",  # Still hallucinated!
                            }
                        ],
                        "projectRewrites": [],
                    }

        p1 = MockFailureProvider("groq", fail_mode="timeout")
        p2 = HallucinatingFallbackProvider()
        fallback = FallbackProvider(providers=[p1, p2], max_retries_per_provider=0)

        user = AuthenticatedUser(uid="test_user_ground_123", token="token_ground_123", email="user@test.com")
        evidence = CandidateEvidence(
            headline="Junior Developer",
            summary="Python script developer.",
            experience=[
                ExperienceItem(
                    id="exp_0",
                    company="Local Co",
                    role="Junior Developer",
                    start_date="2022",
                    end_date="Present",
                    bullets=["Wrote internal script for data export."],
                    technologies=["Python"],
                )
            ],
            projects=[],
            skills=[SkillItem(name="Python")],
        )

        async def mock_get_resume_data(u, r_id):
            return evidence

        async def mock_save_snapshot(u, v_id, doc):
            return True

        monkeypatch.setattr(ResumeService, "get_candidate_resume_data", mock_get_resume_data)
        monkeypatch.setattr(ResumeService, "save_resume_snapshot", mock_save_snapshot)

        req = GenerateResumeRequest(
            target_role="Platform Engineer",
            target_company="Google",
            job_description="Need Kubernetes and distributed systems expert.",
        )

        variant = await ResumeGenerationService.generate_role_targeted_resume(
            user=user,
            req=req,
            provider=fallback,
        )

        # ClaimValidator must have rejected the hallucinated rewrite and preserved original bullet
        exp_bullets = variant.snapshot.experience[0].bullets
        assert exp_bullets[0] == "Wrote internal script for data export."
        assert len(variant.change_ledger) == 0  # No change applied because rewrite was ungrounded


# =====================================================================
# 8. Tenant Isolation Under Provider Failure
# =====================================================================

@pytest.mark.asyncio
class TestTenantIsolationUnderFailure:
    async def test_tenant_isolation_preserved_across_failover(self, monkeypatch):
        """
        Verifies that user A's provider failover never touches user B's evidence.
        """
        user_a = AuthenticatedUser(uid="user_A_111", token="tok_a", email="a@test.com")
        user_b = AuthenticatedUser(uid="user_B_222", token="tok_b", email="b@test.com")

        accessed_uids = []

        async def mock_get_resume_data(u, r_id):
            accessed_uids.append(u.uid)
            return CandidateEvidence(
                headline=f"Headline for {u.uid}",
                experience=[
                    ExperienceItem(
                        id="exp_0",
                        company="Company",
                        role="Role",
                        start_date="2020",
                        end_date="Present",
                        bullets=["Did work."],
                        technologies=["Python"],
                    )
                ],
                projects=[],
                skills=[SkillItem(name="Python")],
            )

        async def mock_save_snapshot(u, v_id, doc):
            return True

        monkeypatch.setattr(ResumeService, "get_candidate_resume_data", mock_get_resume_data)
        monkeypatch.setattr(ResumeService, "save_resume_snapshot", mock_save_snapshot)

        p1 = MockFailureProvider("groq", fail_mode="timeout")
        p2 = MockFailureProvider("gemini", fail_mode="none", succeed_after_attempts=0)
        fallback = FallbackProvider(providers=[p1, p2], max_retries_per_provider=0)

        req = GenerateResumeRequest(target_role="Developer")

        await ResumeGenerationService.generate_role_targeted_resume(user=user_a, req=req, provider=fallback)
        assert len(accessed_uids) > 0
        assert all(uid == "user_A_111" for uid in accessed_uids)

        accessed_uids.clear()
        await ResumeGenerationService.generate_role_targeted_resume(user=user_b, req=req, provider=fallback)
        assert len(accessed_uids) > 0
        assert all(uid == "user_B_222" for uid in accessed_uids)
