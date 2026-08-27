from typing import Optional
from app.ai.factory import get_ai_analyzer_provider
from app.core.security import hash_job_description
from app.schemas.candidate import CandidateEvidence
from app.schemas.analyze import AnalyzeResponse


async def run_ats_analysis(
    target_role: str,
    target_company: Optional[str],
    job_description: str,
    candidate_evidence: CandidateEvidence,
) -> AnalyzeResponse:
    """Orchestrates hashing, provider invocation, and ATS result validation."""
    provider = get_ai_analyzer_provider()
    jd_hash = hash_job_description(job_description)

    return await provider.analyze(
        target_role=target_role,
        target_company=target_company,
        job_description=job_description,
        job_description_hash=jd_hash,
        candidate_evidence=candidate_evidence,
    )
