import asyncio
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.auth import get_authenticated_user, AuthenticatedUser
from app.schemas.career_intelligence import (
    AnalyzeGapsRequest,
    AnalyzeGapsResponse,
    CandidateAttestationRequest,
    AttestSkillResponse,
)
from app.services.career_intelligence_service import CareerIntelligenceService
from app.core.rate_limiter import ai_analysis_limiter, mutation_limiter

router = APIRouter(prefix="/career", tags=["Career Intelligence & Gap Bridging"])


@router.post(
    "/analyze-gaps",
    response_model=AnalyzeGapsResponse,
    summary="Analyze missing requirements against verified evidence for transferability bridges and remediation blueprints",
)
async def analyze_gaps_endpoint(
    req: AnalyzeGapsRequest,
    current_user: AuthenticatedUser = Depends(get_authenticated_user),
) -> AnalyzeGapsResponse:
    await ai_analysis_limiter.check(current_user.uid)
    try:
        return await asyncio.wait_for(
            CareerIntelligenceService.analyze_gaps(current_user, req),
            timeout=30.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Gap analysis timed out after 30 seconds. Please retry.",
        )


@router.post(
    "/attest-skill",
    response_model=AttestSkillResponse,
    summary="Submit structured candidate attestation for a transferable skill or remediation, gated by ClaimValidator",
)
async def attest_skill_endpoint(
    req: CandidateAttestationRequest,
    current_user: AuthenticatedUser = Depends(get_authenticated_user),
) -> AttestSkillResponse:
    await mutation_limiter.check(current_user.uid)
    try:
        return await asyncio.wait_for(
            CareerIntelligenceService.process_attestation(current_user, req),
            timeout=30.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Skill attestation timed out after 30 seconds. Please retry.",
        )
