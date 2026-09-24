import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status, Response
from app.core.auth import get_authenticated_user, AuthenticatedUser
from app.schemas.variant import (
    TargetedResumeVariant,
    CreateTargetedVariantRequest,
    GenerateResumeRequest,
    ApplyVariantChangeRequest,
    AiEditVariantRequest,
    AiEditProposalResponse,
    RevertChangeRequest,
    RevertChangeResponse,
    FitComparisonResponse,
    ExportTargetedResumeResponse,
    ChangeRecord,
)
from app.services.variant_service import VariantService
from app.services.resume_generation_service import ResumeGenerationService
from app.core.rate_limiter import resume_generation_limiter, ai_edit_limiter

router = APIRouter(prefix="/variants", tags=["Targeted Resume Variants"])

VARIANT_ID_PATTERN = r"^[a-zA-Z0-9_\-]+$"


@router.post(
    "/{variant_id}/ai-edit",
    response_model=AiEditProposalResponse,
    summary="Generate an unpersisted AI edit proposal for a single resume bullet or summary",
)
async def ai_edit_variant_endpoint(
    variant_id: str = Path(..., pattern=VARIANT_ID_PATTERN, description="Variant ID"),
    req: AiEditVariantRequest = ...,
    current_user: AuthenticatedUser = Depends(get_authenticated_user),
) -> AiEditProposalResponse:
    await ai_edit_limiter.check(current_user.uid)
    try:
        return await asyncio.wait_for(
            VariantService.propose_ai_edit(current_user, variant_id, req),
            timeout=90.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="AI edit timed out after 90 seconds. Please try again.",
        )


@router.post(
    "/generate",
    response_model=TargetedResumeVariant,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a role-targeted resume variant with tailored bullets and executive summary",
)
async def generate_role_resume_endpoint(
    req: GenerateResumeRequest,
    current_user: AuthenticatedUser = Depends(get_authenticated_user),
) -> TargetedResumeVariant:
    await resume_generation_limiter.check(current_user.uid)
    try:
        return await asyncio.wait_for(
            ResumeGenerationService.generate_role_targeted_resume(current_user, req),
            timeout=90.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Resume generation timed out after 90 seconds. Please try again.",
        )


@router.post(
    "/create",
    response_model=TargetedResumeVariant,
    status_code=status.HTTP_201_CREATED,
    summary="Fork an immutable targeted resume variant for a specific job target",
)
async def create_variant_endpoint(
    req: CreateTargetedVariantRequest,
    current_user: AuthenticatedUser = Depends(get_authenticated_user),
) -> TargetedResumeVariant:
    return await VariantService.create_targeted_variant(current_user, req)


@router.get(
    "/{variant_id}",
    response_model=TargetedResumeVariant,
    summary="Fetch targeted resume variant with full change ledger and snapshot",
)
async def get_variant_endpoint(
    variant_id: str = Path(..., pattern=VARIANT_ID_PATTERN, description="Variant ID"),
    current_user: AuthenticatedUser = Depends(get_authenticated_user),
) -> TargetedResumeVariant:
    return await VariantService.get_targeted_variant(current_user, variant_id)


@router.post(
    "/{variant_id}/apply-change",
    summary="Apply an approved modification to the targeted variant, recording to version ledger",
)
async def apply_variant_change_endpoint(
    variant_id: str = Path(..., pattern=VARIANT_ID_PATTERN, description="Variant ID"),
    req: ApplyVariantChangeRequest = ...,
    current_user: AuthenticatedUser = Depends(get_authenticated_user),
):
    variant, change_record = await VariantService.apply_change_to_variant(current_user, variant_id, req)
    return {
        "success": True,
        "variantId": variant.variant_id,
        "newVersion": variant.version,
        "changeRecord": change_record.model_dump(by_alias=True),
        "message": f"Change applied successfully. Variant is now at version {variant.version}.",
    }


@router.post(
    "/{variant_id}/revert-change",
    response_model=RevertChangeResponse,
    summary="Revert an applied change, restoring original text and appending revert audit record",
)
async def revert_variant_change_endpoint(
    variant_id: str = Path(..., pattern=VARIANT_ID_PATTERN, description="Variant ID"),
    req: RevertChangeRequest = ...,
    current_user: AuthenticatedUser = Depends(get_authenticated_user),
) -> RevertChangeResponse:
    return await VariantService.revert_change_on_variant(current_user, variant_id, req.change_id)


@router.get(
    "/{variant_id}/fit-comparison",
    response_model=FitComparisonResponse,
    summary="Compute before / after fit progression from stored baseline & current analysis snapshots",
)
async def fit_comparison_endpoint(
    variant_id: str = Path(..., pattern=VARIANT_ID_PATTERN, description="Variant ID"),
    current_user: AuthenticatedUser = Depends(get_authenticated_user),
) -> FitComparisonResponse:
    return await VariantService.get_fit_comparison(current_user, variant_id)


@router.get(
    "/{variant_id}/export",
    response_model=ExportTargetedResumeResponse,
    summary="Read-only export generator reading strictly from the targeted resume snapshot",
)
async def export_variant_endpoint(
    variant_id: str = Path(..., pattern=VARIANT_ID_PATTERN, description="Variant ID"),
    format: str = Query("markdown", enum=["markdown", "plain_text", "json"]),
    current_user: AuthenticatedUser = Depends(get_authenticated_user),
) -> ExportTargetedResumeResponse:
    return await VariantService.export_targeted_variant_snapshot(current_user, variant_id, fmt=format)


@router.get(
    "/{variant_id}/export/pdf",
    summary="Read-only PDF export generator reading strictly from the targeted resume snapshot",
)
async def export_variant_pdf_endpoint(
    variant_id: str = Path(..., pattern=VARIANT_ID_PATTERN, description="Variant ID"),
    template: str = Query("ats", description="PDF template design style"),
    current_user: AuthenticatedUser = Depends(get_authenticated_user),
) -> Response:
    pdf_bytes, filename = await VariantService.export_targeted_variant_pdf(current_user, variant_id, template=template)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )
