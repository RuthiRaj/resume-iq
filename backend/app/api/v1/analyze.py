from fastapi import APIRouter, Depends, status, HTTPException
from app.core.auth import AuthenticatedUser, get_authenticated_user
from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse
from app.services.resume_service import (
    get_candidate_resume_data,
    persist_analysis_results,
    get_workspace_analysis,
)
from app.ai.orchestrator import run_ats_analysis
from app.core.rate_limiter import ai_analysis_limiter
from app.core.logging import get_logger

logger = get_logger("app.api.v1.analyze")

router = APIRouter(prefix="/ai", tags=["AI Analyzer"])


@router.get(
    "/workspace-analysis",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get authenticated user's latest derived workspace ATS analysis",
)
async def get_workspace_analysis_endpoint(
    user: AuthenticatedUser = Depends(get_authenticated_user),
) -> AnalyzeResponse:
    analysis = await get_workspace_analysis(user)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workspace analysis found for this candidate.",
        )
    return analysis


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

    # 1. Fetch Candidate Evidence (FastAPI concurrency: non-blocking async REST)
    candidate_evidence = await get_candidate_resume_data(user, request.resume_id)

    # 2. Invoke AI Analyzer Pipeline
    analysis_result = await run_ats_analysis(
        target_role=request.target_role,
        target_company=request.target_company,
        job_description=request.job_description,
        candidate_evidence=candidate_evidence,
    )

    # 3. Persist results for saved resumes or derived workspace analysis cache
    try:
        await persist_analysis_results(
            user=user,
            resume_id=request.resume_id,
            analysis=analysis_result,
        )
    except Exception as e:
        # Non-fatal persistence logging
        logger.warning(
            f"Failed to persist analysis results: {str(e)}",
            extra={"event": "firestore_write_error", "error_type": type(e).__name__, "component": "analyze_endpoint"},
        )

    return analysis_result
