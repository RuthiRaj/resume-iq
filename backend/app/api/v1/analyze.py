from fastapi import APIRouter, Depends, status
from app.core.auth import AuthenticatedUser, get_authenticated_user
from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse
from app.services.resume_service import (
    get_candidate_resume_data,
    persist_analysis_results,
)
from app.ai.orchestrator import run_ats_analysis

from app.core.rate_limiter import ai_analysis_limiter

router = APIRouter(prefix="/ai", tags=["AI Analyzer"])


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute ATS Deep Scan on candidate resume",
)
async def analyze_resume_endpoint(
    request: AnalyzeRequest,
    user: AuthenticatedUser = Depends(get_authenticated_user),
) -> AnalyzeResponse:
    # 0. Enforce per-user rate limit on expensive AI analysis
    await ai_analysis_limiter.check(user.uid)

    # 1. Resolve candidate evidence from Firestore strictly scoped to user.uid
    candidate_evidence = await get_candidate_resume_data(
        user=user,
        resume_id=request.resume_id,
    )

    # 2. Run ATS Analysis via AI Provider
    analysis_result = await run_ats_analysis(
        target_role=request.target_role,
        target_company=request.target_company,
        job_description=request.job_description,
        candidate_evidence=candidate_evidence,
    )

    # 3. Persist results for saved resumes
    if request.resume_id != "workspace":
        try:
            await persist_analysis_results(
                user=user,
                resume_id=request.resume_id,
                analysis=analysis_result,
            )
        except Exception as e:
            # Non-fatal persistence logging
            print(f"Warning: Failed to persist analysis results: {e}")

    return analysis_result
