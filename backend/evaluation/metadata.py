"""
ResumeIQ Evaluation Metadata Instrumentation

Provides utilities for capturing execution, reproducibility, hashing, timing,
and token metadata for offline evaluation runs.

Zero dependencies on production AI decision path; 100% evaluation-isolated.
"""

import hashlib
import time
from datetime import datetime, timezone
import uuid
from typing import Optional, Dict, Any

from app.schemas.candidate import CandidateEvidence
from evaluation.schemas.eval_case import EvaluationMetadata, CandidateJobInput


def hash_candidate_evidence(candidate: CandidateEvidence) -> str:
    """
    Computes a deterministic SHA-256 hash of CandidateEvidence input.
    Serializes CandidateEvidence using pydantic model_dump_json with sorted keys.
    """
    raw_json = candidate.model_dump_json(by_alias=True)
    return hashlib.sha256(raw_json.encode("utf-8")).hexdigest()


def hash_job_description(jd_text: str) -> str:
    """
    Computes a deterministic SHA-256 hash of a job description text string.
    Normalizes leading/trailing whitespace before hashing.
    """
    normalized = jd_text.strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def hash_prompt(prompt_text: str) -> str:
    """
    Computes a deterministic SHA-256 hash of a system instruction prompt.
    Returns format 'sha256:<first_12_chars_of_hex>'.
    """
    digest = hashlib.sha256(prompt_text.strip().encode("utf-8")).hexdigest()
    return f"sha256:{digest[:12]}"


def generate_run_id(prefix: str = "run") -> str:
    """
    Generates a unique, traceable evaluation run ID.
    Format: run_<YYYYMMDD_HHMMSS>_<8_hex_digits>
    """
    utc_now = datetime.now(timezone.utc)
    ts_str = utc_now.strftime("%Y%m%d_%H%M%S")
    rand_suffix = uuid.uuid4().hex[:8]
    return f"{prefix}_{ts_str}_{rand_suffix}"


def get_current_iso_utc() -> str:
    """
    Returns current time in ISO-8601 UTC representation (e.g. 2026-09-09T21:58:00Z).
    Guarantees machine-independent UTC timestamp format.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def estimate_token_cost(
    provider: Optional[str],
    model: Optional[str],
    prompt_tokens: Optional[int],
    completion_tokens: Optional[int],
    price_table: Optional[Dict[str, Dict[str, Dict[str, float]]]] = None,
) -> Optional[float]:
    """
    Calculates estimated cost in USD if tokens and model pricing are known.
    Returns None if pricing or tokens are unavailable.
    Does NOT make external network/API calls for pricing.
    """
    if prompt_tokens is None or completion_tokens is None:
        return None
    if not provider or not model:
        return None

    default_rates = {
        "groq": {
            "llama-3.3-70b-versatile": {"prompt": 0.59, "completion": 0.79},
            "llama3-70b-8192": {"prompt": 0.59, "completion": 0.79},
        },
        "gemini": {
            "gemini-2.5-flash": {"prompt": 0.075, "completion": 0.30},
            "gemini-1.5-pro": {"prompt": 1.25, "completion": 5.00},
        },
    }

    tables = price_table or default_rates
    provider_rates = tables.get(provider.lower())
    if not provider_rates:
        return None

    model_rate = provider_rates.get(model.lower())
    if not model_rate:
        return None

    prompt_cost = (prompt_tokens / 1_000_000.0) * model_rate.get("prompt", 0.0)
    completion_cost = (completion_tokens / 1_000_000.0) * model_rate.get("completion", 0.0)
    return round(prompt_cost + completion_cost, 6)


class EvaluationTimer:
    """
    Context manager for measuring execution latency in milliseconds using a monotonic clock.
    """

    def __init__(self):
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.elapsed_ms: float = 0.0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.perf_counter()
        self.elapsed_ms = round((self.end_time - self.start_time) * 1000.0, 3)


def create_evaluation_metadata(
    case_input: Optional[CandidateJobInput] = None,
    candidate_evidence: Optional[CandidateEvidence] = None,
    job_description: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    prompt_version: Optional[str] = None,
    system_instruction: Optional[str] = None,
    temperature: Optional[float] = None,
    run_id: Optional[str] = None,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    execution_time_ms: Optional[float] = None,
    estimated_cost: Optional[float] = None,
) -> EvaluationMetadata:
    """
    Factory function for building a fully instrumented EvaluationMetadata instance.
    Handles automatic hashing, UTC timestamping, run ID generation, total token calculation,
    and optional cost estimation.
    """
    cand_hash = None
    jd_hash = None

    if case_input is not None:
        cand_hash = hash_candidate_evidence(case_input.candidate_evidence)
        jd_hash = hash_job_description(case_input.job_description)
    else:
        if candidate_evidence is not None:
            cand_hash = hash_candidate_evidence(candidate_evidence)
        if job_description is not None:
            jd_hash = hash_job_description(job_description)

    prompt_ver = prompt_version
    if prompt_ver is None and system_instruction is not None:
        prompt_ver = hash_prompt(system_instruction)

    total_tokens = None
    if prompt_tokens is not None and completion_tokens is not None:
        total_tokens = prompt_tokens + completion_tokens

    cost = estimated_cost
    if cost is None and provider and model:
        cost = estimate_token_cost(
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    return EvaluationMetadata(
        provider=provider,
        model=model,
        prompt_version=prompt_ver,
        candidate_input_hash=cand_hash,
        job_description_hash=jd_hash,
        temperature=temperature,
        run_id=run_id or generate_run_id(),
        executed_at=get_current_iso_utc(),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        execution_time_ms=execution_time_ms,
        estimated_cost=cost,
    )
