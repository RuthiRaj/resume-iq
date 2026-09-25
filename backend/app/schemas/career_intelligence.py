"""
Pydantic v2 Schemas for Career Intelligence & Experiential Gap Bridging (Phase 5.0)

Defines strongly-typed, deterministic contracts for:
- Skill relationship types and transferability rules
- Transferable skill bridge possibilities
- Structured candidate attestation payloads
- Actionable learning paths, project blueprints, and gap remediation strategies
"""

from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.requirement_match import GapType, EvidenceSourceSection
from app.schemas.remediation import ValidationResult, RemediationStatus
from app.schemas.variant import ChangeRecord

SkillRelationshipType = Literal[
    "FRAMEWORK_FAMILY",
    "DATABASE_FAMILY",
    "LANGUAGE_FAMILY",
    "CLOUD_PLATFORM_FAMILY",
    "DEVOPS_ORCHESTRATION",
    "ML_FRAMEWORK_FAMILY",
    "CONCEPTUAL_TRANSFER",
]

GapSeverity = Literal[
    "HardExperientialGap",
    "MissingDomainCertification",
    "LearnableAdjacentSkill",
    "CandidateAttestationRequired",
]


class SkillTransferabilityRule(BaseModel):
    """
    Deterministic rule mapping source skill to target adjacent skill.
    Directional: source_skill -> target_skill does NOT imply target_skill -> source_skill.
    """
    source_skill: str = Field(..., alias="sourceSkill", description="Canonical source skill verified in candidate profile")
    target_skill: str = Field(..., alias="targetSkill", description="Canonical target requirement skill")
    relationship_type: SkillRelationshipType = Field(..., alias="relationshipType")
    transferability_score: float = Field(..., ge=0.0, le=1.0, alias="transferabilityScore", description="Transfer strength metric")
    transfer_rationale: str = Field(..., alias="transferRationale", description="Architectural reasoning for adjacency")
    shared_competencies: List[str] = Field(default_factory=list, alias="sharedCompetencies", description="Concepts shared between technologies")
    critical_differences: List[str] = Field(default_factory=list, alias="criticalDifferences", description="Key paradigms requiring explicit attestation")
    verification_questions: List[str] = Field(default_factory=list, alias="verificationQuestions", description="Targeted questions to prompt user attestation")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class TransferableSkillBridge(BaseModel):
    """
    Evaluated bridge opportunity linking a missing requirement to verified candidate evidence.
    NEVER automatically classified as StrongMatch.
    """
    bridge_id: str = Field(..., alias="bridgeId", description="Unique bridge identifier (brg_...)")
    required_skill: str = Field(..., alias="requiredSkill")
    candidate_skill: str = Field(..., alias="candidateSkill")
    source_evidence_id: str = Field(..., alias="sourceEvidenceId", description="Evidence ID containing candidate skill")
    source_evidence_title: str = Field(default="", alias="sourceEvidenceTitle")
    source_section: EvidenceSourceSection = Field(default="Experience", alias="sourceSection")
    relationship_type: SkillRelationshipType = Field(..., alias="relationshipType")
    transferability_score: float = Field(..., ge=0.0, le=1.0, alias="transferabilityScore")
    transfer_rationale: str = Field(..., alias="transferRationale")
    shared_competencies: List[str] = Field(default_factory=list, alias="sharedCompetencies")
    critical_differences: List[str] = Field(default_factory=list, alias="criticalDifferences")
    attestation_prompt: str = Field(..., alias="attestationPrompt")
    status: Literal["TransferablePossibility", "AttestationRequired", "UserAttested", "Dismissed"] = Field(
        default="TransferablePossibility"
    )

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class ActionableLearningPath(BaseModel):
    """Structured, actionable learning curriculum for ungrounded gaps."""
    title: str
    estimated_weeks: int = Field(default=2, ge=1, le=52, alias="estimatedWeeks")
    key_milestones: List[str] = Field(default_factory=list, alias="keyMilestones")
    authoritative_docs_url: Optional[str] = Field(default=None, alias="authoritativeDocsUrl")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class ProjectBlueprint(BaseModel):
    """Concrete, verifiable portfolio project plan demonstrating a missing capability."""
    project_title: str = Field(..., alias="projectTitle")
    problem_statement: str = Field(..., alias="problemStatement")
    architecture_components: List[str] = Field(default_factory=list, alias="architectureComponents")
    demonstrated_skills: List[str] = Field(default_factory=list, alias="demonstratedSkills")
    verification_checklist: List[str] = Field(default_factory=list, alias="verificationChecklist")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class GapRemediationStrategy(BaseModel):
    """Honest remediation blueprint for hard or unverified skill gaps."""
    requirement_name: str = Field(..., alias="requirementName")
    gap_type: GapType = Field(default="MissingEvidence", alias="gapType")
    severity: GapSeverity = Field(default="HardExperientialGap")
    remediation_guidance: str = Field(..., alias="remediationGuidance")
    learning_paths: List[ActionableLearningPath] = Field(default_factory=list, alias="learningPaths")
    project_blueprints: List[ProjectBlueprint] = Field(default_factory=list, alias="projectBlueprints")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class AnalyzeGapsRequest(BaseModel):
    """Request payload to analyze gaps and discover transferable bridges for a variant."""
    variant_id: str = Field(..., alias="variantId", min_length=1, max_length=100)
    job_description: Optional[str] = Field(default="", alias="jobDescription", max_length=10000)

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class AnalyzeGapsResponse(BaseModel):
    """Comprehensive gap analysis report with bridges and remediation strategies."""
    variant_id: str = Field(..., alias="variantId")
    total_requirements: int = Field(default=0, alias="totalRequirements")
    matched_count: int = Field(default=0, alias="matchedCount")
    transferable_bridges_count: int = Field(default=0, alias="transferableBridgesCount")
    hard_gaps_count: int = Field(default=0, alias="hardGapsCount")
    transferable_bridges: List[TransferableSkillBridge] = Field(default_factory=list, alias="transferableBridges")
    hard_gap_remediations: List[GapRemediationStrategy] = Field(default_factory=list, alias="hardGapRemediations")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class CandidateAttestationRequest(BaseModel):
    """
    Structured candidate attestation payload to bridge a gap with genuine real-world facts.
    Requires substantive context and action details.
    """
    variant_id: str = Field(..., alias="variantId", min_length=1, max_length=100)
    requirement_name: str = Field(..., alias="requirementName", min_length=1, max_length=200)
    adjacent_skill_used: Optional[str] = Field(default=None, alias="adjacentSkillUsed", max_length=100)
    target_item_id: str = Field(..., alias="targetItemId", min_length=1, max_length=50, description="e.g. exp_0, proj_1")
    target_bullet_index: Optional[int] = Field(default=None, ge=0, le=1000, alias="targetBulletIndex")
    attested_context: str = Field(..., alias="attestedContext", min_length=5, max_length=500, description="Where this took place")
    attested_actions: str = Field(..., alias="attestedActions", min_length=5, max_length=500, description="Specific real-world actions executed")
    duration_or_scale: Optional[str] = Field(default=None, alias="durationOrScale", max_length=100)
    expected_version: Optional[int] = Field(default=None, ge=1, alias="expectedVersion")
    apply_to_workspace: bool = Field(default=False, alias="applyToWorkspace", description="Default False: never mutates root workspace without consent")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class CandidateAttestationRecord(BaseModel):
    """Auditable persistence record for a verified candidate attestation."""
    attestation_id: str = Field(..., alias="attestationId")
    user_id: str = Field(..., alias="userId")
    variant_id: str = Field(..., alias="variantId")
    requirement_name: str = Field(..., alias="requirementName")
    adjacent_skill: Optional[str] = Field(default=None, alias="adjacentSkill")
    target_item_id: str = Field(..., alias="targetItemId")
    target_bullet_index: Optional[int] = Field(default=None, alias="targetBulletIndex")
    attested_fact: str = Field(..., alias="attestedFact")
    provenance_hash: str = Field(..., alias="provenanceHash", description="SHA-256 integrity anchor")
    created_at: str = Field(..., alias="createdAt")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class AttestSkillResponse(BaseModel):
    """Response returned upon successful validation and ledger recording of an attestation."""
    success: bool = True
    attestation_id: str = Field(..., alias="attestationId")
    status: RemediationStatus = "Applied"
    requirement_name: str = Field(..., alias="requirementName")
    change_record: ChangeRecord = Field(..., alias="changeRecord")
    new_version: int = Field(..., alias="newVersion")
    validation: ValidationResult
    message: str

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)
