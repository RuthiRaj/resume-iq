from typing import Optional
from app.ai.provider import AiAnalyzerProvider
from app.ai.fallback_provider import FallbackProvider
from app.core.security import hash_job_description
from app.schemas.candidate import CandidateEvidence
from app.schemas.analyze import AnalyzeResponse


async def run_ats_analysis(
    target_role: str,
    target_company: Optional[str],
    job_description: str,
    candidate_evidence: CandidateEvidence,
    provider: Optional[AiAnalyzerProvider] = None,
) -> AnalyzeResponse:
    """Orchestrates hashing, provider invocation, and ATS result validation."""
    active_provider = provider or FallbackProvider()
    jd_hash = hash_job_description(job_description)

    return await active_provider.analyze(
        target_role=target_role,
        target_company=target_company,
        job_description=job_description,
        job_description_hash=jd_hash,
        candidate_evidence=candidate_evidence,
    )
