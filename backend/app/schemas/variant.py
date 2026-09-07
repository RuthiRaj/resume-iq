from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.common import ScoreBreakdown
from app.schemas.requirement_match import (
    EvidenceSourceSection,
    RequirementMatch,
)
from app.schemas.candidate import CandidateEvidence
from app.schemas.analyze import AnalyzeResponse

RequirementImportance = Literal["MustHave", "Preferred", "Unspecified"]
MatchStatus = Literal["StrongMatch", "PartialMatch", "Missing"]


# --- 1. Change & Version Ledger ---

ChangeActionType = Literal["ApplyRemediation", "DirectEdit", "RevertChange", "CandidateFactAddition"]
ChangeStatus = Literal["Draft", "Approved", "Applied", "Reverted"]


class ChangeRecord(BaseModel):
    id: str = Field(..., description="Unique change record ID (chg_...)")
    remediation_id: Optional[str] = Field(default=None, alias="remediationId")
    action_type: ChangeActionType = Field(default="ApplyRemediation", alias="actionType")
    requirement_name: str = Field(..., alias="requirementName")
    section: EvidenceSourceSection = Field(default="Experience")
    target_item_id: str = Field(..., alias="targetItemId", description="e.g. exp_0, proj_1")
    target_bullet_index: Optional[int] = Field(default=None, ge=0, alias="targetBulletIndex")
    original_text: str = Field(default="", alias="originalText")
    proposed_text: str = Field(default="", alias="proposedText")
    approved_text: str = Field(..., alias="approvedText")
    status: ChangeStatus = Field(default="Applied")
    version_introduced: int = Field(default=1, ge=1, alias="versionIntroduced")
    version_reverted: Optional[int] = Field(default=None, ge=1, alias="versionReverted")
    applied_at: str = Field(..., alias="appliedAt")
    reverted_at: Optional[str] = Field(default=None, alias="revertedAt")
    reverted_change_id: Optional[str] = Field(default=None, alias="revertedChangeId")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


# --- 2. Targeted Resume Variant Model ---

class TargetedResumeVariant(BaseModel):
    variant_id: str = Field(..., alias="variantId")
    master_resume_id: str = Field(..., alias="masterResumeId")
    title: str
    target_role: str = Field(..., alias="targetRole")
    target_company: Optional[str] = Field(default="", alias="targetCompany")
    job_description_hash: str = Field(..., alias="jobDescriptionHash")
    version: int = Field(default=1, ge=1)
    is_targeted_variant: bool = Field(default=True, alias="isTargetedVariant")

    # Authoritative Persisted Analysis Snapshots
    baseline_score: Optional[int] = Field(default=None, alias="baselineScore")
    baseline_breakdown: Optional[ScoreBreakdown] = Field(default=None, alias="baselineBreakdown")
    baseline_matches: List[RequirementMatch] = Field(default_factory=list, alias="baselineMatches")

    current_score: Optional[int] = Field(default=None, alias="currentScore")
    current_breakdown: Optional[ScoreBreakdown] = Field(default=None, alias="currentBreakdown")
    current_matches: List[RequirementMatch] = Field(default_factory=list, alias="currentMatches")
    score_delta: Optional[int] = Field(default=None, alias="scoreDelta")

    # Strongly-Typed Forked Candidate Evidence Snapshot
    snapshot: CandidateEvidence

    # Granular Change & Version Ledger
    change_ledger: List[ChangeRecord] = Field(default_factory=list, alias="changeLedger")

    created_at: str = Field(..., alias="createdAt")
    updated_at: str = Field(..., alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


# --- 3. Before / After Fit Comparison ---

StatusProgression = Literal["Resolved", "Improved", "Unchanged", "UnresolvedHardGap"]


class RequirementProgression(BaseModel):
    requirement_name: str = Field(..., alias="requirementName")
    category: str
    importance: RequirementImportance
    baseline_status: MatchStatus = Field(..., alias="baselineStatus")
    current_status: MatchStatus = Field(..., alias="currentStatus")
    progression: StatusProgression = Field(..., alias="progression")
    verified_evidence: Optional[str] = Field(default="", alias="verifiedEvidence")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class FitComparisonResponse(BaseModel):
    variant_id: str = Field(..., alias="variantId")
    target_role: str = Field(..., alias="targetRole")
    target_company: Optional[str] = Field(default="", alias="targetCompany")
    baseline_score: int = Field(..., alias="baselineScore")
    current_score: int = Field(..., alias="currentScore")
    score_delta: int = Field(..., alias="scoreDelta")
    baseline_breakdown: ScoreBreakdown = Field(..., alias="baselineBreakdown")
    current_breakdown: ScoreBreakdown = Field(..., alias="currentBreakdown")
    requirement_progressions: List[RequirementProgression] = Field(default_factory=list, alias="requirementProgressions")
    total_gaps_resolved: int = Field(..., alias="totalGapsResolved")
    total_gaps_remaining: int = Field(..., alias="totalGapsRemaining")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


# --- 4. API Request / Response Contracts ---

class CreateTargetedVariantRequest(BaseModel):
    master_resume_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        alias="masterResumeId",
        description="ID of source master resume",
    )
    target_role: str = Field(..., min_length=1, max_length=150, alias="targetRole")
    target_company: Optional[str] = Field(default="", max_length=150, alias="targetCompany")
    job_description: str = Field(..., min_length=1, max_length=50000, alias="jobDescription")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class ApplyVariantChangeRequest(BaseModel):
    remediation_id: Optional[str] = Field(default=None, max_length=100, alias="remediationId")
    requirement_name: str = Field(..., min_length=1, max_length=200, alias="requirementName")
    section: EvidenceSourceSection = Field(default="Experience")
    target_item_id: str = Field(
        default="exp_0",
        min_length=1,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        alias="targetItemId",
    )
    target_bullet_index: Optional[int] = Field(default=None, ge=0, le=1000, alias="targetBulletIndex")
    approved_bullet: str = Field(..., min_length=1, max_length=2000, alias="approvedBullet")
    source_evidence_id: Optional[str] = Field(default=None, max_length=64, alias="sourceEvidenceId")
    expected_version: Optional[int] = Field(default=None, ge=1, alias="expectedVersion")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class RevertChangeRequest(BaseModel):
    change_id: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_\-]+$", alias="changeId")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class RevertChangeResponse(BaseModel):
    success: bool
    variant_id: str = Field(..., alias="variantId")
    change_id: str = Field(..., alias="changeId")
    revert_change_id: str = Field(..., alias="revertChangeId")
    new_version: int = Field(..., alias="newVersion")
    message: str

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class ExportTargetedResumeRequest(BaseModel):
    format: Literal["markdown", "plain_text", "json"] = "markdown"

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class ExportTargetedResumeResponse(BaseModel):
    variant_id: str = Field(..., alias="variantId")
    title: str
    target_role: str = Field(..., alias="targetRole")
    target_company: Optional[str] = Field(default="", alias="targetCompany")
    version: int
    format: str
    content: str
    exported_at: str = Field(..., alias="exportedAt")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)
