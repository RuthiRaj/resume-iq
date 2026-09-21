"""
Ingestion Schemas for ResumeIQ

Defines the data models and contracts for document text extraction,
structured candidate parsing, reviewable pending ingestion drafts, and
master workspace hydration confirmation.
"""

from typing import Optional, List, Literal, Dict
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.profile import ProfileDTO
from app.schemas.candidate import CandidateEvidence

IngestionStatus = Literal["Pending", "Processing", "Parsed", "Completed", "Failed"]


class ParsedCandidateProfile(BaseModel):
    """Structured candidate data extracted from raw resume text."""
    profile: ProfileDTO = Field(default_factory=ProfileDTO, description="Personal profile details")
    evidence: CandidateEvidence = Field(default_factory=CandidateEvidence, description="Candidate career evidence")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class IngestionDraft(BaseModel):
    """Reviewable pending draft created from resume ingestion."""
    ingestion_id: str = Field(..., alias="ingestionId", description="Unique ingestion draft ID")
    document_name: str = Field(..., alias="documentName", description="Sanitized original document filename")
    document_type: str = Field(default="Resume", alias="documentType", description="Document type")
    file_size_bytes: int = Field(..., alias="fileSizeBytes", description="File size in bytes")
    status: IngestionStatus = Field(default="Parsed", description="Current parsing status")
    raw_text_snippet: Optional[str] = Field(default=None, alias="rawTextSnippet", description="Snippet of extracted text")
    raw_text_char_count: int = Field(default=0, alias="rawTextCharCount", description="Character count of extracted text")
    parsed_data: Optional[ParsedCandidateProfile] = Field(default=None, alias="parsedData", description="Structured candidate profile")
    error_message: Optional[str] = Field(default=None, alias="errorMessage", description="Failure reason if parsing failed")
    file_url: Optional[str] = Field(default=None, alias="fileUrl", description="Publicly resolvable URL of the stored original document (Cloudinary), if the backup upload succeeded")
    created_at: str = Field(..., alias="createdAt", description="ISO 8601 creation timestamp")
    updated_at: str = Field(..., alias="updatedAt", description="ISO 8601 update timestamp")
    completed_at: Optional[str] = Field(default=None, alias="completedAt", description="ISO 8601 timestamp when draft was confirmed & imported")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class IngestResumeResponse(BaseModel):
    """API response contract for resume document ingestion."""
    success: bool
    draft: IngestionDraft
    message: str

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class IngestionConfirmRequest(BaseModel):
    """User-reviewed and approved candidate data for master workspace hydration."""
    parsed_data: ParsedCandidateProfile = Field(..., alias="parsedData", description="Approved candidate profile and evidence")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class IngestionConfirmResponse(BaseModel):
    """Response contract after master workspace hydration confirmation."""
    success: bool
    ingestion_id: str = Field(..., alias="ingestionId")
    status: IngestionStatus
    message: str
    hydrated_summary: Dict[str, int] = Field(default_factory=dict, alias="hydratedSummary")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)
