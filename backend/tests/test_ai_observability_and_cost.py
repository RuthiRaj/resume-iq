import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

from app.core.auth import AuthenticatedUser
from app.schemas.candidate import (
    CandidateEvidence,
    ExperienceItem,
    ProjectItem,
    SkillItem,
)
from app.schemas.common import AnalysisMetadata
from app.schemas.variant import GenerateResumeRequest, TargetedResumeVariant
from app.services.resume_service import ResumeService
from app.services.resume_generation_service import ResumeGenerationService
from app.ai.observability import (
    TokenUsage,
    CostBreakdown,
    StageLatency,
    GroundingMetrics,
    calculate_token_cost,
    CURRENT_PRICING_VERSION,
    MODEL_PRICING_REGISTRY,
)
from app.ai.resilience import ProviderExecutionEvent, ProviderErrorType
from app.ai.fallback_provider import FallbackProvider
from app.ai.providers.groq_provider import GroqAnalyzerProvider
from app.ai.providers.gemini_provider import GeminiAnalyzerProvider
from app.ai.providers.nvidia_provider import NvidiaAnalyzerProvider


# ==============================================================================
# 1. TokenUsage & CostBreakdown Models & Arithmetic Tests
# ==============================================================================

def test_token_usage_model_and_addition():
    u1 = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
    assert u1.prompt_tokens == 100
    assert u1.completion_tokens == 50
    assert u1.total_tokens == 150

    # Test addition with None
    assert u1.add(None).model_dump() == u1.model_dump()

    # Test addition with another usage
    u2 = TokenUsage(prompt_tokens=200, completion_tokens=100, total_tokens=300)
    total = u1.add(u2)
    assert total.prompt_tokens == 300
    assert total.completion_tokens == 150
    assert total.total_tokens == 450


def test_cost_breakdown_model_and_addition():
    c1 = CostBreakdown(
        input_cost_usd=0.000590,
        output_cost_usd=0.000395,
        total_cost_usd=0.000985,
        pricing_version="2026.09.v1",
        pricing_source="registry",
        is_authoritative=True,
    )
    c2 = CostBreakdown(
        input_cost_usd=0.000700,
        output_cost_usd=0.000450,
        total_cost_usd=0.001150,
        pricing_version="2026.09.v1",
        pricing_source="registry",
        is_authoritative=True,
    )

    # Test addition with None
    assert c1.add(None).model_dump() == c1.model_dump()

    # Test addition with another breakdown
    combined = c1.add(c2)
    assert combined.input_cost_usd == pytest.approx(0.001290, abs=1e-6)
    assert combined.output_cost_usd == pytest.approx(0.000845, abs=1e-6)
    assert combined.total_cost_usd == pytest.approx(0.002135, abs=1e-6)
    assert combined.pricing_source == "registry"
    assert combined.is_authoritative is True

    # Test mixed pricing source
    c_fallback = CostBreakdown(
        input_cost_usd=0.0001,
        output_cost_usd=0.0002,
        total_cost_usd=0.0003,
        pricing_source="fallback",
        is_authoritative=False,
    )
    mixed = c1.add(c_fallback)
    assert mixed.pricing_source == "mixed"
    assert mixed.is_authoritative is False


def test_calculate_token_cost_exactness_groq():
    # Groq Llama 3.3 70B: $0.59 / 1M prompt, $0.79 / 1M completion
    usage = TokenUsage(prompt_tokens=1000, completion_tokens=500, total_tokens=1500)
    cost = calculate_token_cost("groq", "llama-3.3-70b-versatile", usage)

    expected_input = 1000 / 1_000_000 * 0.59  # 0.000590
    expected_output = 500 / 1_000_000 * 0.79   # 0.000395
    expected_total = expected_input + expected_output  # 0.000985

    assert cost.input_cost_usd == pytest.approx(expected_input, abs=1e-6)
    assert cost.output_cost_usd == pytest.approx(expected_output, abs=1e-6)
    assert cost.total_cost_usd == pytest.approx(expected_total, abs=1e-6)
    assert cost.is_authoritative is True
    assert cost.pricing_source == "registry"
    assert cost.pricing_version == CURRENT_PRICING_VERSION


def test_calculate_token_cost_exactness_gemini():
    # Gemini Flash: $0.075 / 1M prompt, $0.30 / 1M completion
    usage = TokenUsage(prompt_tokens=2000, completion_tokens=1000, total_tokens=3000)
    cost = calculate_token_cost("gemini", "gemini-2.5-flash", usage)

    expected_input = 2000 / 1_000_000 * 0.075  # 0.000150
    expected_output = 1000 / 1_000_000 * 0.30   # 0.000300
    expected_total = expected_input + expected_output  # 0.000450

    assert cost.input_cost_usd == pytest.approx(expected_input, abs=1e-6)
    assert cost.output_cost_usd == pytest.approx(expected_output, abs=1e-6)
    assert cost.total_cost_usd == pytest.approx(expected_total, abs=1e-6)
    assert cost.is_authoritative is True
    assert cost.pricing_source == "registry"


def test_calculate_token_cost_exactness_nvidia():
    # NVIDIA NIM Llama 3.3 70B: $0.70 / 1M prompt, $0.90 / 1M completion
    usage = TokenUsage(prompt_tokens=10000, completion_tokens=2000, total_tokens=12000)
    cost = calculate_token_cost("nvidia", "meta/llama-3.3-70b-instruct", usage)

    expected_input = 10000 / 1_000_000 * 0.70  # 0.007000
    expected_output = 2000 / 1_000_000 * 0.90   # 0.001800
    expected_total = expected_input + expected_output  # 0.008800

    assert cost.input_cost_usd == pytest.approx(expected_input, abs=1e-6)
    assert cost.output_cost_usd == pytest.approx(expected_output, abs=1e-6)
    assert cost.total_cost_usd == pytest.approx(expected_total, abs=1e-6)
    assert cost.is_authoritative is True


def test_calculate_token_cost_fallback_for_unknown_model():
    # Unknown model should use default fallback rates and mark non-authoritative
    usage = TokenUsage(prompt_tokens=1000, completion_tokens=1000, total_tokens=2000)
    cost = calculate_token_cost("custom_provider", "unknown-model-xyz", usage)

    assert cost.pricing_source == "fallback"
    assert cost.is_authoritative is False
    assert cost.total_cost_usd > 0.0


def test_calculate_token_cost_zero_or_none_usage():
    # None usage
    cost_none = calculate_token_cost("groq", "llama-3.3-70b-versatile", None)
    assert cost_none.total_cost_usd == 0.0
    assert cost_none.input_cost_usd == 0.0
    assert cost_none.output_cost_usd == 0.0

    # 0 tokens
    zero_u = TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)
    cost_zero = calculate_token_cost("groq", "llama-3.3-70b-versatile", zero_u)
    assert cost_zero.total_cost_usd == 0.0


# ==============================================================================
# 2. Token Extraction Tests Across Groq, Gemini, NVIDIA Providers
# ==============================================================================

@pytest.mark.asyncio
async def test_groq_provider_token_extraction(monkeypatch):
    provider = GroqAnalyzerProvider()
    monkeypatch.setattr("app.ai.providers.groq_provider.settings.GROQ_API_KEY", "test_key_123")

    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = '{"summary": "Tailored executive summary", "experienceRewrites": [], "projectRewrites": []}'

    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 450
    mock_usage.completion_tokens = 120
    mock_usage.total_tokens = 570

    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    mock_completion.usage = mock_usage

    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)
    monkeypatch.setattr("app.ai.providers.groq_provider.get_shared_groq_client", lambda k: mock_client)

    res = await provider.generate_json(
        system_instruction="System instruction",
        user_prompt="User prompt",
    )

    assert res["summary"] == "Tailored executive summary"
    assert provider.last_usage is not None
    assert provider.last_usage.prompt_tokens == 450
    assert provider.last_usage.completion_tokens == 120
    assert provider.last_usage.total_tokens == 570


@pytest.mark.asyncio
async def test_gemini_provider_token_extraction(monkeypatch):
    provider = GeminiAnalyzerProvider()
    monkeypatch.setattr("app.ai.providers.gemini_provider.settings.GEMINI_API_KEY", "test_key_123")

    mock_response = MagicMock()
    mock_response.text = '{"summary": "Gemini tailored summary", "experienceRewrites": [], "projectRewrites": []}'

    mock_usage = MagicMock()
    mock_usage.prompt_token_count = 600
    mock_usage.candidates_token_count = 200
    mock_usage.total_token_count = 800
    mock_response.usage_metadata = mock_usage

    mock_client_instance = MagicMock()
    mock_client_instance.aio.models.generate_content = AsyncMock(return_value=mock_response)

    monkeypatch.setattr("app.ai.providers.gemini_provider.genai.Client", lambda **kwargs: mock_client_instance)
    res = await provider.generate_json(
        system_instruction="System instruction",
        user_prompt="User prompt",
    )

    assert res["summary"] == "Gemini tailored summary"
    assert provider.last_usage is not None
    assert provider.last_usage.prompt_tokens == 600
    assert provider.last_usage.completion_tokens == 200
    assert provider.last_usage.total_tokens == 800


@pytest.mark.asyncio
async def test_nvidia_provider_token_extraction(monkeypatch):
    import json
    provider = NvidiaAnalyzerProvider()
    monkeypatch.setattr("app.ai.providers.nvidia_provider.settings.NVIDIA_API_KEY", "test_key_123")

    mock_response_json = {
        "choices": [
            {
                "message": {
                    "content": '{"summary": "Nvidia tailored summary", "experienceRewrites": [], "projectRewrites": []}'
                }
            }
        ],
        "usage": {
            "prompt_tokens": 800,
            "completion_tokens": 250,
            "total_tokens": 1050,
        },
    }

    mock_client = AsyncMock()
    mock_http_resp = MagicMock()
    mock_http_resp.status_code = 200
    mock_http_resp.text = json.dumps(mock_response_json)
    mock_http_resp.json.return_value = mock_response_json
    mock_http_resp.raise_for_status = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_http_resp)

    monkeypatch.setattr("app.ai.providers.nvidia_provider.get_shared_nvidia_client", lambda: mock_client)
    res = await provider.generate_json(
        system_instruction="System instruction",
        user_prompt="User prompt",
    )

    assert res["summary"] == "Nvidia tailored summary"
    assert provider.last_usage is not None
    assert provider.last_usage.prompt_tokens == 800
    assert provider.last_usage.completion_tokens == 250
    assert provider.last_usage.total_tokens == 1050


# ==============================================================================
# 3. FallbackProvider Multi-Attempt Cumulative Usage & Cost Tracking
# ==============================================================================

@pytest.mark.asyncio
async def test_fallback_provider_cumulative_usage_and_cost_on_failover():
    # Provider 1 (Groq) fails with 503
    p1 = MagicMock()
    p1.name = "groq"
    p1.model_name = "llama-3.3-70b-versatile"
    p1.generate_json = AsyncMock(side_effect=HTTPException(status_code=503, detail="Groq server unavailable"))

    # Provider 2 (NVIDIA) succeeds and provides usage
    p2 = MagicMock()
    p2.name = "nvidia"
    p2.model_name = "meta/llama-3.3-70b-instruct"
    p2.last_usage = TokenUsage(prompt_tokens=1500, completion_tokens=300, total_tokens=1800)
    p2.generate_json = AsyncMock(return_value={
        "summary": "Tailored summary",
        "experienceRewrites": [],
        "projectRewrites": [],
    })

    fallback = FallbackProvider(providers=[p1, p2])

    res = await fallback.generate_json(
        system_instruction="Instruction",
        user_prompt="Prompt",
    )

    assert res["summary"] == "Tailored summary"
    assert len(fallback.failover_log) == 1
    # 2 attempts for Groq (1 initial + 1 bounded retry for 503) + 1 attempt for NVIDIA = 3 events
    assert len(fallback.execution_events) == 3

    # Verify first failed attempt event (groq attempt 0)
    ev1 = fallback.execution_events[0]
    assert ev1.provider_name == "groq"
    assert ev1.success is False
    assert ev1.error_type == ProviderErrorType.SERVER_ERROR_5XX
    assert ev1.token_usage is None

    # Verify second failed attempt event (groq retry attempt 1)
    ev2 = fallback.execution_events[1]
    assert ev2.provider_name == "groq"
    assert ev2.success is False

    # Verify third successful attempt event (nvidia)
    ev3 = fallback.execution_events[2]
    assert ev3.provider_name == "nvidia"
    assert ev3.success is True
    assert ev3.token_usage.total_tokens == 1800
    assert ev3.cost is not None
    assert ev3.cost.total_cost_usd > 0.0

    # Cumulative properties
    assert fallback.cumulative_usage.prompt_tokens == 1500
    assert fallback.cumulative_usage.completion_tokens == 300
    assert fallback.cumulative_usage.total_tokens == 1800
    assert fallback.cumulative_cost.total_cost_usd == ev3.cost.total_cost_usd
    assert fallback.total_latency_ms >= 0.0


# ==============================================================================
# 4. ResumeGenerationService End-to-End Observability & Grounding Metrics Tests
# ==============================================================================

@pytest.fixture
def sample_evidence():
    return CandidateEvidence(
        headline="Senior Python Backend Developer",
        summary="Backend engineer with 5 years building REST APIs.",
        experience=[
            ExperienceItem(
                id="exp_0",
                company="Acme Corp",
                role="Senior Backend Developer",
                start_date="2021",
                bullets=[
                    "Engineered distributed ingestion pipeline in Python handling 10,000 req/sec.",
                    "Optimized PostgreSQL queries reducing latency by 40%.",
                ],
                technologies=["Python", "FastAPI", "PostgreSQL"],
            )
        ],
        projects=[
            ProjectItem(
                id="proj_0",
                title="Event Streaming Service",
                description="Real-time event processing system",
                bullets=[
                    "Built streaming pipeline in Python with Kafka.",
                ],
                technologies=["Python", "Kafka"],
            )
        ],
        skills=[
            SkillItem(name="Python", category="Backend"),
            SkillItem(name="FastAPI", category="Backend"),
            SkillItem(name="PostgreSQL", category="Database"),
            SkillItem(name="Kafka", category="Streaming"),
        ],
    )


@pytest.mark.asyncio
async def test_resume_generation_telemetry_and_stage_latency(sample_evidence, monkeypatch):
    user = AuthenticatedUser(uid="user_obs_1", token="token", email="user@test.com")
    monkeypatch.setattr(ResumeService, "get_candidate_resume_data", AsyncMock(return_value=sample_evidence))
    monkeypatch.setattr(ResumeService, "save_resume_snapshot", AsyncMock(return_value=True))

    mock_provider = MagicMock()
    mock_provider.name = "groq"
    mock_provider.model_name = "llama-3.3-70b-versatile"
    mock_provider.last_usage = TokenUsage(prompt_tokens=1200, completion_tokens=250, total_tokens=1450)
    mock_provider.generate_json = AsyncMock(return_value={
        "summary": "Backend engineer with 5 years building REST APIs.",
        "experienceRewrites": [
            {
                "itemId": "exp_0",
                "bulletIndex": 0,
                "originalBullet": "Engineered distributed ingestion pipeline in Python handling 10,000 req/sec.",
                "rewrittenBullet": "Developed distributed ingestion pipeline in Python handling 10,000 req/sec.",
            }
        ],
        "projectRewrites": [],
    })

    req = GenerateResumeRequest(targetRole="Senior Python Engineer")
    variant = await ResumeGenerationService.generate_role_targeted_resume(
        user=user,
        req=req,
        provider=mock_provider,
    )

    assert isinstance(variant, TargetedResumeVariant)
    meta = variant.generation_metadata
    assert meta is not None

    # Check Core Telemetry Keys
    assert meta["operation"] == "resume_tailoring"
    assert meta["provider"] == "groq"
    assert meta["model"] == "llama-3.3-70b-versatile"
    assert meta["pricing_version"] == CURRENT_PRICING_VERSION
    assert meta["pricing_source"] == "registry"

    # Check Token Accounting
    assert meta["token_usage"]["prompt_tokens"] == 1200
    assert meta["token_usage"]["completion_tokens"] == 250
    assert meta["token_usage"]["total_tokens"] == 1450

    # Check Cost Calculation
    assert meta["cumulative_cost_usd"] > 0.0
    assert meta["cost"]["total_cost_usd"] == meta["cumulative_cost_usd"]

    # Check Stage Latency Measurement
    stage_lat = meta["stage_latency"]
    assert "retrieval_ms" in stage_lat and stage_lat["retrieval_ms"] >= 0.0
    assert "planning_ms" in stage_lat and stage_lat["planning_ms"] >= 0.0
    assert "generation_ms" in stage_lat and stage_lat["generation_ms"] >= 0.0
    assert "validation_ms" in stage_lat and stage_lat["validation_ms"] >= 0.0
    assert "total_ms" in stage_lat and stage_lat["total_ms"] >= 0.0

    # Check Grounding Metrics
    grounding = meta["grounding_metrics"]
    assert grounding["claims_evaluated"] == 1
    assert grounding["claims_accepted"] == 1
    assert grounding["claims_rejected"] == 0
    assert grounding["bullets_reverted"] == 0


@pytest.mark.asyncio
async def test_grounding_rejection_and_revert_metric_accounting(sample_evidence, monkeypatch):
    user = AuthenticatedUser(uid="user_obs_2", token="token", email="user@test.com")
    monkeypatch.setattr(ResumeService, "get_candidate_resume_data", AsyncMock(return_value=sample_evidence))
    monkeypatch.setattr(ResumeService, "save_resume_snapshot", AsyncMock(return_value=True))

    mock_provider = MagicMock()
    mock_provider.name = "groq"
    mock_provider.model_name = "llama-3.3-70b-versatile"
    mock_provider.last_usage = TokenUsage(prompt_tokens=1500, completion_tokens=300, total_tokens=1800)

    # First call proposes an ungrounded hallucination with outcome clause and inflated verb
    # Retry call also fails or returns invalid rewrite
    mock_provider.generate_json = AsyncMock(side_effect=[
        {
            "summary": "Backend engineer with 5 years building REST APIs.",
            "experienceRewrites": [
                {
                    "itemId": "exp_0",
                    "bulletIndex": 0,
                    "originalBullet": "Engineered distributed ingestion pipeline in Python handling 10,000 req/sec.",
                    "rewrittenBullet": "Architected distributed pipeline in Python enabling seamless payment processing.",
                }
            ],
            "projectRewrites": [],
        },
        # Retry attempt response
        {
            "experienceRewrites": [
                {
                    "itemId": "exp_0",
                    "bulletIndex": 0,
                    "originalBullet": "Engineered distributed ingestion pipeline in Python handling 10,000 req/sec.",
                    "rewrittenBullet": "Designed high-throughput pipeline enabling real-time streaming.",
                }
            ],
            "projectRewrites": [],
        }
    ])

    req = GenerateResumeRequest(targetRole="Staff Backend Engineer")
    variant = await ResumeGenerationService.generate_role_targeted_resume(
        user=user,
        req=req,
        provider=mock_provider,
    )

    meta = variant.generation_metadata
    grounding = meta["grounding_metrics"]

    # Evaluated initial attempt (rejected) + evaluated retry attempt (rejected)
    assert grounding["claims_evaluated"] == 2
    assert grounding["claims_accepted"] == 0
    assert grounding["claims_rejected"] == 2
    # Bullet was reverted back to original text safely
    assert grounding["bullets_reverted"] == 1

    # Verify bullet safely preserved original text in snapshot
    assert variant.snapshot.experience[0].bullets[0] == "Engineered distributed ingestion pipeline in Python handling 10,000 req/sec."


# ==============================================================================
# 5. Telemetry Privacy & Security Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_telemetry_contains_no_secrets_or_raw_prompts(sample_evidence, monkeypatch):
    user = AuthenticatedUser(uid="user_obs_3", token="super_secret_token_xyz", email="private_user@example.com")
    monkeypatch.setattr(ResumeService, "get_candidate_resume_data", AsyncMock(return_value=sample_evidence))
    monkeypatch.setattr(ResumeService, "save_resume_snapshot", AsyncMock(return_value=True))

    mock_provider = MagicMock()
    mock_provider.name = "gemini"
    mock_provider.model_name = "gemini-2.5-flash"
    mock_provider.last_usage = TokenUsage(prompt_tokens=800, completion_tokens=150, total_tokens=950)
    mock_provider.generate_json = AsyncMock(return_value={
        "summary": "Backend engineer with 5 years building REST APIs.",
        "experienceRewrites": [],
        "projectRewrites": [],
    })

    req = GenerateResumeRequest(
        targetRole="Backend Engineer",
        jobDescription="Must have 5+ years experience in Python and PostgreSQL.",
    )
    variant = await ResumeGenerationService.generate_role_targeted_resume(
        user=user,
        req=req,
        provider=mock_provider,
    )

    meta = variant.generation_metadata
    telemetry_str = str(meta).lower()

    # Assert no user token or sensitive auth strings in telemetry
    assert "super_secret_token_xyz" not in telemetry_str
    assert "api_key" not in meta["token_usage"]
    assert "api_key" not in meta["cost"]
    assert "api_key" not in meta["stage_latency"]
    assert "api_key" not in meta["grounding_metrics"]

    # Assert telemetry does NOT contain raw prompt text or injected commands
    assert "generation_system_prompt" not in telemetry_str
    assert "security & untrusted data directives" not in telemetry_str


# ==============================================================================
# 6. AnalysisMetadata Backward Compatibility Tests
# ==============================================================================

def test_analysis_metadata_backward_compatibility():
    # Legacy initialization without observability fields must pass
    legacy_meta = AnalysisMetadata(
        provider="groq",
        model="llama-3.3-70b-versatile",
        analyzed_at="2026-09-25T12:00:00Z",
        job_description_hash="hash_123",
        target_role="Software Engineer",
    )
    assert legacy_meta.token_usage is None
    assert legacy_meta.estimated_cost_usd is None
    assert legacy_meta.latency_ms is None

    # Modern initialization with observability fields
    modern_meta = AnalysisMetadata(
        provider="groq",
        model="llama-3.3-70b-versatile",
        analyzed_at="2026-09-25T12:00:00Z",
        job_description_hash="hash_123",
        target_role="Software Engineer",
        token_usage=TokenUsage(prompt_tokens=500, completion_tokens=200, total_tokens=700),
        estimated_cost_usd=0.000453,
        latency_ms=342.5,
        pricing_version="2026.09.v1",
    )
    dumped = modern_meta.model_dump(by_alias=True)
    assert dumped["tokenUsage"]["total_tokens"] == 700
    assert dumped["estimatedCostUsd"] == 0.000453
    assert dumped["latencyMs"] == 342.5


# ==============================================================================
# 7. Free Product Invariant Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_free_product_invariant_telemetry_does_not_gate_or_bill(sample_evidence, monkeypatch):
    """
    Invariant: Provider cost/usage telemetry is strictly internal engineering measurement.
    It cannot create user charges, payment requirements, entitlement restrictions, or feature gating.
    """
    user = AuthenticatedUser(uid="free_user_123", token="token_free_user", email="free_user@example.com")
    monkeypatch.setattr(ResumeService, "get_candidate_resume_data", AsyncMock(return_value=sample_evidence))
    monkeypatch.setattr(ResumeService, "save_resume_snapshot", AsyncMock(return_value=True))

    mock_provider = MagicMock()
    mock_provider.name = "groq"
    mock_provider.model_name = "llama-3.3-70b-versatile"
    # Even with very high token consumption
    mock_provider.last_usage = TokenUsage(prompt_tokens=100_000, completion_tokens=50_000, total_tokens=150_000)
    mock_provider.generate_json = AsyncMock(return_value={
        "summary": "Backend engineer with 5 years building REST APIs.",
        "experienceRewrites": [],
        "projectRewrites": [],
    })

    req = GenerateResumeRequest(targetRole="Staff Python Engineer")
    variant = await ResumeGenerationService.generate_role_targeted_resume(
        user=user,
        req=req,
        provider=mock_provider,
    )

    # Generation succeeds fully without payment checks, billing blocks, or user cost enforcement
    assert variant is not None
    assert variant.variant_id is not None
    # Telemetry is purely observational
    assert variant.generation_metadata["cumulative_cost_usd"] > 0.0
    assert "user_charge" not in variant.generation_metadata
    assert "billing_status" not in variant.generation_metadata
    assert "credit_deduction" not in variant.generation_metadata

