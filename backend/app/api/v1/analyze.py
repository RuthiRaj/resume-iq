from fastapi import APIRouter, Depends, status
from app.core.auth import get_current_uid
from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse
from app.services.resume_service import (
    get_candidate_resume_data,
    persist_analysis_results,
)
from app.ai.orchestrator import run_ats_analysis

router = APIRouter(prefix="/ai", tags=["AI Analyzer"])


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute ATS Deep Scan on candidate resume",
)
async def analyze_resume_endpoint(
    request: AnalyzeRequest,
    uid: str = Depends(get_current_uid),
) -> AnalyzeResponse:
    """
    Executes authoritative ATS resume evaluation against a target job description:
    1. Authenticates caller UID via Firebase ID token.
    2. Resolves candidate evidence from Firestore (/users/{uid}/resumes/{resumeId} or master profile).
    3. Normalizes candidate evidence and computes SHA-256 JD hash.
    4. Invokes structured Google Gemini model.
    5. Persists analysis results to Firestore.
    6. Returns structured ATS gap assessment.
    """
    # 1. Resolve candidate evidence from Firestore
    candidate_evidence = await get_candidate_resume_data(
        uid=uid,
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
                uid=uid,
                resume_id=request.resume_id,
                analysis=analysis_result,
            )
        except Exception as e:
            # Non-fatal persistence logging
            print(f"Warning: Failed to persist analysis results: {e}")

    return analysis_result
