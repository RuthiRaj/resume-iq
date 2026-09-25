"""
Pydantic v2 Schemas for Career Roadmap Engine (Phase 5.1)

Defines strongly-typed contracts for:
- Progressive capability roadmap plans (RoadmapPlan)
- Grounded milestones (RoadmapMilestone)
- Deterministic progress state machine (MilestoneState)
- Auditable verification artifacts (VerificationArtifact)
- Milestone progression and roadmap API contracts
"""

from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.career_intelligence import (
    TransferableSkillBridge,
    ActionableLearningPath,
    ProjectBlueprint,
    CandidateAttestationRequest,
)

MilestoneCategory = Literal[
    "TransferableBridge",
    "CoreFoundation",
    "VerifiableProject",
    "DomainCertification",
]

MilestoneState = Literal[
    "NOT_STARTED",
    "IN_PROGRESS",
    "ARTIFACT_SUBMITTED",
    "VERIFIED_PROJECT",
    "ATTESTED",
]

ArtifactType = Literal[
    "GitHubRepository",
    "DeploymentUrl",
    "TechnicalWriteup",
    "AttestationRecord",
]


class VerificationArtifact(BaseModel):
    """Auditable proof of project completion or attestation for a roadmap milestone."""
    artifact_id: str = Field(..., alias="artifactId", description="Unique artifact ID (art_...)")
    artifact_type: ArtifactType = Field(..., alias="artifactType")
    url: Optional[str] = Field(default=None, description="Repository or live URL")
    repository_branch: Optional[str] = Field(default=None, alias="repositoryBranch")
    checklist_completed: List[str] = Field(default_factory=list, alias="checklistCompleted")
    submitted_at: str = Field(..., alias="submittedAt")
    provenance_hash: str = Field(..., alias="provenanceHash", description="SHA-256 integrity hash")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class VerificationArtifactInput(BaseModel):
    """Payload provided by the user when submitting a verification artifact."""
    artifact_type: ArtifactType = Field(default="GitHubRepository", alias="artifactType")
    url: Optional[str] = Field(default=None, max_length=500)
    repository_branch: Optional[str] = Field(default=None, alias="repositoryBranch", max_length=100)
    checklist_completed: List[str] = Field(default_factory=list, alias="checklistCompleted")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class RoadmapMilestone(BaseModel):
    """
    A single grounded milestone within a career capability roadmap.
    Traceable to prerequisite evidence and target requirements.
    """
    milestone_id: str = Field(..., alias="milestoneId", description="Unique milestone ID (ms_...)")
    order_index: int = Field(..., ge=0, alias="orderIndex")
    title: str
    category: MilestoneCategory
    requirement_name: str = Field(..., alias="requirementName")
    target_capability: str = Field(..., alias="targetCapability")
    prerequisite_evidence_ids: List[str] = Field(default_factory=list, alias="prerequisiteEvidenceIds")
    source_bridge_id: Optional[str] = Field(default=None, alias="sourceBridgeId")
    rationale: str
    estimated_weeks: int = Field(default=2, ge=1, le=52, alias="estimatedWeeks")
    learning_path: Optional[ActionableLearningPath] = Field(default=None, alias="learningPath")
    project_blueprint: Optional[ProjectBlueprint] = Field(default=None, alias="projectBlueprint")
    bridge_details: Optional[TransferableSkillBridge] = Field(default=None, alias="bridgeDetails")
    state: MilestoneState = Field(default="NOT_STARTED")
    verification_artifact: Optional[VerificationArtifact] = Field(default=None, alias="verificationArtifact")
    started_at: Optional[str] = Field(default=None, alias="startedAt")
    completed_at: Optional[str] = Field(default=None, alias="completedAt")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class RoadmapProvenance(BaseModel):
    """Cryptographic and contextual provenance tracking why and when the roadmap was generated."""
    source_variant_id: Optional[str] = Field(default=None, alias="sourceVariantId")
    source_analysis_score: Optional[int] = Field(default=None, alias="sourceAnalysisScore")
    generated_at: str = Field(..., alias="generatedAt")
    generator_version: str = Field(default="5.1.0", alias="generatorVersion")
    provenance_hash: str = Field(..., alias="provenanceHash")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class RoadmapPlan(BaseModel):
    """
    Persistent Career Roadmap Aggregate Document.
    Stored under users/{uid}/roadmaps/{roadmapId}.
    """
    roadmap_id: str = Field(..., alias="roadmapId")
    user_id: str = Field(..., alias="userId")
    title: str
    target_role: str = Field(..., alias="targetRole")
    target_company: Optional[str] = Field(default="", alias="targetCompany")
    target_level: Optional[str] = Field(default="", alias="targetLevel")
    source_variant_id: Optional[str] = Field(default=None, alias="sourceVariantId")
    version: int = Field(default=1, ge=1)
    total_milestones: int = Field(default=0, alias="totalMilestones")
    completed_milestones: int = Field(default=0, alias="completedMilestones")
    overall_progress_pct: int = Field(default=0, ge=0, le=100, alias="overallProgressPct")
    milestones: List[RoadmapMilestone] = Field(default_factory=list)
    provenance: Optional[RoadmapProvenance] = None
    created_at: str = Field(..., alias="createdAt")
    updated_at: str = Field(..., alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class GenerateRoadmapRequest(BaseModel):
    """Request contract for deterministically synthesizing a career roadmap."""
    variant_id: Optional[str] = Field(default=None, alias="variantId", max_length=100)
    target_role: Optional[str] = Field(default=None, alias="targetRole", max_length=200)
    target_company: Optional[str] = Field(default="", alias="targetCompany", max_length=200)
    job_description: Optional[str] = Field(default="", alias="jobDescription", max_length=10000)

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class UpdateMilestoneProgressRequest(BaseModel):
    """Request contract to update milestone state, attach proof artifacts, or submit attestation."""
    milestone_id: str = Field(..., alias="milestoneId")
    target_state: MilestoneState = Field(..., alias="targetState")
    expected_version: int = Field(..., ge=1, alias="expectedVersion")
    artifact: Optional[VerificationArtifactInput] = None
    attestation: Optional[CandidateAttestationRequest] = None
    notes: Optional[str] = Field(default=None, max_length=1000)

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class ListRoadmapsResponse(BaseModel):
    """Response contract listing all active roadmaps for the authenticated candidate."""
    roadmaps: List[RoadmapPlan] = Field(default_factory=list)
    total: int = 0

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class DeleteRoadmapResponse(BaseModel):
    """Response contract after deleting a roadmap plan."""
    success: bool = True
    roadmap_id: str = Field(..., alias="roadmapId")
    message: str

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)
