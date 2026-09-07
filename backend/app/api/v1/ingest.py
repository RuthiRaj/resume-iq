"""
Ingestion API Router for ResumeIQ

Provides REST endpoints for resume document ingestion (PDF, DOCX, TXT),
draft retrieval, and user confirmation with master workspace hydration.
"""

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from app.core.auth import get_authenticated_user, AuthenticatedUser
from app.schemas.ingestion import (
    IngestionDraft,
    IngestResumeResponse,
    IngestionConfirmRequest,
    IngestionConfirmResponse,
)
from app.services.ingestion_service import IngestionService
from app.services.document_extractor import validate_document_upload

router = APIRouter(prefix="/resumes", tags=["Resumes Ingestion"])


@router.post("/ingest", response_model=IngestResumeResponse, summary="Ingest resume document (PDF, DOCX, TXT) into reviewable draft")
async def ingest_resume_endpoint(
    file: UploadFile = File(...),
    current_user: AuthenticatedUser = Depends(get_authenticated_user),
) -> IngestResumeResponse:
    """
    Uploads and parses a resume document (PDF, DOCX, TXT) into a reviewable draft.
    Does NOT overwrite or alter canonical master profile or candidate evidence.
    """
    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No document file was uploaded.",
        )

    # Read binary content
    try:
        content = await file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to read uploaded file payload.",
        ) from exc

    # Pre-validate file boundaries
    validate_document_upload(file.filename, len(content))

    draft = await IngestionService.ingest_resume(
        user=current_user,
        filename=file.filename,
        content=content,
    )

    return IngestResumeResponse(
        success=True,
        draft=draft,
        message="Resume document ingested successfully into reviewable draft.",
    )


@router.get("/ingest/{ingestion_id}", response_model=IngestResumeResponse, summary="Get pending resume ingestion draft by ID")
async def get_ingestion_draft_endpoint(
    ingestion_id: str,
    current_user: AuthenticatedUser = Depends(get_authenticated_user),
) -> IngestResumeResponse:
    """Loads a specific resume ingestion draft for the authenticated user."""
    draft = await IngestionService.get_ingestion_draft(
        user=current_user,
        ingestion_id=ingestion_id,
    )
    return IngestResumeResponse(
        success=True,
        draft=draft,
        message="Ingestion draft retrieved successfully.",
    )


@router.post("/ingest/{ingestion_id}/confirm", response_model=IngestionConfirmResponse, summary="Confirm user-reviewed draft and hydrate master workspace")
async def confirm_ingestion_endpoint(
    ingestion_id: str,
    req: IngestionConfirmRequest,
    current_user: AuthenticatedUser = Depends(get_authenticated_user),
) -> IngestionConfirmResponse:
    """
    Confirms the user-reviewed candidate profile & evidence and hydrates the approved data
    into the authenticated candidate's master workspace.
    """
    return await IngestionService.confirm_and_hydrate_ingestion(
        user=current_user,
        ingestion_id=ingestion_id,
        reviewed_data=req.parsed_data,
    )
