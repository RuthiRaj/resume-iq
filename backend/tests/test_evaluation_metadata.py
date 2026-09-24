"""
Tests for ResumeIQ Phase 2.3 Evaluation Metadata Instrumentation

Validates:
- Deterministic candidate and job description SHA-256 hashing.
- Hash sensitivity (different inputs produce distinct hashes).
- Traceable run ID generation.
- Machine-independent ISO-8601 UTC timestamps.
- Token metrics aggregation and optional None behavior.
- Monotonic latency measurement using EvaluationTimer.
- Standard token cost estimation and unknown provider fallback.
- Serialization and deserialization round-trip with Pydantic aliases.
"""

import time
import re
from datetime import datetime, timezone
import pytest
from app.schemas.candidate import CandidateEvidence, ExperienceItem, SkillItem
from evaluation.schemas.eval_case import CandidateJobInput, EvaluationMetadata
from evaluation.metadata import (
    hash_candidate_evidence,
    hash_job_description,
    hash_prompt,
    generate_run_id,
    get_current_iso_utc,
    estimate_token_cost,
    EvaluationTimer,
    create_evaluation_metadata,
)


def test_deterministic_candidate_and_jd_hashing():
    """Verify that hashing same input produces identical SHA-256 hash."""
    candidate1 = CandidateEvidence(
        headline="Backend Engineer",
        summary="Experienced Python developer.",
        experience=[
            ExperienceItem(
                role="Senior Engineer",
                company="TechCorp",
                bullets=["Built APIs in Python."],
            )
        ],
        skills=[SkillItem(name="Python", category="Language")],
    )

    candidate2 = CandidateEvidence(
        headline="Backend Engineer",
        summary="Experienced Python developer.",
        experience=[
            ExperienceItem(
                role="Senior Engineer",
                company="TechCorp",
                bullets=["Built APIs in Python."],
            )
        ],
        skills=[SkillItem(name="Python", category="Language")],
    )

    jd_text1 = "We are seeking a Senior Python Developer with microservices experience."
    jd_text2 = "   We are seeking a Senior Python Developer with microservices experience.  \n"

    # Determinism checks
    hash_cand1 = hash_candidate_evidence(candidate1)
    hash_cand2 = hash_candidate_evidence(candidate2)
    assert hash_cand1 == hash_cand2
    assert len(hash_cand1) == 64

    hash_jd1 = hash_job_description(jd_text1)
    hash_jd2 = hash_job_description(jd_text2)
    assert hash_jd1 == hash_jd2
    assert len(hash_jd1) == 64


def test_different_inputs_produce_different_hashes():
    """Verify that modifying candidate evidence or JD text alters the resulting hash."""
    candidate_base = CandidateEvidence(
        headline="Software Developer",
        summary="Generalist developer.",
    )
    candidate_modified = CandidateEvidence(
        headline="Senior Software Developer",
        summary="Generalist developer.",
    )

    jd_base = "Looking for a Python Developer."
    jd_modified = "Looking for a Java Developer."

    assert hash_candidate_evidence(candidate_base) != hash_candidate_evidence(candidate_modified)
    assert hash_job_description(jd_base) != hash_job_description(jd_modified)


def test_prompt_hashing():
    """Verify system instruction prompt hashing produces sha256: prefix with 12 hex chars."""
    prompt_text = "You are an ATS evaluation assistant."
    prompt_hash = hash_prompt(prompt_text)
    assert prompt_hash.startswith("sha256:")
    assert len(prompt_hash) == 19  # 'sha256:' (7) + 12 hex chars


def test_run_id_generation():
    """Verify run ID follows pattern run_<YYYYMMDD_HHMMSS>_<hex>."""
    run_id1 = generate_run_id()
    run_id2 = generate_run_id(prefix="eval")

    assert run_id1.startswith("run_")
    assert run_id2.startswith("eval_")
    assert run_id1 != run_id2

    # Verify regex pattern match
    pattern = re.compile(r"^[a-z]+_\d{8}_\d{6}_[a-f0-9]{8}$")
    assert pattern.match(run_id1)
    assert pattern.match(run_id2)


def test_iso_utc_timestamp_format():
    """Verify ISO-8601 UTC timestamp ends with Z and parses as valid UTC datetime."""
    timestamp_str = get_current_iso_utc()
    assert timestamp_str.endswith("Z")

    parsed_dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
    assert parsed_dt.tzinfo == timezone.utc


def test_latency_measurement_with_evaluation_timer():
    """Verify EvaluationTimer context manager accurately records non-negative elapsed time in ms."""
    with EvaluationTimer() as timer:
        time.sleep(0.02)  # sleep 20ms

    assert timer.elapsed_ms >= 15.0  # Monotonic clock check
    assert isinstance(timer.elapsed_ms, float)


def test_token_cost_estimation():
    """Verify cost estimation calculation and unknown model/provider fallback to None."""
    # Known provider and model
    cost_known = estimate_token_cost(
        provider="groq",
        model="llama-3.3-70b-versatile",
        prompt_tokens=1000,
        completion_tokens=500,
    )
    assert cost_known is not None
    assert cost_known > 0.0

    # Missing tokens fallback
    cost_no_tokens = estimate_token_cost(
        provider="groq",
        model="llama-3.3-70b-versatile",
        prompt_tokens=None,
        completion_tokens=None,
    )
    assert cost_no_tokens is None

    # Unknown provider fallback
    cost_unknown = estimate_token_cost(
        provider="unknown_ai_provider",
        model="custom-model",
        prompt_tokens=1000,
        completion_tokens=500,
    )
    assert cost_unknown is None


def test_create_evaluation_metadata_factory():
    """Verify factory builds complete EvaluationMetadata instance with all options."""
    candidate = CandidateEvidence(headline="Full Stack Dev")
    case_input = CandidateJobInput(
        candidate_evidence=candidate,
        target_role="Full Stack Developer",
        target_company="Acme",
        job_description="We need a Full Stack Developer with React and Python experience.",
    )

    metadata = create_evaluation_metadata(
        case_input=case_input,
        provider="groq",
        model="llama-3.3-70b-versatile",
        system_instruction="You are an ATS recruiter.",
        temperature=0.2,
        prompt_tokens=1200,
        completion_tokens=400,
        execution_time_ms=185.5,
    )

    assert metadata.provider == "groq"
    assert metadata.model == "llama-3.3-70b-versatile"
    assert metadata.prompt_version.startswith("sha256:")
    assert len(metadata.candidate_input_hash) == 64
    assert len(metadata.job_description_hash) == 64
    assert metadata.temperature == 0.2
    assert metadata.prompt_tokens == 1200
    assert metadata.completion_tokens == 400
    assert metadata.total_tokens == 1600
    assert metadata.execution_time_ms == 185.5
    assert metadata.estimated_cost is not None
    assert metadata.run_id.startswith("run_")
    assert metadata.executed_at.endswith("Z")


def test_optional_telemetry_fields_can_be_none():
    """Verify evaluation metadata can be created cleanly when token/cost telemetry is absent."""
    metadata = create_evaluation_metadata(
        provider="groq",
        model="llama-3.3-70b-versatile",
    )

    assert metadata.provider == "groq"
    assert metadata.model == "llama-3.3-70b-versatile"
    assert metadata.prompt_tokens is None
    assert metadata.completion_tokens is None
    assert metadata.total_tokens is None
    assert metadata.execution_time_ms is None
    assert metadata.estimated_cost is None


def test_evaluation_metadata_serialization_aliases():
    """Verify EvaluationMetadata serializes and deserializes using camelCase aliases."""
    metadata = create_evaluation_metadata(
        provider="gemini",
        model="gemini-2.5-flash",
        prompt_tokens=500,
        completion_tokens=200,
        execution_time_ms=95.0,
    )

    dumped = metadata.model_dump(by_alias=True)
    assert dumped["provider"] == "gemini"
    assert dumped["model"] == "gemini-2.5-flash"
    assert "promptTokens" in dumped
    assert "completionTokens" in dumped
    assert "totalTokens" in dumped
    assert "executionTimeMs" in dumped
    assert "runId" in dumped
    assert "executedAt" in dumped

    # Round trip validation
    revalidated = EvaluationMetadata.model_validate(dumped)
    assert revalidated.provider == "gemini"
    assert revalidated.total_tokens == 700
    assert revalidated.execution_time_ms == 95.0
