"""
FastAPI Routes for Career Roadmap Engine (Phase 5.1 — Milestone 5)

Provides endpoints to:
1. POST /v1/roadmaps/generate - Synthesize deterministic capability roadmap
2. GET /v1/roadmaps - List candidate roadmaps
3. GET /v1/roadmaps/{roadmap_id} - Retrieve single roadmap details
4. PATCH /v1/roadmaps/{roadmap_id}/progress - Update milestone state & verify artifacts
5. POST /v1/roadmaps/{roadmap_id}/milestones/{milestone_id}/promote - Create promotion draft
6. POST /v1/roadmaps/{roadmap_id}/reconcile - Reconcile roadmap with live Workspace evidence
7. POST /v1/roadmaps/{roadmap_id}/refresh - Refresh active roadmap against Master Workspace
8. PATCH /v1/roadmaps/{roadmap_id}/lifecycle - Transition roadmap lifecycle state
9. DELETE /v1/roadmaps/{roadmap_id} - Delete roadmap
"""

import asyncio
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.core.auth import get_authenticated_user, AuthenticatedUser
from app.schemas.career_roadmap import (
    RoadmapPlan,
    GenerateRoadmapRequest,
    UpdateMilestoneProgressRequest,
    ListRoadmapsResponse,
    DeleteRoadmapResponse,
    ReconcileRoadmapResponse,
    RefreshRoadmapRequest,
    RefreshRoadmapResponse,
    UpdateRoadmapLifecycleRequest,
)
from app.schemas.ingestion import IngestionDraft
from app.services.career_roadmap_service import CareerRoadmapService
from app.core.rate_limiter import ai_analysis_limiter, mutation_limiter

router = APIRouter(prefix="/career/roadmaps", tags=["Career Roadmap Engine"])


@router.post(
    "/generate",
    response_model=RoadmapPlan,
    summary="Deterministically synthesize a capability roadmap from candidate evidence and targeted gaps",
)
async def generate_roadmap_endpoint(
    req: GenerateRoadmapRequest,
    current_user: AuthenticatedUser = Depends(get_authenticated_user),
) -> RoadmapPlan:
    await ai_analysis_limiter.check(current_user.uid)
    try:
        return await asyncio.wait_for(
            CareerRoadmapService.generate_roadmap(current_user, req),
            timeout=30.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Roadmap generation timed out after 30 seconds. Please retry.",
        )


@router.get(
    "",
    response_model=ListRoadmapsResponse,
    summary="List all career roadmaps belonging to the authenticated candidate with optional filters",
)
async def list_roadmaps_endpoint(
    target_role: Optional[str] = Query(None, description="Filter roadmaps by matching target role substring"),
    active_only: Optional[bool] = Query(None, description="If true, return only active roadmaps (< 100% completed)"),
    lifecycle: Optional[str] = Query(None, description="Filter by lifecycle state (ACTIVE, COMPLETED, ARCHIVED)"),
    current_user: AuthenticatedUser = Depends(get_authenticated_user),
) -> ListRoadmapsResponse:
    return await CareerRoadmapService.list_roadmaps(
        current_user,
        target_role=target_role,
        active_only=active_only,
        lifecycle=lifecycle,
    )


@router.get(
    "/{roadmap_id}",
    response_model=RoadmapPlan,
    summary="Retrieve a specific career roadmap document",
)
async def get_roadmap_endpoint(
    roadmap_id: str,
    current_user: AuthenticatedUser = Depends(get_authenticated_user),
) -> RoadmapPlan:
    return await CareerRoadmapService.get_roadmap(current_user, roadmap_id)


@router.patch(
    "/{roadmap_id}/progress",
    response_model=RoadmapPlan,
    summary="Update milestone progression state, submit verification artifacts or candidate attestation",
)
async def update_milestone_progress_endpoint(
    roadmap_id: str,
    req: UpdateMilestoneProgressRequest,
    current_user: AuthenticatedUser = Depends(get_authenticated_user),
) -> RoadmapPlan:
    await mutation_limiter.check(current_user.uid)
    try:
        return await asyncio.wait_for(
            CareerRoadmapService.update_milestone_progress(current_user, roadmap_id, req),
            timeout=30.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Roadmap progress update timed out after 30 seconds. Please retry.",
        )


@router.post(
    "/{roadmap_id}/milestones/{milestone_id}/promote",
    response_model=IngestionDraft,
    summary="Create a reviewable evidence ingestion draft from a verified roadmap project",
)
async def promote_milestone_project_endpoint(
    roadmap_id: str,
    milestone_id: str,
    current_user: AuthenticatedUser = Depends(get_authenticated_user),
) -> IngestionDraft:
    await mutation_limiter.check(current_user.uid)
    try:
        return await asyncio.wait_for(
            CareerRoadmapService.create_promotion_draft(current_user, roadmap_id, milestone_id),
            timeout=30.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Promotion draft creation timed out after 30 seconds. Please retry.",
        )


@router.post(
    "/{roadmap_id}/reconcile",
    response_model=ReconcileRoadmapResponse,
    summary="Deterministically reconcile roadmap milestones with current Master Workspace evidence",
)
async def reconcile_roadmap_endpoint(
    roadmap_id: str,
    current_user: AuthenticatedUser = Depends(get_authenticated_user),
) -> ReconcileRoadmapResponse:
    await mutation_limiter.check(current_user.uid)
    try:
        return await asyncio.wait_for(
            CareerRoadmapService.reconcile_roadmap(current_user, roadmap_id),
            timeout=30.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Roadmap evidence reconciliation timed out after 30 seconds. Please retry.",
        )


@router.post(
    "/{roadmap_id}/refresh",
    response_model=RefreshRoadmapResponse,
    summary="Refresh an active roadmap against updated Master Workspace evidence while preserving completed history",
)
async def refresh_roadmap_endpoint(
    roadmap_id: str,
    req: RefreshRoadmapRequest,
    current_user: AuthenticatedUser = Depends(get_authenticated_user),
) -> RefreshRoadmapResponse:
    await mutation_limiter.check(current_user.uid)
    try:
        return await asyncio.wait_for(
            CareerRoadmapService.refresh_roadmap(current_user, roadmap_id, req),
            timeout=30.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Roadmap refresh timed out after 30 seconds. Please retry.",
        )


@router.patch(
    "/{roadmap_id}/lifecycle",
    response_model=RoadmapPlan,
    summary="Transition career roadmap lifecycle state (ACTIVE, COMPLETED, ARCHIVED)",
)
async def update_roadmap_lifecycle_endpoint(
    roadmap_id: str,
    req: UpdateRoadmapLifecycleRequest,
    current_user: AuthenticatedUser = Depends(get_authenticated_user),
) -> RoadmapPlan:
    await mutation_limiter.check(current_user.uid)
    try:
        return await asyncio.wait_for(
            CareerRoadmapService.update_lifecycle(current_user, roadmap_id, req),
            timeout=30.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Roadmap lifecycle transition timed out after 30 seconds. Please retry.",
        )


@router.delete(
    "/{roadmap_id}",
    response_model=DeleteRoadmapResponse,
    summary="Delete a career roadmap",
)
async def delete_roadmap_endpoint(
    roadmap_id: str,
    current_user: AuthenticatedUser = Depends(get_authenticated_user),
) -> DeleteRoadmapResponse:
    await mutation_limiter.check(current_user.uid)
    return await CareerRoadmapService.delete_roadmap(current_user, roadmap_id)
