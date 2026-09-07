import hashlib
from typing import Literal, Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.requirement_match import GapType, EvidenceSourceSection

RemediationEligibility = Literal[
    "Remediable",              # Existing bullet can be clarified, quantified, or strengthened
    "RequiresCandidateFacts",  # Missing evidence or SkillTag needing real-world user context
    "PartiallyRemediable",     # Adjacent technology where bridge can be highlighted
    "NotRemediable",           # Hard experiential gap (e.g. 10+ yrs required vs 3 yrs actual)
]

RemediationActionType = Literal[
    "ImproveExistingBullet",      # Enhance an existing verified bullet
    "PromptForMissingFacts",      # Prompt candidate for missing real-world facts
    "AddProjectContext",          # Prompt candidate to elaborate on a standalone SkillTag
    "ClarifyAdjacentTechnology",  # Highlight transferable skills between adjacent technologies
    "ExplainHardGap",             # Non-remediable structural gap (explains reality neutrally)
    "None",                       # Requirement already StrongMatch
]

RemediationStatus = Literal[
    "Draft",
    "Validated",
    "RequiresCandidateInput",
    "UserEdited",
    "UserApproved",
    "Applied",
    "ReAnalyzed",
]

ClaimCategory = Literal[
    "Metric",
    "Scale",
    "Technology",
    "SeniorityRole",
    "TeamOrganization",
    "Duration",
    "Infrastructure",
]


class UnsupportedClaim(BaseModel):
    category: ClaimCategory
    claim_text: str = Field(..., alias="claimText")
    reason: str
    prompt_for_user: str = Field(..., alias="promptForUser")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class ValidationResult(BaseModel):
    is_valid: bool = Field(default=True, alias="isValid")
    status: RemediationStatus = Field(default="Validated")
    unsupported_claims: List[UnsupportedClaim] = Field(
        default_factory=list, alias="unsupportedClaims"
    )
    sanitized_bullet: str = Field(default="", alias="sanitizedBullet")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class RemediationSuggestion(BaseModel):
    id: str = Field(..., description="Unique remediation suggestion identifier")
    requirement_name: str = Field(..., alias="requirementName")
    importance: Literal["MustHave", "Preferred", "Unspecified"] = Field(
        default="MustHave"
    )
    gap_type: GapType = Field(..., alias="gapType")
    eligibility: RemediationEligibility = Field(default="Remediable")
    action_type: RemediationActionType = Field(
        default="ImproveExistingBullet", alias="actionType"
    )
    target_section: EvidenceSourceSection = Field(
        default="None", alias="targetSection"
    )

    # Stable Source Provenance Anchor
    source_evidence_id: str = Field(
        default="",
        alias="sourceEvidenceId",
        description="Deterministic hash of section, experience ID, and original text to prevent stale edits",
    )
    original_evidence: Optional[str] = Field(default="", alias="originalEvidence")
    target_experience_id: Optional[str] = Field(
        default="", alias="targetExperienceId"
    )
    target_bullet_index: Optional[int] = Field(
        default=None, alias="targetBulletIndex"
    )

    # Truthful Remediation Content
    suggested_bullet: Optional[str] = Field(
        default="",
        alias="suggestedBullet",
        description="Grounded improved bullet (populated ONLY when existing evidence is present and validated)",
    )
    missing_fact_prompt: Optional[str] = Field(
        default="",
        alias="missingFactPrompt",
        description="Targeted question asking candidate for missing real-world facts",
    )
    guidance: str = Field(
        ...,
        description="Actionable advice explaining the gap and remediation strategy",
    )
    potential_impact: Literal["High", "Medium", "Low"] = Field(
        default="Medium",
        alias="potentialImpact",
        description="Categorical indicator of ATS improvement potential",
    )
    status: RemediationStatus = Field(
        default="Draft", description="Server-controlled lifecycle state"
    )
    validation: ValidationResult = Field(
        default_factory=ValidationResult,
        description="Claim preservation validation report",
    )

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class SynthesizeBulletRequest(BaseModel):
    requirement_name: str = Field(..., alias="requirementName", min_length=1, max_length=200)
    candidate_fact: str = Field(..., alias="candidateFact", min_length=5, max_length=1000)
    target_role: Optional[str] = Field(default="", alias="targetRole", max_length=150)
    job_context: Optional[str] = Field(default="", alias="jobContext", max_length=2000)

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class SynthesizeBulletResponse(BaseModel):
    requirement_name: str = Field(..., alias="requirementName")
    synthesized_bullet: str = Field(..., alias="synthesizedBullet")
    validation: ValidationResult
    status: RemediationStatus = "Validated"

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class ApplyRemediationRequest(BaseModel):
    resume_id: str = Field(..., alias="resumeId", min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_\-]+$")
    remediation_id: str = Field(..., alias="remediationId", min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_\-]+$")
    source_evidence_id: str = Field(..., alias="sourceEvidenceId", max_length=100)
    target_section: EvidenceSourceSection = Field(..., alias="targetSection")
    target_experience_id: Optional[str] = Field(default="", alias="targetExperienceId", max_length=100)
    target_bullet_index: Optional[int] = Field(default=None, ge=0, le=1000, alias="targetBulletIndex")
    approved_bullet: str = Field(..., alias="approvedBullet", min_length=5, max_length=1000)
    target_role: Optional[str] = Field(default="", alias="targetRole", max_length=150)
    target_company: Optional[str] = Field(default="", alias="targetCompany", max_length=150)

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class ApplyRemediationResponse(BaseModel):
    success: bool
    status: RemediationStatus = "Applied"
    targeted_resume_id: str = Field(..., alias="targetedResumeId")
    message: str

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)
